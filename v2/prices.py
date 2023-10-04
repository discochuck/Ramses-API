import json
import os
import pathlib

import requests

from utils import db

constant_prices = {
    'slsd': 1.00,
    'fba': 0.5691,
    'bdei': 0.00,
    'smartai': 0.00,
    'test': 0.00,
    'flyshares': 0.00,
    'liveram': 0.00,
    'ttk': 0.00,
    'teth': 0.00,
    'tusdc': 0.00,
    'aaa': 0.00,
    'nfte' : 0.00001
}

coingecko_coins = {
    'ring': 'onering',
    'dei': 'dei-token',
    'mim': 'magic-internet-money',
    'shrp': 'xshrap'
}

defillama_coins = {
    'swETH': 'ethereum:0xf951e335afb289353dc249e82926178eac7ded78',
    'OATH': 'arbitrum:0x00e1724885473b63bce08a9f0a52f35b0979e35a',
    'DAO': 'ethereum:0x0f51bb10119727a7e5eA3538074fb341F56B09Ad',
    'DEUS': 'arbitrum:0xDE5ed76E7c05eC5e4572CfC88d1ACEA165109E44',
    'FTM': 'fantom:0x21be370D5312f44cB42ce377BC9b8a0cEF1A4C83',
    'PLAY': 'bsc:0xd069599e718f963bd84502b49ba8f8657faf5b3a',
    'UNIDX': 'ethereum:0x95b3497bbcccc46a8f45f5cf54b0878b39f8d96c',
    'ankrETH': 'ethereum:0xe95a203b1a91a908f9b9ce46459d101078c2c3cb',
    'cbETH': 'ethereum:0xbe9895146f7af43049ca1c1ae358b0541ea49704',
    'jEUR': 'ethereum:0x0f17bc9a994b87b5225cfb6a2cd4d667adb4f20b',
    'QI': 'polygon:0x580a84c73811e1839f75d86d75d88cca0c241ff4',
    'OHM': 'ethereum:0x64aa3364F17a4D01c6f1751Fd97C2BD3D7e7f1D5',
    'gOHM': 'arbitrum:0x8D9bA570D6cb60C7e3e0F31343Efe75AB8E65FB1',
    'gDAI': 'arbitrum:0xd85E038593d7A098614721EaE955EC2022B9B91B',
    'GRAIN': 'optimism:0xfD389Dc9533717239856190F42475d3f263a270d',
    'plsRDNT': 'arbitrum:0x1605bbdab3b38d10fa23a7ed0d0e8f4fea5bff59',
    'ARB': 'arbitrum:0x912CE59144191C1204E64559FE8253a0e49E6548',
    'sfrxETH': 'arbitrum:0x95aB45875cFFdba1E5f451B950bC2E42c0053f39',
    'YFX': 'arbitrum:0xaaE0c3856e665ff9b3E2872B6D75939D810b7E40',
    'GMD': 'arbitrum:0x4945970EfeEc98D393b4b979b9bE265A3aE28A8B',
    'RAM': 'arbitrum:0xAAA6C1E32C55A7Bfa8066A6FAE9b42650F262418',
    'VELA': 'arbitrum:0x088cd8f5eF3652623c22D48b1605DCfE860Cd704',
    'ARKEN': 'arbitrum:0xAf5db6E1CC585ca312E8c8F7c499033590cf5C98',
    'MAGIC': 'arbitrum:0x539bdE0d7Dbd336b79148AA742883198BBF60342',
    'BIFI': 'optimism:0x4E720DD3Ac5CFe1e1fbDE4935f386Bb1C66F4642',
    'DMT': 'arbitrum:0x8B0E6f19Ee57089F7649A455D89D7bC6314D04e8',
    'GND': 'arbitrum:0xD67A097dCE9d4474737e6871684aE3c05460F571',
    'GNS': 'arbitrum:0x18c11FD286C5EC11c3b683Caa813B77f5163A122',
    'agEUR': 'ethereum:0x1a7e4e63778B4f12a199C062f3eFdD288afCBce8',
    'sCANTO': 'canto:0x9F823D534954Fc119E31257b3dDBa0Db9E2Ff4ed',
    'neadRAM': 'arbitrum:0x40301951Af3f80b8C1744ca77E55111dd3c1dba1',
    'EUROe': 'ethereum:0x820802Fa8a99901F52e39acD21177b0BE6EE2974',
    'fBOMB': 'optimism:0x74ccbe53F77b08632ce0CB91D3A545bF6B8E0979',
    'ANKR': 'bsc:0xf307910A4c7bbc79691fD374889b36d8531B08e3',
    'Lqdr': 'arbitrum:0x816E21c33fa5F8440EBcDF6e01D39314541BEA72',
    'SPA': '0x5575552988A3A80504bBaeB1311674fCFd40aD4B',
    'LDO': 'arbitrum:0x13Ad51ed4F1B7e9Dc168d8a00cB3f4dDD85EfA60',
    'TAROT': 'base:0xF544251D25f3d243A36B07e7E7962a678f952691',
    'FXS': 'ethereum:0x3432b6a60d23ca0dfca7761b7ab56459d9c964d0',

    'DAI': 'arbitrum:0xda10009cbd5d07dd0cecc66161fc93d7c9000da1',
    'LUSD': 'arbitrum:0x93b346b6BC2548dA6A1E7d98E9a421B42541425b',
    'stERN': 'arbitrum:0xf7a0dd3317535ec4f4d29adf9d620b3d8d5d5069',
    'alUSD': 'optimism:0xCB8FA9a76b8e203D8C3797bF438d8FB81Ea3326A',
    'GRAI': 'arbitrum:0x894134a25a5faC1c2C26F1d8fBf05111a3CB9487',
    'USDC.e': 'arbitrum:0xff970a61a04b1ca14834a43f5de4533ebddb5cc8',
    'USDC': 'arbitrum:0xaf88d065e77c8cc2239327c5edb3a432268e5831',
    'FRAX': 'arbitrum:0x17fc002b466eec40dae837fc4be5c67993ddbd6f',
    'USDT': 'arbitrum:0xfd086bc7cd5c481dcc9c85ebe478a1c0b69fcbb9',
    'MAI': 'arbitrum:0x3F56e0c36d275367b8C502090EDF38289b3dEa0d',
    'USD+': 'arbitrum:0xe80772eaf6e2e18b651f160bc9158b2a5cafca65',
    'DAI+': 'arbitrum:0xeb8e93a0c7504bffd8a8ffa56cd754c63aaebfe8',
    'STAR': 'arbitrum:0xC19669A405067927865B40Ea045a2baabbbe57f5',
    'USDs': 'arbitrum:0xD74f5255D557944cf7Dd0E45FF521520002D5748',
    'DUSD': 'arbitrum:0x8EC1877698ACF262Fe8Ad8a295ad94D6ea258988',
    'axlUSDC': 'arbitrum:0xEB466342C4d449BC9f53A865D5Cb90586f405215'

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
    # try:
    #     coingecko_prices = get_prices_from_coingecko([
    #         token['symbol'] for token in tokens if prices[token['symbol']] == 0
    #     ])
    #     prices.update(coingecko_prices)
    # except Exception as e:
    #     exception_happened = True
    #     if debug:
    #         raise e
    #     print("Error in coingecko")

    # set neadRAM price
    prices['xRAM'] = prices['RAM']
    prices['ELR'] = prices['RAM'] * 1.06

    # if any exception happened in defillama or coingecko and token price is zero use previous price for the token
    if exception_happened:
        for token in tokens:
            symbol = token['symbol']
            if prices[symbol] == 0:
                prices[symbol] = token['price']

    print("missing prices", [k for k in prices.keys() if prices[k] == 0])

    return prices


if __name__ == '__main__':
    get_prices(json.loads(db.get('v2_subgraph_tokens')), debug=True)
    # pprint(get_prices(json.loads(db.get('v2_subgraph_tokens'))))
