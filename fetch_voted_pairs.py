import json
from pprint import pprint

import requests

from coingecko import get_prices
from multicall import Call, Multicall
from utils import w3, db

period = 1680134400


def get_voted_pairs(token_ids):
    pairs = json.loads(db.get('pairs'))

    calls = []
    for token_id in token_ids:
        for pair_address, pair in pairs.items():
            key = f"{token_id}-{pair_address}"
            if pair['fee_distributor_address'] and pair['totalVeShareByPeriod'] > 0:
                calls.append(
                    Call(
                        w3,
                        pair['fee_distributor_address'],
                        ["veShareByPeriod(uint256,uint256)(uint256)", period, token_id],
                        [[key, lambda v: int(v[0])]]
                    )
                )

    print(len(calls))
    voted_pairs = {}
    for key, weight in Multicall(w3, calls)().items():
        token_id, pair_address = key.split('-')
        token_voted_pairs = voted_pairs.get(token_id, {})
        if weight > 0:
            token_voted_pairs[pair_address] = weight
            voted_pairs[token_id] = token_voted_pairs

    return voted_pairs


def calculate_total_lost():
    with open('pairs.json', 'r') as file:
        pairs = json.load(file)

    symbols = []
    for pair_address, pair in pairs.items():
        symbols += [token['symbol'] for token in pair['fee_distributor_tokens']]
    symbols = list(set(symbols))
    prices = get_prices(symbols)

    for pair_address, pair in pairs.items():
        pair_total_lost = 0
        for token in pair['fee_distributor_tokens']:
            lost_usd = token['lost'] / 10 ** token['decimals'] * prices[token['symbol']]
            if lost_usd > 0:
                token['lost_usd'] = lost_usd
            else:
                token['lost_usd'] = 0
            pair_total_lost += token['lost_usd']
        pair['total_lost'] = pair_total_lost

    return pairs

    # pairs = sorted(pairs.values(), key=lambda p: p['total_lost'], reverse=True)
    # for i in range(10):
    #     pair = pairs[i]
    #     print(pair['symbol'], int(pair['total_lost']))


def main():
    voted_pairs = json.loads(db.get('voted_pairs'))
    if voted_pairs is None:
        voted_pairs = {}

    for i in range(1, 1400, 50):
        print(i, i + 20)
        if str(i) in voted_pairs:
            continue

        voted_pairs.update(
            get_voted_pairs(range(i, i + 50))
        )
        db.set('voted_pairs', json.dumps(voted_pairs))


if __name__ == '__main__':
    main()
