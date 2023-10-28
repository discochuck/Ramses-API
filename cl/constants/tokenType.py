# Not using enum because it's not json serializable
Token_Type = {
    "RAM": -10,
    "LSD": -1,
    "OTHERS": 0,
    "WETH": 1,
    "LOOSE_STABLE": 2,
    "STABLE": 3,
}

token_type_dict = {
    "gDAI": Token_Type['LOOSE_STABLE'],
    "LUSD": Token_Type['LOOSE_STABLE'],
    "ERN": Token_Type['LOOSE_STABLE'],
    "stERN": Token_Type['LOOSE_STABLE'],
    "DOLA": Token_Type['LOOSE_STABLE'],
    "MAI": Token_Type['LOOSE_STABLE'],
    "GRAI": Token_Type['LOOSE_STABLE'],
    "jEUR": Token_Type["LOOSE_STABLE"],
    "STAR": Token_Type["LOOSE_STABLE"],
    "alUSD": Token_Type["LOOSE_STABLE"],
    "DUSD": Token_Type["LOOSE_STABLE"],
    "jEUR": Token_Type["LOOSE_STABLE"],
    "agEUR": Token_Type["LOOSE_STABLE"],
    "stEUR": Token_Type["LOOSE_STABLE"],
    "alUSD": Token_Type["LOOSE_STABLE"],

    "USDC": Token_Type['STABLE'],
    "USDC.e": Token_Type['STABLE'],
    "USDT": Token_Type['STABLE'],
    "FRAX": Token_Type['STABLE'],
    "DAI": Token_Type['STABLE'],

    "frxETH": Token_Type['LSD'],
    "sfrxETH": Token_Type['LSD'],
    "wstETH": Token_Type["LSD"],
    "swETH": Token_Type["LSD"],
}

weth_address = "0x82af49447d8a07e3bd95bd0d56f35241523fbab1".lower()
ram_address = "0xAAA6C1E32C55A7Bfa8066A6FAE9b42650F262418".lower()
