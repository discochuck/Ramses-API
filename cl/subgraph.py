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

        try:
            response = requests.post(
                url=cl_subgraph_url,
                json={
                    "query": query
                }, timeout=15
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
        except requests.exceptions.Timeout:
            if debug:
                print("Timeout")
            log("Timeout in cl_subgraph_tokens")
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
        query = f"""
                {{pools(skip: {skip}, limit: {limit}) {{
                        id 
                        token0 
                            {{
                                id 
                                symbol
                                decimals
                                tokenDayData(first:7 orderBy:date orderDirection:desc){{
                                    date
                                    priceUSD
                                }}
                            }} 
                        token1 
                            {{
                                id 
                                symbol
                                decimals
                                tokenDayData(first:7 orderBy:date orderDirection:desc){{
                                    date
                                    priceUSD
                                }}
                            }} 
                        feeTier 
                        liquidity 
                        sqrtPrice
                        tick 
                        totalValueLockedUSD 
                        totalValueLockedToken0 
                        totalValueLockedToken1 
                        gauge {{
                            id 
                            rewardTokens 
                            isAlive
                        }} 
                        feeDistributor {{
                            id 
                            rewardTokens
                        }}
                        poolDayData(first:7 orderBy:date orderDirection:desc){{  
                            date
                            feesUSD
                            tvlUSD
                            liquidity
                            high
                            low
                            volumeToken0
                            volumeToken1
                        }}
                    }}
                }}
                """

        try:
            response = requests.post(
                url=cl_subgraph_url,
                json={
                    "query": query
                }, timeout=15
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
        except requests.exceptions.Timeout:
            if debug:
                print("Timeout")
            log("Timeout in cl_subgraph_pools")
            return json.loads(db.get('cl_subgraph_pools'))

    # cache pairs
    db.set('cl_subgraph_pools', json.dumps(pools))

    return pools
