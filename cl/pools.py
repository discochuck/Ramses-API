import datetime
import time
import json
import decimal
from decimal import Decimal
import math
from pprint import pprint

from multicall import Multicall, Call
from utils import w3, db, log, RAM_ADDRESS
from cl.subgraph import get_cl_subgraph_tokens, get_cl_subgraph_pools
from cl.tick import get_tick_at_sqrt_ratio, get_sqrt_ratio_at_tick, TICK_SPACINGS
from v2.pairs import get_pairs_v2
from v2.prices import get_prices
from cl.sqrt_price_math import get_amount0_delta, get_amount1_delta, token_amounts_from_current_price
from cl.constants.tokenType import Token_Type, weth_address
from cl.range_tvl import range_tvl

decimal.getcontext().prec = 50

with open('cl/constants/feeDistribution.json', 'r') as file:
    fee_distribution = json.load(file)


def _fetch_pools(debug):
    # set constants
    week = 7 * 24 * 60 * 60
    now = datetime.datetime.now().timestamp()
    period = int(now // week * week + week)

    # fetch tokens and pairs from subgraph
    tokens_array = get_cl_subgraph_tokens(debug)
    pools_array = get_cl_subgraph_pools(debug)

    # reformat tokens and pairs
    # + filter out pairs without gauge
    tokens = {}
    for token in tokens_array:
        token['price'] = float(token['price'])
        token['decimals'] = int(token['decimals'])
        tokens[token['id']] = token
    pools = {}
    for pool in pools_array:
        if pool.get('gauge', {}):
            pool['symbol'] = 'CL-' + pool['token0']['symbol'] + '-' + pool['token1']['symbol'] + '-' + str(float(pool['feeTier']) / 1e4) + '%'
            pool['voteBribes'] = {}
            pool['totalVeShareByPeriod'] = 0
            pool['liquidity'] = int(pool['liquidity'])
            pool['totalSupply'] = int(pool['liquidity'])
            pool['isStable'] = True
            pool['tvl'] = float(pool['totalValueLockedUSD'])
            pool['reserve0'] = float(pool['totalValueLockedToken0']) * 10**int(pool['token0']['decimals'])
            pool['reserve1'] = float(pool['totalValueLockedToken1']) * 10**int(pool['token1']['decimals'])
            pool['price'] = (float(pool['sqrtPrice']) / (2**96))**2
            pool['projectedFees'] = {'tokens': {}, 'apr': 0}
            pools[pool['id']] = pool

    today = time.time() // 86400 * 86400
    cutoff = today - 86400 * 3
    x96 = int(2**96)

    # process tvl
    for pool_address, pool in pools.items():
        token0_price = tokens[pool['token0']['id']]['price']
        token0_decimals = tokens[pool['token0']['id']]['decimals']
        token1_price = tokens[pool['token1']['id']]['price']
        token1_decimals = tokens[pool['token1']['id']]['decimals']
        pool['tvl'] = pool['reserve0'] * token0_price / 10 ** token0_decimals + pool['reserve1'] * token1_price / 10**token1_decimals

    # process fee apr, based on last 7 days' fees
    # usd in range is based on the day's high and low prices, narrowed to +- 10% if needed
    for pool_address, pool in pools.items():
        valid_days = list(filter(lambda day: int(day['date']) >= cutoff, pool['poolDayData']))

        pool['feesUSD'] = 0
        usd_in_range = 0
        token0 = tokens[pool['token0']['id']]
        token1 = tokens[pool['token1']['id']]
        pool['projectedFees']['days'] = 0
        pool['projectedFees']['tokens'][pool['token0']['id']] = 0
        pool['projectedFees']['tokens'][pool['token1']['id']] = 0

        # print()
        # print(pool['symbol'])
        for day in valid_days:

            day_usd_in_range = range_tvl(tokens, pool, int(day['liquidity']))

            if (day_usd_in_range > Decimal(day['tvlUSD'])):
                day_usd_in_range = Decimal(day['tvlUSD'])

            pool['feesUSD'] += float(day['feesUSD'])
            # print("day['feesUSD']", day['feesUSD'])
            # print("day['tvlUSD']", day['tvlUSD'])
            # print("day_usd_in_range", day_usd_in_range)
            # projected fees for the voters, this accounts for the 75% going to voter
            pool['projectedFees']['days'] += 1
            pool['projectedFees']['tokens'][pool['token0']['id']] += int(float(day['volumeToken0']) * int(pool['feeTier']) / 1e6 * 10**token0['decimals'] * fee_distribution['veRam'])
            pool['projectedFees']['tokens'][pool['token1']['id']] += int(float(day['volumeToken1']) * int(pool['feeTier']) / 1e6 * 10**token1['decimals'] * fee_distribution['veRam'])
            usd_in_range += float(day_usd_in_range)

        pool['averageUsdInRange'] = usd_in_range / len(valid_days) if len(valid_days) > 0 else 1

        # apr is in %s, 20% goes to users, 80% goes to veRAM and treasury
        try:
            # this already accounts for the 20% to LP
            pool['feeApr'] = pool['feesUSD'] / usd_in_range * 100 * fee_distribution['lp'] * 365

            # print()
            # print(pool['symbol'])
            # print("fees", pool['feesUSD'])
            # print("usd_in_range", usd_in_range)
            # print("feeApr", pool['feeApr'])
        except ZeroDivisionError:
            pool['feeApr'] = 0

    # fetch pair's vote share
    calls = []
    for pool_address, pool in pools.items():
        fee_distributor_address = pool['feeDistributor']['id']
        calls.append(
            Call(
                w3,
                fee_distributor_address,
                ["totalVeShareByPeriod(uint256)(uint256)", period],
                [[pool_address, lambda v: v[0]]]
            )
        )
    for pool_address, value in Multicall(w3, calls)().items():
        pools[pool_address]['totalVeShareByPeriod'] += value

    # fetch pair's vote bribes
    calls = []
    for pool_address, pool in pools.items():
        fee_distributor_address = pool['feeDistributor']['id']
        for token_address in pool['feeDistributor']['rewardTokens']:
            key = f'{pool_address}-{token_address}'
            calls.append(
                Call(
                    w3,
                    fee_distributor_address,
                    ["tokenTotalSupplyByPeriod(uint256,address)(uint256)", period, token_address],
                    [[key, lambda v: v[0]]]
                )
            )
    for key, value in Multicall(w3, calls)().items():
        pool_address, token_address = key.split('-')
        if value > 0:
            pools[pool_address]['voteBribes'][token_address] = value

    calls = []
    for pool_address, pool in pools.items():
        key = pool_address
        calls.append(
            Call(
                w3,
                pool_address,
                ["fee()(uint24)"],
                [[key, lambda v: v[0]]]
            )
        )
    for key, value in Multicall(w3, calls)().items():
        pool_address = key
        pools[pool_address]['initialFee'] = str(int(value))

    # fetch pair's lp reward rates
    _reward_rates = {}
    _period_finish = {}
    calls = []
    for pool_address, pool in pools.items():
        _reward_rates[pool_address] = {}
        _period_finish[pool_address] = {}
        for token_address in pool['gauge']['rewardTokens']:
            _reward_rates[token_address] = 0
            key = f'{pool_address}-{token_address}'

            calls.append(
                Call(
                    w3,
                    pool['gauge']['id'],
                    ["rewardRate(address)(uint256)", token_address],
                    [[key, lambda v: v[0]]]
                ),
            )

    for key, value in Multicall(w3, calls)().items():
        pool_address, token_address = key.split('-')
        _reward_rates[pool_address][token_address] = value

    # calculate APRs
    for pool_address, pool in pools.items():

        # calculate LP APR
        totalUSD = 0
        for token_address in pool['gauge']['rewardTokens']:
            # reward rate reported by gauge contracts are already normalized to total unboosted liquidity
            totalUSD += _reward_rates[pool_address][token_address] * 24 * 60 * 60 * tokens[token_address]['price'] / 10 ** tokens[token_address][
                'decimals']

        # lp apr estimate uses current tick (+-)7.5%, (+-)0.5%, or (+-)0.25%
        position_usd = 0
        if (pool['price'] > 0):
            position_usd = range_tvl(tokens, pool, pool['liquidity'])
            # make position_usd smaller if it's greater than tvl
            if (position_usd > pool['tvl']):
                position_usd = pool['tvl']

        pool['lpApr'] = (totalUSD * 36500 / (position_usd if position_usd > 0 else 1)) + (pool['feeApr'] if pool['feeApr'] < 10000 else 0)
        pool['lpAprOld'] = 4 * totalUSD * 36500 / (pool['tvl'] if pool['tvl'] > 0 else 1)
        # print("totalUSD", totalUSD)

        # calculate vote APR
        if pool['totalVeShareByPeriod'] > 0:
            totalUSD = 0
            projected_fees_usd = 0
            for token_address, amount in pool['voteBribes'].items():
                totalUSD += amount * tokens[token_address]['price'] / 10 ** tokens[token_address]['decimals']
            pool['voteApr'] = totalUSD / 7 * 36500 / (pool['totalVeShareByPeriod'] * tokens[RAM_ADDRESS]['price'] / 1e18)

            if (pool['projectedFees']['days'] > 0):
                for token_address, amount in pool['projectedFees']['tokens'].items():
                    projected_fees_usd += amount * tokens[token_address]['price'] / 10 ** tokens[token_address]['decimals']
                pool['projectedFees']['apr'] = projected_fees_usd / pool['projectedFees']['days'] * 36500 / (pool['totalVeShareByPeriod'] * tokens[RAM_ADDRESS]['price'] / 1e18)
        else:
            pool['voteApr'] = 0

    # convert floats to strings
    for pool_address, pool in pools.items():
        for key in pool.keys():
            if isinstance(pool[key], float) or (isinstance(pool[key], int) and not isinstance(pool[key], bool)):
                pool[key] = "{:.18f}".format(pool[key])

        for token_address, amount in pool['voteBribes'].items():
            pool['voteBribes'][token_address] = "{:.18f}".format(amount)

    # remove unused fields
    for pool_address, pool in pools.items():
        pool['token0'] = pool['token0']['id']
        pool['token1'] = pool['token1']['id']
        del pool['liquidity']
        del pool['totalValueLockedUSD']
        del pool['totalValueLockedToken0']
        del pool['totalValueLockedToken1']
        del pool['sqrtPrice']
        del pool['poolDayData']
        del pool['averageUsdInRange']
        del pool['feesUSD']

    for token_address, token in tokens.items():
        del token['type']

    return {
        'tokens': list(tokens.values()),
        'pools': list(pools.values())
    }


def get_cl_pools(debug=False):
    try:
        pools = _fetch_pools(debug)
        db.set('cl_pools', json.dumps(pools))
    except Exception as e:
        if debug:
            raise e
        log("Error on get_cl_pools")
        pools = json.loads(db.get('cl_pools'))

    return pools


def get_mixed_pairs(debug=False):
    cl = get_cl_pools(debug)
    v2 = get_pairs_v2(debug)

    combined_tokens = cl['tokens'] + v2['tokens']
    unique_tokens = []
    unique_token_ids = []
    for token in combined_tokens:
        if token['id'] not in unique_token_ids:
            unique_token_ids.append(token['id'])
            unique_tokens.append(token)

    combined_pairs = cl['pools'] + v2['pairs']

    return {
        'tokens': unique_tokens,
        'pairs': combined_pairs
    }


if __name__ == '__main__':
    p = get_cl_pools(True)

    pprint(p['pools'])
