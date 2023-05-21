import json
import os
import pathlib
from pprint import pprint

import requests

token_addresses = [
    "0x03e8d118a1864c7dc53bf91e007ab7d91f5a06fa",
    "0x088cd8f5ef3652623c22d48b1605dcfe860cd704",
    "0x0c4681e6c0235179ec3d4f4fc4df3d14fdd96017",
    "0x10393c20975cf177a3513071bc110f7962cd67da",
    "0x13aabc0a9a5d6865da8fd0296080e172cf8bb958",
    "0x13ad51ed4f1b7e9dc168d8a00cb3f4ddd85efa60",
    "0x178412e79c25968a32e89b11f63b33f733770c2a",
    "0x17fc002b466eec40dae837fc4be5c67993ddbd6f",
    "0x1819e21698b777b69f903ff5550361cf12ed1def",
    "0x18c11fd286c5ec11c3b683caa813b77f5163a122",
    "0x1a5b0aaf478bf1fda7b934c76e7692d722982a6d",
    "0x1debd73e752beaf79865fd6446b0c970eae7732f",
    "0x1e3c6c53f9f60bf8aae0d7774c21fa6b1afddc57",
    "0x2cab3abfc1670d1a452df502e216a66883cdf079",
    "0x2e041cddf767a452599907ef29ae790ef72c1dc8",
    "0x3082cc23568ea640225c2467653db90e9250aaa0",
    "0x325e26d065f5c47d6bf378ba6f22811fd616f1bd",
    "0x3db4b7da67dd5af61cb9b3c70501b1bdb24b2c22",
    "0x3e6648c5a70a150a88bce65f4ad4d506fe15d2af",
    "0x3f56e0c36d275367b8c502090edf38289b3dea0d",
    "0x40301951af3f80b8c1744ca77e55111dd3c1dba1",
    "0x46f74778b265df3a15ec9695ccd2fd3869ca848c",
    "0x485ac8b64f5278f48441ee13831b115e176662e6",
    "0x4945970efeec98d393b4b979b9be265a3ae28a8b",
    "0x5372036e630e69df05791860b71e71665d9524f5",
    "0x539bde0d7dbd336b79148aa742883198bbf60342",
    "0x5429706887fcb58a595677b73e9b0441c25d993d",
    "0x5575552988a3a80504bbaeb1311674fcfd40ad4b",
    "0x5979d7b546e38e414f7e9822514be443a4800529",
    "0x6688b00f0c23a4a546beaae51a7c90c439895d48",
    "0x6a7661795c374c0bfc635934efaddff3a7ee23b6",
    "0x6aa395f06986ea4efe0a4630c7865c1eb08d5e7e",
    "0x6edf5622643254c52702f31fc499c54690a5c593",
    "0x74ccbe53f77b08632ce0cb91d3a545bf6b8e0979",
    "0x7f465507f058e17ad21623927a120ac05ca32741",
    "0x80bb30d62a16e1f2084deae84dc293531c3ac3a1",
    "0x82af49447d8a07e3bd95bd0d56f35241523fbab1",
    "0x82e3a8f066a6989666b031d916c43672085b1582",
    "0x8a72b245d60f2dabad44041d050d08c35ba60f43",
    "0x912ce59144191c1204e64559fe8253a0e49e6548",
    "0x921f99719eb6c01b4b8f0ba7973a7c24891e740a",
    "0x93b346b6bc2548da6a1e7d98e9a421b42541425b",
    "0x93f854ba0cb6fccaa4afb7a45db4b4e5e4989b9f",
    "0x954ac1c73e16c77198e83c088ade88f6223f3d44",
    "0x95ab45875cffdba1e5f451b950bc2e42c0053f39",
    "0x9830529a03f4e1bab41ff441a16901f211442622",
    "0x99c409e5f62e4bd2ac142f17cafb6810b8f0baae",
    "0x9d2f299715d94d8a7e6f5eaa8e654e8c74a988a7",
    "0xa1150db5105987cec5fd092273d1e3cbb22b378b",
    "0xa4a9ef80ee5d5fd8426f9861ed13e3aad5ddd096",
    "0xa7903c2d3518ac23ea013403df3fc5c6267259b5",
    "0xaaa6c1e32c55a7bfa8066a6fae9b42650f262418",
    "0xaae0c3856e665ff9b3e2872b6d75939d810b7e40",
    "0xad435674417520aeeed6b504bbe654d4f556182f",
    "0xb261104a83887ae92392fb5ce5899fcfe5481456",
    "0xb3221e033cf491a0052add79f60e2a3fa1f8c0c8",
    "0xb9c8f0d3254007ee4b98970b94544e473cd610ec",
    "0xbb85d38faa5064fab8bf3e0a79583a2670f03dbc",
    "0xbf05279f9bf1ce69bbfed670813b7e431142afa4",
    "0xc5102fe9359fd9a28f877a67e36b0f050d81a3cc",
    "0xcaa38bcc8fb3077975bbe217acfaa449e6596a84",
    "0xcf985aba4647a432e60efceeb8054bbd64244305",
    "0xd0e6435d5a0fdfe73c90dcc206e22dd99f1b1db9",
    "0xd42785d323e608b9e99fa542bd8b1000d4c2df37",
    "0xd74f5255d557944cf7dd0e45ff521520002d5748",
    "0xd85e038593d7a098614721eae955ec2022b9b91b",
    "0xda10009cbd5d07dd0cecc66161fc93d7c9000da1",
    "0xdba35afc5f4d5af4933c29a157dab3975f3eee9b",
    "0xde1e704dae0b4051e80dabb26ab6ad6c12262da0",
    "0xde5ed76e7c05ec5e4572cfc88d1acea165109e44",
    "0xe05a08226c49b636acf99c40da8dc6af83ce5bb3",
    "0xe80772eaf6e2e18b651f160bc9158b2a5cafca65",
    "0xea2fb0b18d40d1f6837bdf54749cc9a43469d40b",
    "0xeb8e93a0c7504bffd8a8ffa56cd754c63aaebfe8",
    "0xec13336bbd50790a00cdc0feddf11287eaf92529",
    "0xf97f4df75117a78c1a5a0dbb814af92458539fb4",
    "0xfa5ed56a203466cbbc2430a43c66b9d8723528e7",
    "0xfb9e5d956d889d91a82737b9bfcdac1dce3e1449",
    "0xfc5a1a6eb076a2c7ad06ed22c90d7e710e35ad0a",
    "0xfd086bc7cd5c481dcc9c85ebe478a1c0b69fcbb9",
    "0xfea7a6a0b346362bf88a9e4a88416b77a57d6c2a",
    "0xff970a61a04b1ca14834a43f5de4533ebddb5cc8"
]


def get_prices():
    coins = []
    prices = {}
    for token_address in token_addresses:
        coins.append(f'arbitrum:{token_address}')
        # prices[token_address] = 0

    response = requests.get(
        url=f"https://coins.llama.fi/prices/current/{','.join(coins)}",
    )

    print(response.status_code)

    for key, value in response.json()['coins'].items():
        _, token_address = key.split(':')
        prices[value['symbol']] = value['price']

    pprint(prices)


if __name__ == '__main__':
    get_prices()
