import datetime
import json
from pprint import pprint

import requests

from coingecko import get_prices_from_coingecko
from multicall import Call, Multicall
from utils import w3, db
from v2.prices import get_prices_from_defillama


def get_apr():
    response = requests.post(
        url="https://api.thegraph.com/subgraphs/name/sullivany/ramses",
        json={
            "query": "{  bribeEntities {    id pair { id symbol }    bribeTokens {      token {        id        symbol        decimals}    }     }}"
        }
    )

    fee_distributors = response.json()['data']['bribeEntities']

    week = 7 * 24 * 60 * 60
    now = datetime.datetime.now().timestamp()
    period = int(now // week * week + week)

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
    prices = get_prices_from_coingecko(symbols)

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


def get_subgraph_tokens(catch_errors):
    # get tokens from subgraph
    skip = 0
    tokens = []
    while True:
        query = f"{{ tokens(skip: {skip}, limit: 100) {{ id symbol decimals }} }}"
        response = requests.post(
            url="https://api.thegraph.com/subgraphs/name/ramsesexchange/api-subgraph",
            json={
                "query": query
            }
        )

        if response.status_code == 200:
            new_tokens = response.json()['data']['tokens']
            tokens += new_tokens

            if len(new_tokens) < 100:
                break
            else:
                skip += 100
        else:
            log("Error in subgraph tokens")
            return json.loads(db.get('v2_apr_tokens'))

    # get tokens prices
    symbols = list(set([token['symbol'] for token in tokens]))
    try:
        prices = get_prices_from_coingecko(symbols)
        # prices = get_prices_from_defillama(symbols)
        # db.set('v2_prices', json.dumps(prices))
    except Exception as e:
        if not catch_errors:
            raise e
        log("Error on prices")
        prices = json.loads(db.get('v2_prices'))
    for token in tokens:
        token['price'] = prices[token['symbol']]

    # cache tokens
    # db.set('v2_apr_tokens', json.dumps(tokens))

    return tokens


def get_subgraph_pairs():
    # get pairs from subgraph
    skip = 0
    pairs = []
    while True:
        query = f"{{ pairs(skip: {skip}) {{ id symbol totalSupply token0 reserve0 token1 reserve1 gauge {{ id totalDerivedSupply rewardTokens }} feeDistributor {{ id rewardTokens }} }} }}"
        response = requests.post(
            url="https://api.thegraph.com/subgraphs/name/ramsesexchange/api-subgraph",
            json={
                "query": query
            }
        )

        if response.status_code == 200:
            new_pairs = response.json()['data']['pairs']
            pairs += new_pairs

            if len(new_pairs) < 100:
                break
            else:
                skip += 100
        else:
            log("Error in subgraph pairs")
            return json.loads(db.get('v2_apr_subgraph_pairs'))

    # cache pairs
    # db.set('v2_apr_subgraph_pairs', json.dumps(pairs))

    return pairs


def get_subgraph_data(catch_errors):
    tokens = {}
    for token in get_subgraph_tokens(catch_errors):
        tokens[token['id']] = token
    pairs = get_subgraph_pairs()

    # todo: limit quick fix
    # gauge_response = requests.post(
    #     url="https://api.thegraph.com/subgraphs/name/sullivany/ramses",
    #     json={
    #         "query": """{ gaugeEntities (skip: 0, first: 1000) { id pair { id symbol reserve0 reserve1 totalSupply token0 { id symbol } token1 { id symbol } } rewardTokens { token { id symbol decimals } } } }"""
    #     }
    # )
    #
    # gauge_response_2 = requests.post(
    #     url="https://api.thegraph.com/subgraphs/name/sullivany/ramses",
    #     json={
    #         "query": """{ gaugeEntities (skip: 1000, first: 1000) { id pair { id symbol reserve0 reserve1 totalSupply token0 { id symbol } token1 { id symbol } } rewardTokens { token { id symbol decimals } } } }"""
    #     }
    # )

    gauges = []
    for pair in pairs:
        if not pair['gauge']:
            continue
        gauges.append({
            'id': pair['gauge']['id'],
            'pair': {
                'id': pair['id'],
                'symbol': pair['symbol'],
                'reserve0': float(pair['reserve0']) / 10 ** float(tokens[pair['token0']]['decimals']),
                'reserve1': float(pair['reserve1']) / 10 ** float(tokens[pair['token1']]['decimals']),
                'totalSupply': float(pair['totalSupply']) / 1e18,
                'token0': {
                    'id': pair['token0'],
                    'symbol': tokens[pair['token0']]['symbol']
                },
                'token1': {
                    'id': pair['token1'],
                    'symbol': tokens[pair['token1']]['symbol']
                },
            },
            'rewardTokens': [
                {
                    'token': {
                        'id': token_address,
                        'symbol': tokens[token_address]['symbol'],
                        'decimals': tokens[token_address]['decimals'],
                    }
                } for token_address in pair['gauge']['rewardTokens']
            ]

        })

    bribes = []
    for pair in pairs:
        if not pair['feeDistributor']:
            continue
        bribes.append({
            'id': pair['feeDistributor']['id'],
            'pair': {
                'id': pair['id'],
                'symbol': pair['symbol'],
                'reserve0': float(pair['reserve0']) / 10 ** float(tokens[pair['token0']]['decimals']),
                'reserve1': float(pair['reserve1']) / 10 ** float(tokens[pair['token1']]['decimals']),
                'totalSupply': float(pair['totalSupply']) / 1e18,
                'token0': {
                    'id': pair['token0'],
                    'symbol': tokens[pair['token0']]['symbol']
                },
                'token1': {
                    'id': pair['token1'],
                    'symbol': tokens[pair['token1']]['symbol']
                },
            },
            'bribeTokens': [
                {
                    'token': {
                        'id': token_address,
                        'symbol': tokens[token_address]['symbol'],
                        'decimals': tokens[token_address]['decimals'],
                    }
                } for token_address in pair['feeDistributor']['rewardTokens']
            ]

        })

    data = {
        'gaugeEntities': gauges,
        'bribeEntities': bribes
    }

    return data


def _fetch_pairs(catch_errors):
    subgraph_data = get_subgraph_data(catch_errors)
    fee_distributors = subgraph_data['bribeEntities']
    gauges = subgraph_data['gaugeEntities']

    week = 7 * 24 * 60 * 60
    now = datetime.datetime.now().timestamp()
    period = int(now // week * week + week)

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
                ["derivedSupply()(uint256)"],
                [[pair_address, lambda v: v[0]]]
            ),
        )

        if pair_address not in pairs:
            pairs[pair_address] = {
                'pair_address': pair_address,
                'symbol': gauge['pair']['symbol'],
                'totalSupply': float(gauge['pair']['totalSupply']),
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

        if 'RAM' not in [token['token']['symbol'] for token in fee_distributor['bribeTokens']]:
            fee_distributor['bribeTokens'].append({
                'token': {
                    'id': '0xaaa6c1e32c55a7bfa8066a6fae9b42650f262418',
                    'symbol': 'RAM',
                    'decimals': 18
                }
            })

        if fee_distributor_address == '0x1568d05b8fd251d17687c395db5aa8adbe384e77':
            fee_distributor['bribeTokens'].append({
                'token': {
                    'id': '0x18c11FD286C5EC11c3b683Caa813B77f5163A122',
                    'symbol': 'GNS',
                    'decimals': 18
                }
            })

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
    period_finish_calls = []
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

            period_finish_calls.append(
                Call(
                    w3,
                    gauge_address,
                    ["periodFinish(address)(uint256)", token_address],
                    [[key, lambda v: int(v[0])]]
                ),
            )

            gauge_tokens[key] = {
                'type': 'gt',
                'address': token_address,
                'symbol': token['symbol'],
                'rewardPerToken': 0,
                'decimals': int(token['decimals']),
                'periodFinish': 0
            }

    period_finish = Multicall(w3, period_finish_calls)()
    for key, value in Multicall(w3, calls)().items():
        gauge_tokens[key]['rewardRate'] = value
        gauge_tokens[key]['periodFinish'] = period_finish[key]

    tokens = fee_distributor_tokens.copy()
    tokens.update(gauge_tokens)
    symbols = [token['symbol'] for token in tokens.values()]
    symbols += [pair['token0']['symbol'] for pair in pairs.values()]
    symbols += [pair['token1']['symbol'] for pair in pairs.values()]

    symbols = list(set(symbols))

    try:
        prices = get_prices_from_coingecko(symbols)
        # db.set('v2_prices', json.dumps(prices))
    except Exception as e:
        if not catch_errors:
            raise e
        log("Error on prices")
        # prices = json.loads(db.get('v2_prices'))

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
                if token['periodFinish'] > now:
                    totalUSD += token['rewardRate'] * 24 * 60 * 60 / 10 ** token['decimals'] * token['price']

            pair['total_lp_reward_usd'] = totalUSD
            pair['lp_apr'] = totalUSD * 36500 / (pair['gaugeTotalSupply'] * pair['price'] / 1e18) / 2.5

    return pairs


def get_pairs(catch_errors=True):
    try:
        pairs = _fetch_pairs(catch_errors)
        db.set('pairs', json.dumps(pairs))
    except Exception as e:
        if not catch_errors:
            raise e
        log("Error on get_pairs")
        pairs = json.loads(db.get('pairs'))
    return pairs


if __name__ == '__main__':
    p = _fetch_pairs(False)
    pair = p['0x8ac36fbce743b632d228f9c2ea5e3bb8603141c7'.lower()]
    pprint(pair['gauge_tokens'])
    print(pair['lp_apr'])
