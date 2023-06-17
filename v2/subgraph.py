import json

import requests

from utils import log, db
from v2.prices import get_prices


def get_subgraph_tokens(debug):
    # return json.loads(db.get('v2_subgraph_tokens'))
    # get tokens from subgraph
    skip = 0
    limit = 100
    tokens = []
    while True:
        query = f"{{ tokens(skip: {skip}, limit: {limit}) {{ id name symbol decimals whitelisted}} }}"
        response = requests.post(
            url="https://api.thegraph.com/subgraphs/name/ramsesexchange/api-subgraph",
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
            return json.loads(db.get('v2_subgraph_tokens'))

    # get tokens prices
    prices = get_prices(tokens, debug=debug)
    for token in tokens:
        token['price'] = prices[token['symbol']]

    # cache tokens
    db.set('v2_subgraph_tokens', json.dumps(tokens))

    return tokens


def get_subgraph_pairs(debug):
    # get pairs from subgraph
    skip = 0
    limit = 100
    pairs = []
    while True:
        query = f"{{ pairs(skip: {skip}, limit: {limit}) {{ id symbol totalSupply isStable token0 reserve0 token1 reserve1 gauge {{ id totalDerivedSupply rewardTokens isAlive }} feeDistributor {{ id rewardTokens }} }} }}"
        response = requests.post(
            url="https://api.thegraph.com/subgraphs/name/ramsesexchange/api-subgraph",
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
            if debug:
                print(response.text)
            log("Error in subgraph pairs")
            return json.loads(db.get('v2_subgraph_pairs'))

    # cache pairs
    db.set('v2_subgraph_pairs', json.dumps(pairs))

    return pairs
