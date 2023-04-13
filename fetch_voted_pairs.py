import csv
import json
import math
from pprint import pprint

from coingecko import get_prices
from multicall import Call, Multicall
from utils import w3, db

period = 1680739200 + 604800

lost_pairs = ['0x93d98b4caac02385a0ae7caaeadc805f48553f76', '0xba9f17ca67d1c8416bb9b132d50232191e27b45e', '0x040da64a9347c9786069eee1d191a1b9062edc0f',
              '0xeb9153afbaa3a6cfbd4fce39988cea786d3f62bb', '0xce63c58c83ed2aff21c1d5bb85bad93869c632f7', '0xe25c248ee2d3d5b428f1388659964446b4d78599',
              '0xd46f8323e6e5540746e2df154cc1056907e89c7a', '0xb1406b8344cd65dbe9f304938c0ecf2209f54d18', '0x8ac36fbce743b632d228f9c2ea5e3bb8603141c7',
              '0x109eb5e931b1ddf115997ebcf918ac07a75d3778', '0x159d1e96a39b3bd85a08d0e852c9e0560b268ecd', '0x7052992202c4308e64880d56b3f30a483371db6b',
              '0x64204895b538c794dc131f5500e54e50dafe4b75', '0xbd8121b651a9374bdd08a005bc59ff067930dba6', '0x54de7a8ba975d455f3c69c4d48e0e41a349c9088',
              '0xe3e757bc5af026ae80095cdaace0b51a61f5e639', '0x6b18ae9225011eaf4a7e52f1069fb66462406bf0', '0x0212363bc16e8d1844580becccdceb8614b68af4',
              '0x92a248663e9a8bb602fc18898eb91cc30c92a387', '0x3932192de4f17dfb94be031a8458e215a44bf560', '0x0abc6e5146e53bc71b343d8eca22a017103f4463',
              '0xdd8b120ddae0f19b922324012816f2f3ce529bf8', '0xf0eab4513cd5671604eef90761b8bcb209e64df1', '0x275f7112e3900fdf3c9532d749dd4985790e7933',
              '0x5513a48f3692df1d9c793eeab1349146b2140386', '0x1e50482e9185d9dac418768d14b2f2ac2b4daf39', '0xb4752b59dce5f1fe0f45ef5aa9e1ad1eef9ab927',
              '0x7a492402bfe4362a17db3c38b04d17545e08a396', '0x3f6253767208aaf70071d563403c8023809d52ff', '0x3c6ef5ed8ad5df0d5e3d05c6e607c60f987fb735',
              '0xc977492506e6516102a5687154394ed747a617ff', '0x0f9a90636c778f6a583f7d2212e4921715af4900', '0xfe3b6dd9457e13b2f44b9356e55fc5e6248b27ba',
              '0xa1e132274b8f808fcf4bff91804417f1cccfc0f1', '0x893684af15c97bccef17b10b1f32dc18bc066654', '0x96db7fb649cfe9b65493b2f6b4422736ccf5b7bf',
              '0x218fdee44e8e923b500895e324af6c0a2e07195d', '0x8e78f0f6d116f94252d3bcd73d8ade63d415c1bf', '0x00d61bcc9541e3027fea534d92cc8cc097c7a51c']


def get_voted_pairs(token_ids):
    pairs = json.loads(db.get('pairs'))

    calls = []
    for token_id in token_ids:
        for pair_address, pair in pairs.items():
            key = f"{token_id}-{pair_address}"
            if pair['fee_distributor_address']:
                calls.append(
                    Call(
                        w3,
                        pair['fee_distributor_address'],
                        ["veShareByPeriod(uint256,uint256)(uint256)", period, token_id],
                        [[key, lambda v: int(v[0])]]
                    )
                )

    print(len(calls))
    voted_pairs = {}
    for key, weight in Multicall(w3, calls)().items():
        token_id, pair_address = key.split('-')
        token_voted_pairs = voted_pairs.get(token_id, {})
        if weight > 0:
            token_voted_pairs[pair_address] = weight
            voted_pairs[token_id] = token_voted_pairs

    return voted_pairs


def store_voted_pairs():
    voted_pairs = {}

    for i in range(1, 2000, 50):
        print(i, i + 50)
        if i in voted_pairs:
            continue

        for key, value in get_voted_pairs(range(i, i + 50)).items():
            voted_pairs[key] = value

    db.set('voted_pairs', json.dumps(voted_pairs))


def calculate_lost(pair):
    fee_distributor_address = pair['fee_distributor_address']

    lost = {}

    for token in pair['fee_distributor_tokens']:
        print(token['symbol'])
        calls = []
        for token_id in pair['voters']:
            calls.append(
                Call(
                    w3,
                    fee_distributor_address,
                    ["earned(address,uint256)(uint256)", token['address'], token_id],
                    [[token_id, lambda v: int(v[0])]]
                )
            )

        calls.append(
            Call(
                w3,
                token['address'],
                ["balanceOf(address)(uint256)", pair['fee_distributor_address']],
                [[token['address'], lambda v: int(v[0])]]
            )
        )

        result = Multicall(w3, calls)()
        balance = result.pop(token['address'])
        total_earned = 0
        for token_id, earned in result.items():
            total_earned += earned

        lost[token['address']] = {
            'lost': total_earned - balance,
            **token,
        }

    return lost


def process_lost():
    with open('./lost.json', 'r') as file:
        data = json.load(file)

    total_lost_usd = 0
    pairs = {}
    symbols = []
    for pair_address, pair in data.items():

        if 'lost' not in pair:
            continue

        if pair['totalVeShareByPeriod'] == 0:
            continue

        pairs[pair_address] = {
            'pair_address': pair_address,
            'symbol': pair['symbol'],
            'fee_distributor_address': pair['fee_distributor_address'],
            'tokens': [],
            'pair_lost_usd': 0
        }
        for token_address, token in pair['lost'].items():
            if token['lost'] > 0:
                symbols.append(token['symbol'])
                lost_usd = token['lost'] / 10 ** token['decimals'] * token['price']
                total_lost_usd += lost_usd
                pairs[pair_address]['tokens'].append({
                    'address': token_address,
                    'decimals': token['decimals'],
                    'symbol': token['symbol'],
                    'lost': token['lost'],
                    'lost_usd': lost_usd
                })
                pairs[pair_address]['pair_lost_usd'] += lost_usd
            else:
                if abs(token['lost'] / 1e18) > 10:
                    print(pair['symbol'], token['symbol'], token['lost'] / 1e18)

        pair_lost = pairs[pair_address].get('pair_lost_usd')
        # if pair_lost:
        # print(pairs[pair_address]['symbol'], pair_lost, total_lost_usd)

    print('total lost usd:', total_lost_usd)
    with open('simplified_lost.json', 'w') as file:
        file.write(json.dumps(pairs))

    symbols = list(set(symbols))
    rows = []
    text_output = ''
    for symbol in symbols:
        text_output += f'\n{symbol}\n'
        total = 0
        unscaled_total = 0
        rows.append(["Pair", "Fee Distributor", f"{symbol} Amount", "Unscaled Amount"])
        for pair_address, pair in pairs.items():
            for token in pair['tokens']:
                if token['symbol'] == symbol:
                    text_output += f"erc20,{token['address']},{pair['fee_distributor_address']},{token['lost'] / 10 ** token['decimals']},\n"
                    rows.append([
                        pair['symbol'], pair['fee_distributor_address'], token['lost'], token['lost'] / 10 ** token['decimals']
                    ])
                    total += token['lost']
                    unscaled_total += token['lost'] / 10 ** token['decimals']
        rows.append(['', '', total, unscaled_total])
        rows.append([])
        rows.append([])

    with open(f"transfers/transfers.csv", 'w', newline='') as file:
        csv.writer(file).writerows(rows)

    with open(f"transfers/transfers.txt", 'w') as file:
        file.write(text_output)


def calculate_rewards():
    with open('./lost.json', 'r') as file:
        lost_data = json.load(file)

    with open('./voted_pairs.json', 'r') as file:
        voted_pairs = json.load(file)

    symbols = []

    rewards = {}
    rewards_human_readable = {}
    for token_id, votes in voted_pairs.items():
        token_id = int(token_id)
        rewards[token_id] = {}
        rewards_human_readable[token_id] = {}
        for pair_address, ve_share in votes.items():
            pair_symbol = lost_data[pair_address]['symbol']

            rewards[token_id][pair_address] = {}
            rewards_human_readable[token_id][pair_symbol] = {}
            for token in lost_data[pair_address]['fee_distributor_tokens']:
                token_symbol = token['symbol']
                symbols.append(token_symbol)

                correct_reward = wrong_reward = 0
                if lost_data[pair_address]['correctTotalVeShareByPeriod'] > 0:
                    correct_reward = ve_share * token['tokenTotalSupplyByPeriod'] / lost_data[pair_address]['correctTotalVeShareByPeriod'] / 10 ** token[
                        'decimals']
                if lost_data[pair_address]['totalVeShareByPeriod'] > 0:
                    wrong_reward = ve_share * token['tokenTotalSupplyByPeriod'] / lost_data[pair_address]['totalVeShareByPeriod'] / 10 ** token['decimals']

                token_rewards = {
                    'correct_reward': correct_reward,
                    'wrong_reward': wrong_reward
                }
                rewards[token_id][pair_address][token['address']] = token_rewards
                rewards_human_readable[token_id][pair_symbol][token_symbol] = token_rewards

    # pprint(rewards_human_readable[3])

    symbols = list(set(symbols))
    prices = get_prices(symbols)

    total_lost = 0
    token_extra_reward = []
    for token_id, pairs in rewards_human_readable.items():
        token_total_extra_reward = 0
        for pair_symbol, tokens in pairs.items():
            for token_symbol, token_rewards in tokens.items():
                if token_symbol != 'RAM':
                    continue
                diff = token_rewards['wrong_reward'] - token_rewards['correct_reward']
                assert diff >= 0
                token_total_extra_reward += diff * prices[token_symbol]
                total_lost += diff * prices[token_symbol]
        token_extra_reward.append([token_id, int(token_total_extra_reward)])

    print(total_lost)
    token_extra_reward = sorted(token_extra_reward, key=lambda x: x[1])
    prev = 0
    for row in token_extra_reward:
        row.append(prev + row[1])
        prev += row[1]

    for row in token_extra_reward:
        row[1] //= prices['RAM']
        row[2] //= prices['RAM']

    pprint(
        sorted(token_extra_reward, key=lambda x: x[1])
    )


def double_check():
    with open('./lost.json', 'r') as file:
        data1 = json.load(file)

    with open('./lost_double_check.py', 'r') as file:
        data2 = json.load(file)

    for pair_address, pair in data1.items():
        for token_address, _ in pair.get('lost', {}).items():
            token1 = data1[pair_address]['lost'][token_address]
            token2 = data2[pair_address]['lost'][token_address]
            if token1['lost'] != token2['lost'] > 0:
                print(pair['symbol'], token1['symbol'])
                print(token1['lost'] / 10 ** token1['decimals'], token2['lost'] / 10 ** token2['decimals'])
                print()


def get_pairs():
    with open('./pairs.json', 'r') as file:
        pairs = json.load(file)

    calls = []
    for pair_address, pair in pairs.items():
        fee_distributor_address = pair['fee_distributor_address']
        calls.append(
            Call(
                w3,
                fee_distributor_address,
                ["totalVeShareByPeriod(uint256)(uint256)", period],
                [[pair_address, lambda v: v[0]]]
            )
        )

    for pair_address, total_ve_share in Multicall(w3, calls)().items():
        pairs[pair_address]['totalVeShareByPeriod'] = total_ve_share

    with open('./pairs.json', 'w') as file:
        file.write(json.dumps(pairs))

    return pairs


def check_ve_share():
    # lusd lqty
    #  0x0f9a90636c778f6a583f7d2212e4921715af4900

    # pairs = get_pairs()
    with open('./pairs.json', 'r') as file:
        pairs = json.load(file)

    with open('./voted_pairs.json', 'r') as file:
        voted_pairs = json.load(file)

    # store_voted_pairs()
    # voted_pairs = json.loads(db.get('voted_pairs'))

    for pair_address, pair in pairs.items():
        pair['correctTotalVeShareByPeriod'] = 0
        pair['voters'] = []

    for token_id, votes in voted_pairs.items():
        for pair_address, weight in votes.items():
            pairs[pair_address]['correctTotalVeShareByPeriod'] += weight
            pairs[pair_address]['voters'].append(int(token_id))

    for pair_address, pair in pairs.items():
        if pair['totalVeShareByPeriod'] != pair['correctTotalVeShareByPeriod']:
            pair['lost'] = dict(calculate_lost(pair).items())
            print(
                pair['symbol'],
                len(pair['voters']),
                pair['totalVeShareByPeriod'],
                pair['correctTotalVeShareByPeriod'],
                abs(pair['totalVeShareByPeriod'] - pair['correctTotalVeShareByPeriod']) / 1e18

            )

    db.set('lost', json.dumps(dict(pairs)))


def check_balance(fee_distributor_address, token_address):
    calls = []
    for token_id in range(1, 2000):
        calls.append(
            Call(
                w3,
                fee_distributor_address,
                ["earned(address,uint256)(uint256)", token_address, token_id],
                [[token_id, lambda v: int(v[0])]]
            )
        )
    calls.append(
        Call(
            w3,
            token_address,
            ["balanceOf(address)(uint256)", fee_distributor_address],
            [[token_address, lambda v: int(v[0])]]
        )
    )
    calls.append(
        Call(
            w3,
            token_address,
            ["decimals()(uint256)"],
            [['decimals', lambda v: int(v[0])]]
        )
    )

    result = Multicall(w3, calls)()
    detail = result.copy()

    balance = result[token_address]
    del result[token_address]

    decimals = result['decimals']
    del result['decimals']

    required_balance = 0
    for token_id, earned in result.items():
        required_balance += earned

    return {
        'fee_distributor_address': fee_distributor_address,
        'token_address': token_address,
        'decimals': decimals,
        'balance': balance,
        'required_balance': required_balance,
        'diff': balance - required_balance,
        # 'detail': detail
        'detail': {}
    }


def store_balance_check():
    balance_checks = {}
    pairs = json.loads(db.get('pairs'))
    for pair_address, pair in pairs.items():
        pair_symbol = pair['symbol']
        print(pair_symbol)
        balance_checks[pair_symbol] = {}
        for token in pair['fee_distributor_tokens']:
            token_symbol = token['symbol']
            print('-', token_symbol)
            check_result = check_balance(pair['fee_distributor_address'], token['address'])
            balance_checks[pair_symbol][token_symbol] = check_result

        db.set('balance_checks', json.dumps(balance_checks))


def process_balance_check(use_db=False):
    if use_db:
        balance_checks = json.loads(db.get('balance_checks'))
        pairs = json.loads(db.get('pairs'))
    else:
        with open('balance_check3.json', 'r') as file:
            balance_checks = json.load(file)
        with open('./pairs.json', 'r') as file:
            pairs = json.load(file)

    # extract decimals
    decimals = {}
    pairs_addresses = {}
    for _, pair in pairs.items():
        pairs_addresses[pair['symbol']] = _
        for token in pair['fee_distributor_tokens']:
            decimals[token['symbol']] = token['decimals']

    # extract symbols
    symbols = []
    for pair_symbol, tokens in balance_checks.items():
        for token_symbol, token in tokens.items():
            symbols.append(token_symbol)
    symbols = list(set(symbols))

    # get prices
    prices = get_prices(symbols)

    lost_usd = 0
    extra_usd = 0
    pair_losts = []
    transfers = []
    for pair_symbol, tokens in balance_checks.items():
        pair_lost_usd = 0
        pair_extra_usd = 0
        for token_symbol, token in tokens.items():
            diff = token['diff'] // 10 ** decimals[token_symbol] * prices[token_symbol]
            if diff > 0:
                pair_extra_usd += diff
            else:
                pair_lost_usd += diff

            token_address = token['address']
            if diff < -10:
                amount = token['diff'] / 10 ** token['decimals']
                print(token['diff'] - amount * 10 ** token['decimals'] > 0)
                amount += token['diff'] - amount * 10 ** token['decimals']

                transfers.append(['erc20',token_address, ])

        if abs(pair_extra_usd) < 10 and abs(pair_lost_usd) < 10:
            continue

        # print(pair_symbol, pair_lost_usd, pair_extra_usd)
        pair_losts.append([
            pairs_addresses[pair_symbol],
            -pair_lost_usd,
            pair_symbol,
            len(tokens.keys())
        ])

        lost_usd += pair_lost_usd
        extra_usd += pair_extra_usd

    pair_losts = list(sorted(pair_losts, key=lambda x: x[1], reverse=True))

    # for pair_address, _, __ in pair_losts:
    #     pair = pairs[pair_address]
    #     print(pair['symbol'], end=' ')
    #     verify_total_ve_share(pair['fee_distributor_address'])

    # pprint(pair_losts)
    # print(lost_usd, extra_usd)

    # pprint(transfers)

    # pair_symbol = 'vrAMM-TAROT/WETH'
    # print([token_id for token_id, earned in list(balance_checks[pair_symbol].values())[0]['detail'].items() if earned > 0])
    # print([token_id for token_id, earned in list(balance_checks[pair_symbol].values())[1]['detail'].items() if earned > 0])
    # print(pairs[pairs_addresses[pair_symbol]]['fee_distributor_address'])


def verify_total_ve_share(fee_distributor_address):
    calls = []
    for token_id in range(1, 2000):
        calls.append(
            Call(
                w3,
                fee_distributor_address,
                ["veShareByPeriod(uint256,uint256)(uint256)", period, token_id],
                [[token_id, lambda v: int(v[0])]]
            )
        )

    calls.append(
        Call(
            w3,
            fee_distributor_address,
            ["totalVeShareByPeriod(uint256)(uint256)", period],
            [[0, lambda v: int(v[0])]]
        )
    )

    result = Multicall(w3, calls)()
    total_ve_share = result[0]
    del result[0]
    for key, weight in result.items():
        total_ve_share -= weight

    print(total_ve_share)


def main():
    pair_addresses = [
        '0x0f9a90636c778f6a583f7d2212e4921715af4900',
        '0x75eb76eb00f350709c51346c845984ca96fc0033',
        '0x109eb5e931b1ddf115997ebcf918ac07a75d3778',
        '0x1e50482e9185d9dac418768d14b2f2ac2b4daf39',
        '0x3932192de4f17dfb94be031a8458e215a44bf560',
        '0x275f7112e3900fdf3c9532d749dd4985790e7933',
        '0x5513a48f3692df1d9c793eeab1349146b2140386',
        '0xb1406b8344cd65dbe9f304938c0ecf2209f54d18',
        '0x64204895b538c794dc131f5500e54e50dafe4b75',
        '0x96db7fb649cfe9b65493b2f6b4422736ccf5b7bf',
        '0xd46f8323e6e5540746e2df154cc1056907e89c7a',
        '0xf0eab4513cd5671604eef90761b8bcb209e64df1',
        '0xce63c58c83ed2aff21c1d5bb85bad93869c632f7',
        '0x040da64a9347c9786069eee1d191a1b9062edc0f',
        '0x8ac36fbce743b632d228f9c2ea5e3bb8603141c7',
        '0x93d98b4caac02385a0ae7caaeadc805f48553f76',
        '0x00d61bcc9541e3027fea534d92cc8cc097c7a51c',
        '0x8e78f0f6d116f94252d3bcd73d8ade63d415c1bf',
        '0x92a248663e9a8bb602fc18898eb91cc30c92a387',
        '0x14ef31110d6dc9d178e5a994aa856260f9afe672',
        '0x3f6253767208aaf70071d563403c8023809d52ff',
        '0xe3e757bc5af026ae80095cdaace0b51a61f5e639',
        '0x7052992202c4308e64880d56b3f30a483371db6b',
        '0xba9f17ca67d1c8416bb9b132d50232191e27b45e',
        '0xa1e132274b8f808fcf4bff91804417f1cccfc0f1',
        '0x159d1e96a39b3bd85a08d0e852c9e0560b268ecd',
        '0x218fdee44e8e923b500895e324af6c0a2e07195d',
        '0xdd8b120ddae0f19b922324012816f2f3ce529bf8',
        '0x0f9a90636c778f6a583f7d2212e4921715af4900',
        '0xeb9153afbaa3a6cfbd4fce39988cea786d3f62bb',
    ]

    with open('./pairs.json', 'r') as file:
        pairs = json.load(file)

    token_ids = [3]
    for token_id in token_ids:
        print()
        print(token_id)
        earned = {}
        calls = []
        for pair_address in pair_addresses:
            pair = pairs[pair_address]
            fee_distributor_address = pair['fee_distributor_address']
            earned[pair_address] = {
                'symbol': pair['symbol'],
                'fee_distributor_address': fee_distributor_address,
                'tokens': {}
            }
            for token in pair['fee_distributor_tokens']:
                token_address = token['address']
                earned[pair_address]['tokens'][token_address] = {
                    'symbol': token['symbol'],
                    'decimals': token['decimals'],
                    'earned': 0,
                    'fee_distributor_balance': 0,
                }
                key = f"{pair_address}-{token_address}"
                calls.append(
                    Call(
                        w3,
                        fee_distributor_address,
                        ["earned(address,uint256)(uint256)", token_address, token_id],
                        [[f"{key}-earned", lambda v: int(v[0])]]
                    )
                )

                calls.append(
                    Call(
                        w3,
                        token_address,
                        ["balanceOf(address)(uint256)", fee_distributor_address],
                        [[f"{key}-balance", lambda v: int(v[0])]]
                    )
                )

        for key, amount in Multicall(w3, calls)().items():
            fee_distributor_address, token_address, t = key.split('-')
            if t == 'earned':
                earned[fee_distributor_address]['tokens'][token_address]['earned'] = amount
            else:
                earned[fee_distributor_address]['tokens'][token_address]['fee_distributor_balance'] = amount

        for pair_address, pair in earned.items():
            has_earned = False
            for token_address, token in pair['tokens'].items():
                earned = token['earned']
                balance = token['fee_distributor_balance']
                if earned > balance:
                    has_earned = True
                    print(pair['symbol'], token['symbol'], (earned - balance) / 10 ** token['decimals'])

            if has_earned:
                print('-', pair['fee_distributor_address'])
                print()


if __name__ == '__main__':
    # main()
    # calculate_rewards()
    # process_lost()
    # double_check()

    store_balance_check()
    # process_balance_check(use_db=True)

    # process_balance_check()
