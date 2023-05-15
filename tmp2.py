import json
from pprint import pprint

import requests

from coingecko import get_prices
from multicall import Call, Multicall
from utils import w3, db


def main():
    with open('pairs.json', 'r') as file:
        pairs = json.load(file)

    total_lost = {}

    x = 0
    for address, pair in pairs.items():
        if len(pair['fee_distributor_tokens']) == 0 or 'earned' not in pair['fee_distributor_tokens'][0]:
            x += 1
            continue

        fee_distributor_address = pair['fee_distributor_address']
        calls = []
        print(pair['symbol'])
        for token in pair['fee_distributor_tokens']:
            print('-', token['symbol'])
            calls.append(
                Call(
                    w3,
                    token['address'],
                    ["balanceOf(address)(uint256)", fee_distributor_address],
                    [[token['address'], lambda v: int(v[0])]]
                )
            )

        balances = Multicall(w3, calls)()
        for token in pair['fee_distributor_tokens']:
            token['balance'] = balances[token['address']]
            token['lost'] = token['earned'] - token['balance']

            lost = total_lost.get(token['address'])
            if not lost:
                lost = token.copy()
            else:
                lost['balance'] += token['balance']
                lost['lost'] += token['lost']
            total_lost[token['address']] = lost

    symbols = [token['symbol'] for token in total_lost.values()]
    prices = get_prices(symbols)
    total_lost_usd = 0
    for token_address, token in total_lost.items():
        symbol = token['symbol']
        lost = token['lost'] / 10 ** token['decimals']
        lost_usd = lost * prices[symbol]
        token['lost_usd'] = lost_usd

        if lost > 0:
            print(symbol, lost, int(lost_usd))
            total_lost_usd += lost_usd

    with open('pairs.json', 'w') as file:
        file.write(json.dumps(pairs))

    print(int(total_lost_usd))

    with open('pairs.json', 'w') as file:
        file.write(json.dumps(pairs))

    print(x)


if __name__ == '__main__':
    main()
