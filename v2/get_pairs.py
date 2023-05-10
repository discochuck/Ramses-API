import datetime
import json
from pprint import pprint

import requests

from coingecko import get_prices
from multicall import Multicall, Call
from utils import w3, db, log


def get_subgraph_tokens():
    # get tokens from subgraph
    skip = 0
    limit = 100
    tokens = []
    while True:
        query = f"{{ tokens(skip: {skip}, limit: {limit}) {{ id symbol decimals }} }}"
        response = requests.post(
            url="https://api.thegraph.com/subgraphs/name/sullivany/ramses-v2",
            json={
                "query": query
            }
        )

        if response.status_code == 200:
            new_tokens = response.json()['data']['tokens']
            tokens += new_tokens

            if len(new_tokens) < limit:
                break
            else:
                skip += limit
        else:
            log("Error in subgraph tokens")
            return json.loads(db.get('v2_tokens'))

    # get tokens prices
    symbols = list(set([token['symbol'] for token in tokens]))
    try:
        prices = get_prices(symbols)
        db.set('v2_prices', json.dumps(prices))
    except:
        log("Error on prices")
        prices = json.loads(db.get('v2_prices'))
    for token in tokens:
        token['price'] = prices[token['symbol']]

    # cache tokens
    db.set('v2_tokens', json.dumps(tokens))

    return tokens


def get_subgraph_pairs():
    # get pairs from subgraph
    skip = 0
    limit = 100
    pairs = []
    while True:
        query = f"{{ pairs(skip: {skip}, limit: {limit}) {{ id symbol token0 reserve0 token1 reserve1 gauge {{ id totalDerivedSupply rewardTokens }} feeDistributor {{ id rewardTokens }} }} }}"
        response = requests.post(
            url="https://api.thegraph.com/subgraphs/name/sullivany/ramses-v2",
            json={
                "query": query
            }
        )

        if response.status_code == 200:
            new_pairs = response.json()['data']['pairs']
            pairs += new_pairs

            if len(new_pairs) < limit:
                break
            else:
                skip += limit
        else:
            log("Error in subgraph pairs")
            return json.loads(db.get('v2_pairs'))

    # cache pairs
    db.set('v2_pairs', json.dumps(pairs))

    return pairs


def _fetch_pairs():
    tokens = get_subgraph_tokens()
    pairs = get_subgraph_pairs()

    week = 7 * 24 * 60 * 60
    period = int(datetime.datetime.now().timestamp() // week * week + week)

    pools = {}
    for pair in pairs:
        pools[pair['id']] = pair

    calls = []
    for pair in pairs:
        fee_distributor_address = pair['feeDistributor']['id']
        pair_address = pair['id']

        calls.append(
            Call(
                w3,
                fee_distributor_address,
                ["totalVeShareByPeriod(uint256)(uint256)", period],
                [[pair_address, lambda v: v[0]]]
            )
        )

    for pair_address, value in Multicall(w3, calls)().items():
        pools[pair_address]['feeDistributor']['totalVeShareByPeriod'] += value

    calls = []
    for pair in pairs:
        fee_distributor_address = pair['feeDistributor']['id']
        pair_address = pair['id']
        for token_address in pair['feeDistributor']['rewardTokens']:
            key = f'{pair_address}-{token_address}'

            calls.append(
                Call(
                    w3,
                    fee_distributor_address,
                    ["tokenTotalSupplyByPeriod(uint256,address)(uint256)", period, token_address],
                    [[key, lambda v: v[0]]]
                )
            )

    fee_distributor_tokens = {}
    for key, value in Multicall(w3, calls)().items():
        key = key.split('-')[0]
        fee_distributor_tokens[key]['tokenTotalSupplyByPeriod'] += value

    gauge_tokens = {}
    calls = []
    for gauge in gauges:
        gauge_address = gauge['id']
        pair_address = gauge['pair']['id']
        pools[pair_address]['gauge_address'] = gauge_address
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
    symbols += [pair['token0']['symbol'] for pair in pools.values()]
    symbols += [pair['token1']['symbol'] for pair in pools.values()]

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
            pools[pair_address]['current_vote_bribes'].append(token)
            pools[pair_address]['total_current_vote_bribe_usd'] += token['totalUSD']

    for address, pair in pools.items():
        pair['token0']['price'] = prices[pair['token0']['symbol']]
        pair['token1']['price'] = prices[pair['token1']['symbol']]
        pair['tvl'] = pair['token0']['reserve'] * pair['token0']['price'] + pair['token1']['reserve'] * pair['token1']['price']

        if pair['totalSupply'] > 0:
            pair['price'] = pair['tvl'] / pair['totalSupply']

    for key, token in fee_distributor_tokens.items():
        pair_address = key.split('-')[0]
        pair = pools[pair_address]

        token['price'] = prices[token['symbol']]
        token['totalUSD'] = token['tokenTotalSupplyByPeriod'] / 10 ** token['decimals'] * token['price']
        pair['fee_distributor_tokens'].append(token)

    for key, token in gauge_tokens.items():
        pair_address = key.split('-')[0]
        pair = pools[pair_address]

        token['price'] = prices[token['symbol']]
        pair['gauge_tokens'].append(token)

    for address, pair in pools.items():
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

    for pair_address, pair in pools.items():
        for key in pair.keys():
            if isinstance(pair[key], float):
                pair[key] = "{:.18f}".format(pair[key])

    return pools


def get_pairs():
    try:
        pairs = _fetch_pairs()
        db.set('pairs', json.dumps(pairs))
    except:
        log("Error on get_pairs")
        pairs = json.loads(db.get('pairs'))
    return pairs


if __name__ == '__main__':
    print(
        # get_subgraph_pairs()
        # get_subgraph_tokens()
    )
    # p = _fetch_pairs()
    # pprint(
    #     list(p.values())[0]
    # )
