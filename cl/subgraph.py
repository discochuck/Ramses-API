import json

import requests

from utils import log, db
from v2.prices import get_prices

cl_subgraph_url = "https://api.thegraph.com/subgraphs/name/ramsesexchange/concentrated-liquidity-graph"


def get_cl_subgraph_tokens(debug):
    # get tokens from subgraph
    skip = 0
    limit = 100
    tokens = []
    while True:
        query = f"{{ tokens(skip: {skip}, limit: {limit}) {{ id name symbol decimals }} }}"
        response = requests.post(
            url=cl_subgraph_url,
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
            if debug:
                print(response.text)
            log("Error in subgraph tokens")
            return json.loads(db.get('cl_subgraph_tokens'))

    # get tokens prices
    prices = get_prices(tokens, debug=debug)
    for token in tokens:
        token['price'] = prices[token['symbol']]

    # cache tokens
    db.set('cl_subgraph_tokens', json.dumps(tokens))

    return tokens


def get_cl_subgraph_pools(debug):
    # get pairs from subgraph
    skip = 0
    limit = 100
    pools = []
    while True:
        query = f"{{ pools(skip: {skip}, limit: {limit}) {{ id token0 {{id symbol}} token1 {{id symbol}} feeTier liquidity sqrtPrice token0Price token1Price tick totalValueLockedUSD totalValueLockedToken0 totalValueLockedToken1 gauge {{id feeDistributor {{id rewardTokens}} rewardTokens isAlive}}}} }}"
        response = requests.post(
            url=cl_subgraph_url,
            json={
                "query": query
            }
        )

        if response.status_code == 200:
            new_pools = response.json()['data']['pools']
            pools += new_pools

            if len(new_pools) < limit:
                break
            else:
                skip += limit
        else:
            if debug:
                print(response.text)
            log("Error in subgraph pairs")
            return json.loads(db.get('cl_subgraph_pools'))

    # cache pairs
    db.set('cl_subgraph_pools', json.dumps(pools))

    return pools
