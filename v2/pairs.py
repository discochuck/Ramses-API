import datetime
import json
from pprint import pprint

from multicall import Multicall, Call
from utils import w3, db, log, RAM_ADDRESS, V1_FACTORY_ADDRESS, fees
from v2.subgraph import get_subgraph_tokens, get_subgraph_pairs, get_subgraph_pair_day_data


def _fetch_pairs(debug):
    # set constants
    week = 7 * 24 * 60 * 60
    now = datetime.datetime.now().timestamp()
    period = int(now // week * week + week)

    # fetch tokens and pairs from subgraph
    tokens_array = get_subgraph_tokens(debug)
    pairs_array = get_subgraph_pairs(debug)
    pair_day_data = get_subgraph_pair_day_data(len(pairs_array), debug)

    # reformat tokens and pairs
    # + filter out pairs without gauge
    tokens = {}
    for token in tokens_array:
        token['price'] = float(token['price'])
        token['decimals'] = int(token['decimals'])
        tokens[token['id']] = token
    pairs = {}
    for pair in pairs_array:
        if pair['gauge']:
            pair['voteBribes'] = {}
            pair['totalVeShareByPeriod'] = 0
            pair['reserve0'] = int(pair['reserve0'])
            pair['reserve1'] = int(pair['reserve1'])
            pair['totalSupply'] = int(pair['totalSupply'])
            pair['gauge']['totalDerivedSupply'] = int(pair['gauge']['totalDerivedSupply'])
            pair['projectedFees'] = {'tokens': {}, 'apr': 0}
            pairs[pair['id']] = pair

    # set pair TVL
    _pairs_price = {}
    for pair_address, pair in pairs.items():
        pair['tvl'] = pair['reserve0'] * tokens[pair['token0']]['price'] / 10 ** tokens[pair['token0']]['decimals'] \
            + pair['reserve1'] * tokens[pair['token1']]['price'] / 10 ** tokens[pair['token1']]['decimals']
        if pair['totalSupply'] > 0:
            _pairs_price[pair_address] = pair['tvl'] * 1e18 / pair['totalSupply']
        else:
            _pairs_price[pair_address] = 0

    # fetch pair's vote share
    calls = []
    for pair_address, pair in pairs.items():
        fee_distributor_address = pair['feeDistributor']['id']
        calls.append(
            Call(
                w3,
                fee_distributor_address,
                ["totalVeShareByPeriod(uint256)(uint256)", period],
                [[pair_address, lambda v: v[0]]]
            )
        )
    for pair_address, value in Multicall(w3, calls)().items():
        pairs[pair_address]['totalVeShareByPeriod'] += value

    # fetch pair's vote bribes
    calls = []
    for pair_address, pair in pairs.items():
        fee_distributor_address = pair['feeDistributor']['id']
        for token_address in pair['feeDistributor']['rewardTokens']:
            key = f'{pair_address}-{token_address}'
            calls.append(
                Call(
                    w3,
                    fee_distributor_address,
                    ["tokenTotalSupplyByPeriod(uint256,address)(uint256)", period, token_address],
                    [[key, lambda v: v[0]]]
                )
            )
    for key, value in Multicall(w3, calls)().items():
        pair_address, token_address = key.split('-')
        if value > 0:
            pairs[pair_address]['voteBribes'][token_address] = value

    # fetch pair's lp reward rates
    _reward_rates = {}
    _period_finish = {}
    calls = []
    period_finish_calls = []
    for pair_address, pair in pairs.items():
        _reward_rates[pair_address] = {}
        _period_finish[pair_address] = {}
        for token_address in pair['gauge']['rewardTokens']:
            _reward_rates[token_address] = 0
            key = f'{pair_address}-{token_address}'

            calls.append(
                Call(
                    w3,
                    pair['gauge']['id'],
                    ["rewardRate(address)(uint256)", token_address],
                    [[key, lambda v: v[0]]]
                ),
            )

            period_finish_calls.append(
                Call(
                    w3,
                    pair['gauge']['id'],
                    ["periodFinish(address)(uint256)", token_address],
                    [[key, lambda v: int(v[0])]]
                ),
            )

    for key, value in Multicall(w3, calls)().items():
        pair_address, token_address = key.split('-')
        _reward_rates[pair_address][token_address] = value

    for key, value in Multicall(w3, period_finish_calls)().items():
        pair_address, token_address = key.split('-')
        _period_finish[pair_address][token_address] = value

    # fetch pair's fee ratios
    calls = []
    for pair_address, pair in pairs.items():
        key = pair_address
        pair['fee'] = fees['stable'] if pair['isStable'] else fees['variable']  # default fees
        # fetch custom fees
        calls.append(
            Call(
                w3,
                V1_FACTORY_ADDRESS,
                ["pairFee(address)(uint256)", pair['id']],
                [[key, lambda v: v[0]]]
            )
        )
    for key, value in Multicall(w3, calls)().items():
        if value > 0:
            pairs[key]['fee'] = value

    # calculate APRs
    for pair_address, pair in pairs.items():
        # calculate vote APR
        if pair['totalVeShareByPeriod'] > 0:
            totalUSD = 0
            for token_address, amount in pair['voteBribes'].items():
                totalUSD += amount * tokens[token_address]['price'] / 10 ** tokens[token_address]['decimals']
            pair['voteApr'] = totalUSD / 7 * 36500 / (pair['totalVeShareByPeriod'] * tokens[RAM_ADDRESS]['price'] / 1e18)
        else:
            pair['voteApr'] = 0

        # calculate LP APR
        if pair['gauge']['totalDerivedSupply'] > 0:
            totalUSD = 0
            for token_address in pair['gauge']['rewardTokens']:
                if _period_finish[pair_address][token_address] > now:
                    totalUSD += _reward_rates[pair_address][token_address] * 24 * 60 * 60 * tokens[token_address]['price'] / 10 ** tokens[token_address][
                        'decimals']
            pair['lpApr'] = totalUSD * 36500 / (pair['gauge']['totalDerivedSupply'] * _pairs_price[pair_address] / 1e18) / 2.5
        else:
            pair['lpApr'] = 0

        # add up each day's fees
        pair['projectedFees']['tokens'][pair['token0']] = 0
        pair['projectedFees']['tokens'][pair['token1']] = 0
        for day in pair_day_data.get(pair['id'], []):
            pair['projectedFees']['tokens'][pair['token0']] += int(float(day['dailyVolumeToken0']) * pair['fee'] / 1e4 * 10**tokens[pair['token0']]['decimals'])
            pair['projectedFees']['tokens'][pair['token1']] += int(float(day['dailyVolumeToken1']) * pair['fee'] / 1e4 * 10**tokens[pair['token1']]['decimals'])

        # calculate vote APR
        if pair['totalVeShareByPeriod'] > 0:
            totalUSD = 0
            projected_fees_usd = 0
            for token_address, amount in pair['voteBribes'].items():
                totalUSD += amount * tokens[token_address]['price'] / 10 ** tokens[token_address]['decimals']
            pair['voteApr'] = totalUSD / 7 * 36500 / (pair['totalVeShareByPeriod'] * tokens[RAM_ADDRESS]['price'] / 1e18)

            # calculate the fees in USD
            for token_address, amount in pair['projectedFees']['tokens'].items():
                projected_fees_usd += amount * tokens[token_address]['price'] / 10 ** tokens[token_address]['decimals']
            pair['projectedFees']['apr'] = projected_fees_usd / 7 * 36500 / (pair['totalVeShareByPeriod'] * tokens[RAM_ADDRESS]['price'] / 1e18)
        else:
            pair['voteApr'] = 0

    # convert floats to strings
    for pair_address, pair in pairs.items():
        for key in pair.keys():
            if isinstance(pair[key], float) or (isinstance(pair[key], int) and not isinstance(pair[key], bool)):
                pair[key] = "{:.18f}".format(pair[key])

        for token_address, amount in pair['voteBribes'].items():
            pair['voteBribes'][token_address] = "{:.18f}".format(amount)

    return {
        'tokens': list(tokens.values()),
        'pairs': list(pairs.values())
    }


def get_pairs_v2(debug=False):
    try:
        pairs = _fetch_pairs(debug)
        db.set('v2_pairs', json.dumps(pairs))
    except Exception as e:
        if debug:
            raise e
        log("Error on get_pairs")
        pairs = json.loads(db.get('v2_pairs'))

    return pairs


if __name__ == '__main__':
    p = get_pairs_v2(True)

    pprint(p['pairs'])
