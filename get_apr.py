import datetime
import json
from pprint import pprint

import requests

from coingecko import get_prices
from multicall import Call, Multicall
from utils import w3, db


def get_apr():
    response = requests.post(
        url="https://api.thegraph.com/subgraphs/name/sullivany/ramses",
        json={
            "query": "{  bribeEntities {    id pair { id symbol }    bribeTokens {      token {        id        symbol        decimals}    }     }}"
        }
    )

    fee_distributors = response.json()['data']['bribeEntities']

    week = 7 * 24 * 60 * 60
    period = int(datetime.datetime.now().timestamp() // week * week + week)

    pairs = {}
    calls = []
    for fee_distributor in fee_distributors:
        fee_distributor_address = fee_distributor['id']

        calls.append(
            Call(
                w3,
                fee_distributor_address,
                ["totalVeShareByPeriod(uint256)(uint256)", period],
                [[fee_distributor_address, lambda v: v[0]]]
            )
        )

        pairs[fee_distributor_address] = {
            'pair_address': fee_distributor['pair']['id'],
            'fee_distributor_address': fee_distributor_address,
            'symbol': fee_distributor['pair']['symbol'],
            'totalVeShareByPeriod': 0,
            'totalUSD': 0,
            'apr': 0,
            'tokens': []
        }

    for address, value in Multicall(w3, calls)().items():
        pairs[address]['totalVeShareByPeriod'] = value

    tokens = {}
    calls = []
    for fee_distributor in fee_distributors:
        fee_distributor_address = fee_distributor['id']
        for token in fee_distributor['bribeTokens']:
            token = token['token']
            token_address = token['id']
            key = f'{fee_distributor_address}-{token_address}'

            calls.append(
                Call(
                    w3,
                    fee_distributor_address,
                    ["tokenTotalSupplyByPeriod(uint256,address)(uint256)", period, token_address],
                    [[key, lambda v: v[0]]]
                )
            )
            tokens[key] = {
                'address': token_address,
                'symbol': token['symbol'],
                'tokenTotalSupplyByPeriod': 0,
                'decimals': int(token['decimals'])
            }

    for address, value in Multicall(w3, calls)().items():
        tokens[address]['tokenTotalSupplyByPeriod'] = value

    symbols = list(set([token['symbol'] for token in tokens.values()]))
    prices = get_prices(symbols)

    for key, token in tokens.items():
        pair_address = key.split('-')[0]
        pair = pairs[pair_address]

        token['price'] = prices[token['symbol']]
        token['totalUSD'] = token['tokenTotalSupplyByPeriod'] / 10 ** token['decimals'] * token['price']

        pair['totalUSD'] += token['totalUSD']
        pair['tokens'].append(token)

    for address, pair in pairs.items():
        if pair['totalVeShareByPeriod'] > 0:
            pair['apr'] = pair['totalUSD'] / 7 * 36500 / (pair['totalVeShareByPeriod'] * prices['RAM'] / 1e18)

            # print(address, pair['symbol'], round(pair['apr']))

    # pprint(pairs['0xec6b34307ce7e83de1b053560ee9974a54c5804d'])

    db.set('apr', json.dumps(pairs))

    return pairs


if __name__ == '__main__':
    get_apr()
