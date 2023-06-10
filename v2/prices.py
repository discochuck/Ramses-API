import json
import os
import pathlib
from pprint import pprint

import requests

from utils import db

constant_prices = {
    'usd+': 1,
    'dai+': 1,
    'ets epsilon': 1,
    'mai': 1,
    'usdc': 1,
    'usdt': 1,
    'dai': 1,
    'frax': 1,
    'usdc.e': 1,
    'elr': 0.03,
    'xpork': 0.000005400,
    'bath': 0.0005189,
    'uwu': 1.05,

    # TODO: FILTER THESE TOKENS OUT

    'smartai': 0,
    'test': 0,
    'flyshares': 0,
    'liveram': 0,
    'ttk': 0,
    'teth': 0,
    'tusdc': 0,
    'aaa': 0
}

coingecko_coins = {
    'dao': 'dao-maker',
    'gmd': 'gmd-protocol',
    'yfx': 'yieldfarming-index',
    'bifi': 'beefy-finance',
    'magic': 'magic',
    'ram': 'ramses-exchange',
    'fbomb': 'fantom-bomb',
    'fs': 'fantomstarter',
    'arc': 'arcadeum',
    'arb': 'arbitrum',
    'hop': 'hop-protocol',
    'spa': 'sperax',
    'ldo': 'lido-dao',
    'ring': 'onering',
    'gns': 'gains-network',
    'wusdr': 'wrapped-usdr',
    'sfrxeth': 'staked-frax-ether',
    'grain': 'granary',
    'ageur': 'ageur',
    'euroe': 'euroe-stablecoin',
    'gnd': 'gnd-protocol',
    'pork': 'pigscanfly',
    'aidoge': 'arbdoge-ai',
    'aicode': 'ai-code',
    'vela': 'vela-token',
    'dei': 'dei-token',
    'lusd': 'liquity-usd',
    'usds': 'sperax-usd',
    'mim': 'magic-internet-money',
    'unsheth': 'unsheth-unsheth',
    'ankr': 'ankr-network',
    'arken': 'arken-finance'
}

defillama_coins = {
    'DAO': 'ethereum:0x0f51bb10119727a7e5eA3538074fb341F56B09Ad',
    'DEUS': 'fantom:0xde5ed76e7c05ec5e4572cfc88d1acea165109e44',
    'FBA': 'fantom:0x0e249130b3545a2a287de9f27d805cab95f03db9',
    'FTM': 'fantom:0x21be370D5312f44cB42ce377BC9b8a0cEF1A4C83',
    'PLAY': 'bsc:0xd069599e718f963bd84502b49ba8f8657faf5b3a',
    'UNIDX': 'ethereum:0x95b3497bbcccc46a8f45f5cf54b0878b39f8d96c',
    'ankrETH': 'ethereum:0xe95a203b1a91a908f9b9ce46459d101078c2c3cb',
    'cbETH': 'ethereum:0xbe9895146f7af43049ca1c1ae358b0541ea49704',
    'jEUR': 'ethereum:0x0f17bc9a994b87b5225cfb6a2cd4d667adb4f20b',
    'QI': 'polygon:0x580a84c73811e1839f75d86d75d88cca0c241ff4',
    'BATH': 'arbitrum:0xe5b8C3381C0A2544883CfF9dDaf1e48D9dea9E49',
    'OHM': 'arbitrum:0xf0cb2dc0db5e6c66B9a70Ac27B06b878da017028',
    'gOHM': 'arbitrum:0x8D9bA570D6cb60C7e3e0F31343Efe75AB8E65FB1'
}


def get_prices_from_coingecko(symbols):
    def get_coins_ids(symbols_):
        with open(os.path.join(str(pathlib.Path(__file__).parent), '../coingecko_coins.json'), encoding="utf8") as file:
            coins = json.loads(file.read())

        ids = {}
        for symbol in symbols_:
            symbol = symbol.lower()

            if symbol in coingecko_coins:
                ids[symbol] = coingecko_coins[symbol]
            else:
                coin = [coin['id'] for coin in coins if coin['symbol'] == symbol]
                if len(coin) == 1:
                    ids[symbol] = coin[0]
                else:
                    ids[symbol] = None

        return ids

    prices = {}

    ids = get_coins_ids(symbols)

    ids_array = list([v for v in ids.values() if v]) + ['ethereum', 'ramses-exchange']

    response = requests.get(
        url="https://pro-api.coingecko.com/api/v3/simple/price",
        params={
            'ids': ','.join(ids_array),
            'vs_currencies': 'usd',
            'x_cg_pro_api_key': 'CG-AyFXDTk59MkkPukojFceCjTo'
        }
    ).json()

    for symbol in symbols:
        if symbol.lower() in response:
            prices[symbol] = response[ids[symbol.lower()]]['usd']

    prices['ETH'] = response['ethereum']['usd']
    prices['RAM'] = response['ramses-exchange']['usd']

    return prices


def get_prices_from_defillama(tokens):
    queries = {}
    prices = {}
    for token in tokens:
        queries[token['symbol']] = defillama_coins.get(token['symbol'], f"arbitrum:{token['id']}")

    response = requests.get(
        url=f"https://coins.llama.fi/prices/current/{','.join(queries.values())}",
    ).json()['coins']

    for symbol, query in queries.items():
        if query in response:
            prices[symbol] = response[query]['price']

    return prices


def get_prices(tokens, debug=False):
    prices = {}

    symbols = [token['symbol'] for token in tokens]

    # set constant prices
    for symbol in symbols:
        if symbol.lower() in constant_prices.keys():
            prices[symbol] = constant_prices[symbol.lower()]
        else:
            prices[symbol] = 0

    exception_happened = False

    # fetch zero prices from defillama
    try:
        defillama_prices = get_prices_from_defillama([
            token for token in tokens if prices[token['symbol']] == 0
        ])
        prices.update(defillama_prices)
    except Exception as e:
        exception_happened = True
        if debug:
            raise e
        print("Error in defillama")

    # fetch prices from coingecko
    try:
        coingecko_prices = get_prices_from_coingecko([
            token['symbol'] for token in tokens if prices[token['symbol']] == 0
        ])
        prices.update(coingecko_prices)
    except Exception as e:
        exception_happened = True
        if debug:
            raise e
        print("Error in coingecko")

    # set neadRAM price
    prices['neadRAM'] = prices['RAM'] * 0.9

    # if any exception happened in defillama or coingecko and token price is zero use previous price for the token
    if exception_happened:
        for token in tokens:
            symbol = token['symbol']
            if prices[symbol] == 0:
                prices[symbol] = token['price']

    print("missing prices", [k for k in prices.keys() if prices[k] == 0])

    return prices


if __name__ == '__main__':
    get_prices(json.loads(db.get('v2_subgraph_tokens')), debug=False)
    # pprint(get_prices(json.loads(db.get('v2_subgraph_tokens'))))
