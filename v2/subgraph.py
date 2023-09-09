import json
import time

import requests

from utils import log, db
from v2.prices import get_prices
import math


v2_subgraph_url = "https://api.thegraph.com/subgraphs/name/ramsesexchange/api-subgraph"
backup_v2_subgraph_url = "http://146.190.190.51:8000/subgraphs/name/ramsesexchange/api-subgraph"
urls = [v2_subgraph_url, backup_v2_subgraph_url]
sulli_analytics_subgraph_url = "https://api.thegraph.com/subgraphs/name/sullivany/ramses-analytics"
v2_analytics_subgraph_url = "https://api.thegraph.com/subgraphs/name/ramsesexchange/analytics-subgraph"
backup_v2_analytics_subgraph_url = "https://146.190.190.51:8000/subgraphs/name/ramsesexchange/analytics-subgraph"
analytics_urls = [sulli_analytics_subgraph_url, v2_analytics_subgraph_url, backup_v2_analytics_subgraph_url]


def get_subgraph_tokens(debug):
    # return json.loads(db.get('v2_subgraph_tokens'))
    # get tokens from subgraph
    skip = 0
    limit = 100
    tokens = []
    while True:
        query = f"{{ tokens(skip: {skip}, limit: {limit}) {{ id name symbol decimals whitelisted}} }}"
        try:
            response = try_subgraph(urls, query)

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
        except requests.exceptions.Timeout:
            if debug:
                print("Timeout")
            log("Timeout in v2_subgraph_tokens")
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
        query = f"""
            {{ 
                pairs(skip: {skip}, limit: {limit}) 
                    {{ 
                        id 
                        symbol 
                        totalSupply 
                        isStable 
                        token0 
                        reserve0 
                        token1 
                        reserve1 
                        gauge 
                            {{ 
                                id 
                                totalDerivedSupply 
                                rewardTokens 
                                isAlive
                                xRamRatio
                            }} 
                        feeDistributor 
                            {{ 
                                id 
                                rewardTokens 
                            }} 
                    }} 
            }}
            """
        try:
            response = try_subgraph(urls, query)

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
        except requests.exceptions.Timeout:
            if debug:
                print("Timeout")
            log("Timeout in v2_subgraph_pairs")
            return json.loads(db.get('v2_subgraph_pairs'))

    # cache pairs
    db.set('v2_subgraph_pairs', json.dumps(pairs))

    return pairs


def get_subgraph_pair_day_data(pair_count=100, debug=False):
    # get pair day data from subgraph
    data_count_limit = pair_count * 7  # 7 days per pool
    cutoff = math.floor(time.time() - 86400 * 7)
    skip = 0
    limit = 100
    raw_pair_day_data = []
    while True:
        query = f"""
                    {{ pairDayDatas(
                            skip: {skip}, 
                            limit: {limit}, 
                            where: {{ 
                                date_gt: {cutoff} 
                            }}, 
                            orderBy: 
                                date, 
                            orderDirection: 
                                desc
                        ) 
                            {{  
                                pairAddress
                                date
                                dailyVolumeToken0
                                dailyVolumeToken1
                            }} 
                    }}
                """
        try:
            response = try_subgraph(analytics_urls, query, 5)

            if response.status_code == 200:
                new_pair_day_data = response.json()['data']['pairDayDatas']
                raw_pair_day_data += new_pair_day_data

                if len(new_pair_day_data) < limit or len(raw_pair_day_data) >= data_count_limit:
                    break
                else:
                    skip += limit
            else:
                if debug:
                    print(response.text)
                log("Error in subgraph pairs day data")
                return json.loads(db.get('v2_subgraph_pair_day_data'))
        except requests.exceptions.Timeout:
            if debug:
                print("Timeout")
            log("Timeout in v2_subgraph_pair_day_data")
            return json.loads(db.get('v2_subgraph_pair_day_data'))

    pair_day_data = {}

    # format data into pools
    for data in raw_pair_day_data:
        if data['pairAddress'] not in pair_day_data:
            pair_day_data[data['pairAddress']] = []
        pair_day_data[data['pairAddress']].append(data)

    # cache pairs
    db.set('v2_subgraph_pair_day_data', json.dumps(pair_day_data))

    return pair_day_data


def try_subgraph(urls, query, timeout=15):

    response = {}

    for i in range(len(urls)):
        try:
            response = requests.post(
                urls[i],
                json={
                    "query": query
                }, timeout=timeout)
        except Exception as e:
            log(f"Error in {urls[i]}")
            log(e)
            continue

        if (response.status_code == 200):
            return response

    return response