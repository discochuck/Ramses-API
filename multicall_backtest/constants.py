from enum import IntEnum


class Network(IntEnum):
    Mainnet = 1
    Kovan = 42
    Rinkeby = 4
    Görli = 5
    xDai = 100
    BSC = 56
    Polygon = 137
    Avax = 43114
    Fantom = 250
    Okex = 66
    Arbi = 42161


MULTICALL_ADDRESSES = {
    Network.Mainnet: "0x5eb3fa2dfecdde21c950813c665e9364fa609bd2",
    Network.Kovan: "0x2cc8688C5f75E365aaEEb4ea8D6a480405A48D2A",
    Network.Rinkeby: "0x42Ad527de7d4e9d9d011aC45B31D8551f8Fe9821",
    Network.Görli: "0x77dCa2C955b15e9dE4dbBCf1246B4B85b651e50e",
    Network.xDai: "0xb5b692a88BDFc81ca69dcB1d924f59f0413A602a",
    Network.BSC: "0x6Cf63cC81660Dd174A49e0C61A1f916456Ee1471",
    Network.Polygon: "0x8a233a018a2e123c0D96435CF99c8e65648b429F",
    Network.Avax: "0x12AB889eb2886d76BC609f930D4DCb759E515bfc",
    Network.Fantom: "0x08AB4aa09F43cF2D45046870170dd75AE6FBa306",
    Network.Okex: "0x6ddB0845aeB285eD7ef712768a0E123c8F2Eab0E",
    Network.Arbi: "0x65487D83406457ef860700685e4Bd14de938865D",
    # Network.KCC: '0x08ab4aa09f43cf2d45046870170dd75ae6fba306',
    # Network.Optimism: '',
    # Network.ONE: '0x12AB889eb2886d76BC609f930D4DCb759E515bfc'
}
