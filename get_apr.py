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


def log(msg):
    print(msg)


def _fetch_pairs():
    def get_subgraph_data():
        response = requests.post(
            url="https://api.thegraph.com/subgraphs/name/sullivany/ramses",
            json={
                "query": """{ gaugeEntities { id pair { id symbol reserve0 reserve1 totalSupply token0 { id symbol } token1 { id symbol } } rewardTokens { token { id symbol decimals } } } bribeEntities { id pair { id symbol reserve0 reserve1 totalSupply token0 { id symbol } token1 { id symbol } } bribeTokens { token { id symbol decimals } } } }"""
            }
        )
        if response.status_code == 200:
            data = response.json()['data']
            db.set('v2_subgraph_data', json.dumps(data))
            return data
        else:
            log("Error in subgraph")
            return json.loads(db.get('v2_subgraph_data'))

    subgraph_data = get_subgraph_data()
    fee_distributors = subgraph_data['bribeEntities']
    gauges = subgraph_data['gaugeEntities']

    week = 7 * 24 * 60 * 60
    period = int(datetime.datetime.now().timestamp() // week * week + week)

    pairs = {}
    calls = []
    for fee_distributor in fee_distributors:
        fee_distributor_address = fee_distributor['id']
        pair_address = fee_distributor['pair']['id']

        calls.append(
            Call(
                w3,
                fee_distributor_address,
                ["totalVeShareByPeriod(uint256)(uint256)", period],
                [[pair_address + '-' + str(period), lambda v: v[0]]]
            )
        )
        # calls.append(
        #     Call(
        #         w3,
        #         fee_distributor_address,
        #         ["totalVeShareByPeriod(uint256)(uint256)", period - week],
        #         [[pair_address + '-' + str(period - week), lambda v: v[0]]]
        #     )
        # )

        pairs[pair_address] = {
            'pair_address': pair_address,
            'symbol': fee_distributor['pair']['symbol'],
            'totalSupply': float(fee_distributor['pair']['totalSupply']),
            'price': 0,
            'tvl': 0,
            'token0': {
                'reserve': float(fee_distributor['pair']['reserve0']),
                'address': fee_distributor['pair']['token0']['id'],
                'symbol': fee_distributor['pair']['token0']['symbol'],
                'price': 0
            },
            'token1': {
                'reserve': float(fee_distributor['pair']['reserve1']),
                'address': fee_distributor['pair']['token1']['id'],
                'symbol': fee_distributor['pair']['token1']['symbol'],
                'price': 0
            },
            'fee_distributor_address': fee_distributor_address,
            'gauge_address': '',
            'gaugeTotalSupply': 0,
            'totalVeShareByPeriod': 0,
            'vote_apr': 0,
            'lp_apr': 0,
            'fee_distributor_tokens': [],
            'gauge_tokens': [],
            'current_vote_bribes': [],
            'total_vote_reward_usd': 0,
            'total_current_vote_bribe_usd': 0,
            'total_lp_reward_usd': 0
        }

    for address, value in Multicall(w3, calls)().items():
        address = address.split('-')[0]
        pairs[address]['totalVeShareByPeriod'] += value

    calls = []
    for gauge in gauges:
        gauge_address = gauge['id']
        pair_address = gauge['pair']['id']
        calls.append(
            Call(
                w3,
                gauge_address,
                ["totalSupply()(uint256)"],
                [[pair_address, lambda v: v[0]]]
            ),
        )

        if pair_address not in pairs:
            pairs[pair_address] = {
                'pair_address': pair_address,
                'symbol': gauge['pair']['symbol'],
                'totalSupply': float(gauge['pair']['totalSupply']),
                'price': 0,
                'tvl': 0,
                'token0': {
                    'reserve': float(gauge['pair']['reserve0']),
                    'address': gauge['pair']['token0']['id'],
                    'symbol': gauge['pair']['token0']['symbol'],
                    'price': 0
                },
                'token1': {
                    'reserve': float(gauge['pair']['reserve1']),
                    'address': gauge['pair']['token1']['id'],
                    'symbol': fee_distributor['pair']['token1']['symbol'],
                    'price': 0
                },
                'fee_distributor_address': '',
                'gauge_address': gauge_address,
                'gaugeTotalSupply': 0,
                'totalVeShareByPeriod': 0,
                'vote_apr': 0,
                'lp_apr': 0,
                'fee_distributor_tokens': [],
                'gauge_tokens': [],
                'current_vote_bribes': [],
                'total_vote_reward_usd': 0,
                'total_current_vote_bribe_usd': 0,
                'total_lp_reward_usd': 0
            }

    for address, value in Multicall(w3, calls)().items():
        pairs[address]['gaugeTotalSupply'] = value

    fee_distributor_tokens = {}
    calls = []
    for fee_distributor in fee_distributors:
        fee_distributor_address = fee_distributor['id']
        pair_address = fee_distributor['pair']['id']
        for token in fee_distributor['bribeTokens']:
            token = token['token']
            token_address = token['id']
            key = f'{pair_address}-{token_address}'

            calls.append(
                Call(
                    w3,
                    fee_distributor_address,
                    ["tokenTotalSupplyByPeriod(uint256,address)(uint256)", period, token_address],
                    [[key + '|' + str(period), lambda v: v[0]]]
                )
            )
            # calls.append(
            #     Call(
            #         w3,
            #         fee_distributor_address,
            #         ["tokenTotalSupplyByPeriod(uint256,address)(uint256)", period - week, token_address],
            #         [[key + '|' + str(period - week), lambda v: v[0]]]
            #     )
            # )
            fee_distributor_tokens[key] = {
                'type': 'ft',
                'address': token_address,
                'symbol': token['symbol'],
                'tokenTotalSupplyByPeriod': 0,
                'decimals': int(token['decimals']),
                'totalUSD': 0
            }

    for key, value in Multicall(w3, calls)().items():
        key = key.split('|')[0]
        fee_distributor_tokens[key]['tokenTotalSupplyByPeriod'] += value

    gauge_tokens = {}
    calls = []
    for gauge in gauges:
        gauge_address = gauge['id']
        pair_address = gauge['pair']['id']
        pairs[pair_address]['gauge_address'] = gauge_address
        for token in gauge['rewardTokens']:
            token = token['token']
            token_address = token['id']
            key = f'{pair_address}-{token_address}'

            calls.append(
                Call(
                    w3,
                    gauge_address,
                    ["rewardRate(address)(uint256)", token_address],
                    [[key, lambda v: v[0]]]
                ),
            )

            gauge_tokens[key] = {
                'type': 'gt',
                'address': token_address,
                'symbol': token['symbol'],
                'rewardPerToken': 0,
                'decimals': int(token['decimals'])
            }

    for key, value in Multicall(w3, calls)().items():
        gauge_tokens[key]['rewardRate'] = value

    tokens = fee_distributor_tokens.copy()
    tokens.update(gauge_tokens)
    symbols = [token['symbol'] for token in tokens.values()]
    symbols += [pair['token0']['symbol'] for pair in pairs.values()]
    symbols += [pair['token1']['symbol'] for pair in pairs.values()]

    symbols = list(set(symbols))

    try:
        prices = get_prices(symbols)
        db.set('v2_prices', json.dumps(prices))
    except:
        log("Error on prices")
        prices = json.loads(db.get('v2_prices'))

    current_bribe_tokens = {}
    calls = []
    for fee_distributor in fee_distributors:
        fee_distributor_address = fee_distributor['id']
        pair_address = fee_distributor['pair']['id']
        for token in fee_distributor['bribeTokens']:
            token = token['token']
            token_address = token['id']
            key = f'{pair_address}-{token_address}'

            calls.append(
                Call(
                    w3,
                    fee_distributor_address,
                    ["tokenTotalSupplyByPeriod(uint256,address)(uint256)", period, token_address],
                    [[key, lambda v: v[0]]]
                )
            )
            current_bribe_tokens[key] = {
                'address': token_address,
                'symbol': token['symbol'],
                'tokenTotalSupplyByPeriod': 0,
                'decimals': int(token['decimals']),
                'totalUSD': 0
            }

    for key, value in Multicall(w3, calls)().items():
        pair_address = key.split('-')[0]
        token = current_bribe_tokens[key]

        token['price'] = prices[token['symbol']]
        token['tokenTotalSupplyByPeriod'] = value
        token['totalUSD'] = token['tokenTotalSupplyByPeriod'] / 10 ** token['decimals'] * token['price']

        if token['totalUSD'] > 0:
            pairs[pair_address]['current_vote_bribes'].append(token)
            pairs[pair_address]['total_current_vote_bribe_usd'] += token['totalUSD']

    for address, pair in pairs.items():
        pair['token0']['price'] = prices[pair['token0']['symbol']]
        pair['token1']['price'] = prices[pair['token1']['symbol']]
        pair['tvl'] = pair['token0']['reserve'] * pair['token0']['price'] + pair['token1']['reserve'] * pair['token1']['price']

        if pair['totalSupply'] > 0:
            pair['price'] = pair['tvl'] / pair['totalSupply']

    for key, token in fee_distributor_tokens.items():
        pair_address = key.split('-')[0]
        pair = pairs[pair_address]

        token['price'] = prices[token['symbol']]
        token['totalUSD'] = token['tokenTotalSupplyByPeriod'] / 10 ** token['decimals'] * token['price']
        pair['fee_distributor_tokens'].append(token)

    for key, token in gauge_tokens.items():
        pair_address = key.split('-')[0]
        pair = pairs[pair_address]

        token['price'] = prices[token['symbol']]
        pair['gauge_tokens'].append(token)

    for address, pair in pairs.items():
        if pair['totalVeShareByPeriod'] > 0:
            totalUSD = 0
            for token in pair['fee_distributor_tokens']:
                totalUSD += token['tokenTotalSupplyByPeriod'] / 10 ** token['decimals'] * token['price']
            pair['total_vote_reward_usd'] = totalUSD
            pair['vote_apr'] = totalUSD / 7 * 36500 / (pair['totalVeShareByPeriod'] * prices['RAM'] / 1e18)

        if pair['gaugeTotalSupply'] > 0:
            totalUSD = 0
            for token in pair['gauge_tokens']:
                totalUSD += token['rewardRate'] * week / 10 ** token['decimals'] * token['price']

            pair['total_lp_reward_usd'] = totalUSD
            pair['lp_apr'] = totalUSD / 7 * 36500 / (pair['gaugeTotalSupply'] * pair['price'] / 1e18)

    return pairs


def get_pairs():
    try:
        pairs = _fetch_pairs()
        db.set('pairs', json.dumps(pairs))
    except:
        log("Error on get_pairs")
        pairs = json.loads(db.get('pairs'))
    return pairs


if __name__ == '__main__':
    p = _fetch_pairs()
    pair = p['0x8ac36fbce743b632d228f9c2ea5e3bb8603141c7'.lower()]
    pprint(pair)
