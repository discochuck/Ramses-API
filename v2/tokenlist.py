import json

import requests

from utils import log, db
from v2.subgraph import get_subgraph_tokens


def get_tokenlist(debug):
    tokens_array = get_subgraph_tokens(debug)

    # reformat tokens and pairs
    # + filter out pairs without gauge
    tokens = []
    for _token in tokens_array:
        # print(_token['symbol'])
        # print(_token['whitelisted'])
        if _token['whitelisted']:
            token = {}

            token['chainId'] = int(42161)
            token['address'] = _token['id']
            token['name'] = _token['name']
            token['symbol'] = _token['symbol']
            token['decimals'] = int(_token['decimals'])

            tokens.append(token)

    tokenlist = {}
    with open('v2/constants/tokenlist.json', 'r') as file:
        tokenlist = json.load(file)

    tokenlist['tokens'] = tokens

    return tokenlist


def get_logos_from_defillama(tokens):
    queries = {}
    prices = {}
    for token in tokens:
        queries[token['symbol']] = f"arbitrum:{token['address']}"

    response = requests.get(
        url=f"https://coins.llama.fi/prices/current/{','.join(queries.values())}",
    ).json()['coins']

    for symbol, query in queries.items():
        if query in response:
            prices[symbol] = response[query]['price']

    return prices
