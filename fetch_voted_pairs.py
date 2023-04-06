import csv
import json
import math
from pprint import pprint

from coingecko import get_prices
from multicall import Call, Multicall
from utils import w3, db

period = 1680134400 + 7 * 24 * 60 * 60

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


def store_voted_pairs():
    voted_pairs = {}

    for i in range(1, 1400, 50):
        print(i, i + 50)
        if i in voted_pairs:
            continue

        for key, value in get_voted_pairs(range(i, i + 50)).items():
            voted_pairs[key] = value

    db.set('voted_pairs', json.dumps(voted_pairs))


def process_lost():
    with open('./lost.json', 'r') as file:
        data = json.load(file)

    pairs = {}
    symbols = []
    for pair_address, pair in data.items():

        if pair_address not in lost_pairs:
            continue

        pairs[pair_address] = {
            'pair_address': pair_address,
            'symbol': pair['symbol'],
            'fee_distributor_address': pair['fee_distributor_address'],
            'tokens': []
        }
        for token_address, token in pair['lost'].items():
            if token['lost'] > 0:
                symbols.append(token['symbol'])
                lost_usd = token['lost'] / 10 ** token['decimals'] * token['price']
                pairs[pair_address]['tokens'].append({
                    'address': token_address,
                    'decimals': token['decimals'],
                    'symbol': token['symbol'],
                    'lost': token['lost'],
                    'lost_usd': lost_usd
                })

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


def main():
    # lusd lqty
    #  0x0f9a90636c778f6a583f7d2212e4921715af4900

    with open('./pairs.json', 'r') as file:
        pairs = json.load(file)

    # with open('./voted_pairs.json', 'r') as file:
    #     voted_pairs = json.load(file)

    store_voted_pairs()
    voted_pairs = json.loads(db.get('voted_pairs'))

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
                pair['lost']
            )

    db.set('lost', json.dumps(dict(pairs)))


if __name__ == '__main__':
    # calculate_rewards()
    # process_lost()
    main()
    # double_check()
