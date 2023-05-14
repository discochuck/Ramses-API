import datetime
import json
from pprint import pprint

import requests

from coingecko import get_prices
from multicall import Multicall, Call
from utils import w3, db, log, RAM_ADDRESS


def get_subgraph_tokens(debug):
    # return json.loads(db.get('v2_tokens'))
    # get tokens from subgraph
    skip = 0
    limit = 100
    tokens = []
    while True:
        query = f"{{ tokens(skip: {skip}, limit: {limit}) {{ id name symbol decimals }} }}"
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
            if debug: print(response.text)
            log("Error in subgraph tokens")
            return json.loads(db.get('v2_tokens'))

    # get tokens prices
    symbols = list(set([token['symbol'] for token in tokens]))
    try:
        prices = get_prices(symbols)
        db.set('v2_prices', json.dumps(prices))
    except Exception as e:
        if debug: raise e
        log("Error on prices")
        prices = json.loads(db.get('v2_prices'))
    for token in tokens:
        token['price'] = prices[token['symbol']]

    # cache tokens
    db.set('v2_tokens', json.dumps(tokens))

    return tokens


def get_subgraph_pairs(debug):
    # return json.loads(db.get('v2_pairs'))
    # get pairs from subgraph
    skip = 0
    limit = 100
    pairs = []
    while True:
        query = f"{{ pairs(skip: {skip}, limit: {limit}) {{ id symbol totalSupply isStable token0 reserve0 token1 reserve1 gauge {{ id totalDerivedSupply rewardTokens isAlive }} feeDistributor {{ id rewardTokens }} }} }}"
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
            if debug: print(response.text)
            log("Error in subgraph pairs")
            return json.loads(db.get('v2_pairs'))

    # cache pairs
    db.set('v2_pairs', json.dumps(pairs))

    return pairs


def _fetch_pairs(debug):
    # set constants
    week = 7 * 24 * 60 * 60
    now = datetime.datetime.now().timestamp()
    period = int(now // week * week + week)

    # fetch tokens and pairs from subgraph
    tokens_array = get_subgraph_tokens(debug)
    pairs_array = get_subgraph_pairs(debug)

    # reformat tokens and pairs
    # + filter out pairs without gauge
    tokens = {}
    for token in tokens_array:
        token['price'] = float(token['price'])
        token['decimals'] = int(token['decimals'])
        tokens[token['id']] = token
    pairs = {}
    for pair in pairs_array:
        if pair['gauge']:
            pair['voteBribes'] = {}
            pair['totalVeShareByPeriod'] = 0
            pair['reserve0'] = int(pair['reserve0'])
            pair['reserve1'] = int(pair['reserve1'])
            pair['totalSupply'] = int(pair['totalSupply'])
            pair['gauge']['totalDerivedSupply'] = int(pair['gauge']['totalDerivedSupply'])
            pairs[pair['id']] = pair

    # set pair TVL
    _pairs_price = {}
    for pair_address, pair in pairs.items():
        pair['tvl'] = pair['reserve0'] * tokens[pair['token0']]['price'] / 10 ** tokens[pair['token0']]['decimals'] \
                      + pair['reserve1'] * tokens[pair['token1']]['price'] / 10 ** tokens[pair['token1']]['decimals']
        if pair['totalSupply'] > 0:
            _pairs_price[pair_address] = pair['tvl'] * 1e18 / pair['totalSupply']
        else:
            _pairs_price[pair_address] = 0

    # fetch pair's vote share
    calls = []
    for pair_address, pair in pairs.items():
        fee_distributor_address = pair['feeDistributor']['id']
        calls.append(
            Call(
                w3,
                fee_distributor_address,
                ["totalVeShareByPeriod(uint256)(uint256)", period],
                [[pair_address, lambda v: v[0]]]
            )
        )
    for pair_address, value in Multicall(w3, calls)().items():
        pairs[pair_address]['totalVeShareByPeriod'] += value

    # fetch pair's vote bribes
    calls = []
    for pair_address, pair in pairs.items():
        fee_distributor_address = pair['feeDistributor']['id']
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
    for key, value in Multicall(w3, calls)().items():
        pair_address, token_address = key.split('-')
        if value > 0:
            pairs[pair_address]['voteBribes'][token_address] = value

    # fetch pair's lp reward rates
    _reward_rates = {}
    calls = []
    for pair_address, pair in pairs.items():
        _reward_rates[pair_address] = {}
        for token_address in pair['gauge']['rewardTokens']:
            _reward_rates[token_address] = 0
            key = f'{pair_address}-{token_address}'

            calls.append(
                Call(
                    w3,
                    pair['gauge']['id'],
                    ["rewardRate(address)(uint256)", token_address],
                    [[key, lambda v: v[0]]]
                ),
            )
    for key, value in Multicall(w3, calls)().items():
        pair_address, token_address = key.split('-')
        _reward_rates[pair_address][token_address] = value

    # calculate APRs
    for pair_address, pair in pairs.items():
        # calculate vote APR
        if pair['totalVeShareByPeriod'] > 0:
            totalUSD = 0
            for token_address, amount in pair['voteBribes'].items():
                totalUSD += amount * tokens[token_address]['price'] / 10 ** tokens[token_address]['decimals']
            pair['voteApr'] = totalUSD / 7 * 36500 / (pair['totalVeShareByPeriod'] * tokens[RAM_ADDRESS]['price'] / 1e18)
        else:
            pair['voteApr'] = 0

        # calculate LP APR
        if pair['gauge']['totalDerivedSupply'] > 0:
            totalUSD = 0
            for token_address in pair['gauge']['rewardTokens']:
                totalUSD += _reward_rates[pair_address][token_address] * 24 * 60 * 60 * tokens[token_address]['price'] / 10 ** tokens[token_address]['decimals']
            pair['lpApr'] = totalUSD * 36500 / (pair['gauge']['totalDerivedSupply'] * _pairs_price[pair_address] / 1e18) / 2.5
        else:
            pair['lpApr'] = 0

    # convert floats to strings
    for pair_address, pair in pairs.items():
        for key in pair.keys():
            if isinstance(pair[key], float) or isinstance(pair[key], int):
                pair[key] = "{:.18f}".format(pair[key])

        for token_address, amount in pair['voteBribes'].items():
            pair['voteBribes'][token_address] = "{:.18f}".format(amount)

    return {
        'tokens': list(tokens.values()),
        'pairs': list(pairs.values())
    }


def get_pairs(debug=False):
    try:
        pairs = _fetch_pairs(debug)
        db.set('pairs', json.dumps(pairs))
    except Exception as e:
        if debug: raise e
        log("Error on get_pairs")
        pairs = json.loads(db.get('pairs'))

    return pairs


if __name__ == '__main__':
    p = get_pairs(True)

    pprint(p['pairs'][1])
