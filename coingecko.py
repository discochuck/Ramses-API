import json
import os
import pathlib
from pprint import pprint

import requests

local_coin_ids = {
    'dao': 'dao-maker',
    'gmd': 'gmd-protocol',
    'yfx': 'yieldfarming-index',
    'bifi': 'beefy-finance',
    'magic': 'magic',
    'ram': 'ramses-exchange',
    'fbomb': 'fantom-bomb',
    'fs': 'fantomstarter',
    'arc': 'arcadeum',
    'qi': 'qi-dao',
    'arb': 'arbitrum',
    'hop': 'hop-protocol',
    'spa': 'sperax',
    'ldo': 'lido-dao',
    'ring': 'onering',
    'gns': 'gains-network',
    'cbeth': 'coinbase-wrapped-staked-eth',
    'wusdr': 'wrapped-usdr',
    'sfrxeth': 'staked-frax-ether',
    'grain': 'granary',
    'ageur': 'ageur',
    'fba': 'firebird-aggregator',
    'euroe': 'euroe-stablecoin',
    'gnd': 'gnd-protocol',
    'pork': 'pigscanfly',
    'aidoge': 'arbdoge-ai',
    'aicode': 'ai-code',
    'play': 'xcad-network-play',
    'vela': 'vela-token',
    'ohm': 'olympus',
    'dei': 'dei-token',
    'lusd': 'liquity-usd',
    'usdc': 'usd-coin',
    'usdt': 'tether',
    'mai': 'mai',
    'dai': 'dai',
    'usds': 'sperax-usd',
    'mim': 'magic-internet-money',
    'frax': 'frax',
    'unsheth': 'unsheth-unsheth',
    'neadram': 'the-ennead'
    'ankr': 'ankr-network',
    'ankreth': 'ankr-staked-eth'
}

stable_coins = [
    'usd+',
    'dai+',
    'ets epsilon',
]

constant_prices = {
    'elr': 0.043,
    'xpork': 0.00001308,
    'gmusd': 1.05,
    'gmdusdc': 1.07,
    'smartai': 0,
    'flyshares': 0,
    'bbb': 0,
    'tusdc': 0,
    'teth': 0,
    'liveram': 0,
    'test': 0
}


def get_coins_ids(symbols):
    with open(os.path.join(str(pathlib.Path(__file__).parent), './coingecko_coins.json'), encoding="utf8") as file:
        coins = json.loads(file.read())

    ids = {}
    for symbol in symbols:
        symbol = symbol.lower()

        if symbol in local_coin_ids:
            ids[symbol] = local_coin_ids[symbol]
        else:
            coin = [coin['id'] for coin in coins if coin['symbol'] == symbol]
            if len(coin) == 1:
                ids[symbol] = coin[0]
            else:
                ids[symbol] = None
                print(f"{symbol} not found in coingecko or found more than one")

    return ids


def get_prices(symbols):
    prices = {}

    symbols_ = []
    for symbol in symbols:
        if symbol.lower() in stable_coins:
            prices[symbol] = 1
        elif symbol.lower() in constant_prices.keys():
            prices[symbol] = constant_prices[symbol.lower()]
        else:
            symbols_.append(symbol)

    symbols = symbols_

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
        prices[symbol] = response.get(ids[symbol.lower()], {'usd': 0})['usd']

    prices['ETH'] = response['ethereum']['usd']
    prices['RAM'] = response['ramses-exchange']['usd']

    return prices


if __name__ == '__main__':
    pprint(
        get_prices(
            ['neadRAM', 'TEST', 'DAO', 'WETH', 'TAROT', 'wstETH', 'LQTY', 'OATH', 'UNIDX', 'gmUSD', 'VELA', 'MIM', 'MAGIC', 'YFX', 'DOLA', 'LEVI', 'LUSD',
             'FRAX', 'L2DAO',
             'DAI',
             'GMX', 'xSHRAP', 'GNS', 'BIFI', 'jEUR', 'MAI', 'DAI+', 'USDT', 'ELR', 'gDAI', 'USD+', 'DEI', 'RAM', 'DEUS', 'LQDR', 'NFTE', 'frxETH', 'fBOMB',
             'GMD', 'FXS', 'XCAD', 'USDC']
        )
    )
