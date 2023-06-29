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
    cutoff = today - 86400 * 7
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
        pool['projectedFees']['tokens'][pool['token0']['id']] = 0
        pool['projectedFees']['tokens'][pool['token1']['id']] = 0
        for day in valid_days:
            # print(pool['token0']['symbol'], "-", pool['token1']['symbol'])
            try:
                token0_price_USD = next(token0_day for token0_day in pool['token0']['tokenDayData'] if token0_day['date'] == day['date'])
                token0_price_USD = Decimal(token0_price_USD['priceUSD'])
            except StopIteration:
                token0_price_USD = 0

            try:
                token1_price_USD = next(token1_day for token1_day in pool['token1']['tokenDayData'] if token1_day['date'] == day['date'])
                token1_price_USD = Decimal(token1_price_USD['priceUSD'])
            except StopIteration:
                token1_price_USD = 0

            if token0_price_USD == 0:
                token0_price_USD = tokens[pool['token0']['id']]['price']
            if token1_price_USD == 0:
                token1_price_USD = tokens[pool['token1']['id']]['price']

            # inverted because using token1, since token1's getAmountDelta is easier to deal with

            try:
                low = 1 / Decimal(day['high'])
            except decimal.DivisionByZero:
                low = Decimal(0)
            try:
                high = 1 / Decimal(day['low'])
            except decimal.DivisionByZero:
                high = low / Decimal(0.9) * Decimal(1.1)

            mid = Decimal((high + low) / 2)

            # limit range if too large
            # print("high", high)
            # print("low ", low)
            # print("range too large", high > (mid * Decimal(1.1)))
            if (high > (mid * Decimal(1.1))):
                high = mid * Decimal(1.1)
                low = mid * Decimal(0.9)

            high_ratio = high.as_integer_ratio()
            low_ratio = low.as_integer_ratio()
            high_sqrt_x96 = math.isqrt(high_ratio[0] * x96 * x96 // high_ratio[1])
            low_sqrt_x96 = math.isqrt(low_ratio[0] * x96 * x96 // low_ratio[1])

            # expand if range <1 tick spacing
            if (high_sqrt_x96 > 0 and low_sqrt_x96 > 0):
                tick_upper = get_tick_at_sqrt_ratio(high_sqrt_x96)
                tick_lower = get_tick_at_sqrt_ratio(low_sqrt_x96)
                if (tick_upper - tick_lower < TICK_SPACINGS[pool['feeTier']]):
                    tick_mid = (tick_upper + tick_lower) // 2
                    tick_upper = tick_mid + TICK_SPACINGS[pool['feeTier']] // 2
                    tick_lower = tick_mid - TICK_SPACINGS[pool['feeTier']] // 2
                    high_sqrt_x96 = get_sqrt_ratio_at_tick(tick_upper)
                    low_sqrt_x96 = get_sqrt_ratio_at_tick(tick_lower)
                # print("tick_upper", tick_upper)
                # print("tick_lower", tick_lower)

            token1_in_range = int(day['liquidity']) * (high_sqrt_x96 - low_sqrt_x96) // x96
            day_usd_in_range = (token1_in_range * token1_price_USD / 10**int(pool['token1']['decimals'])) * 2  # assume symmetrical for estimation
            # print(pool['token1']['symbol'])
            # print("TVL USD", Decimal(day['tvlUSD']))
            # print("adjusted USD in range", usd_in_range)
            # print("adjusted higher than actual", usd_in_range > Decimal(day['tvlUSD']))
            # print("high_sqrt_x96", high_sqrt_x96)
            # print("low_sqrt_x96 ", low_sqrt_x96)
            # print("day liquidity", (day['liquidity']))
            # print("current liq  ", pool['liquidity'])
            # print("token1_in_range", token1_in_range)
            # print("token1 price", token1_price_USD)

            if (day_usd_in_range > Decimal(day['tvlUSD'])):
                day_usd_in_range = Decimal(day['tvlUSD'])

            pool['feesUSD'] += float(day['feesUSD'])
            pool['projectedFees']['tokens'][pool['token0']['id']] += int(float(day['volumeToken0']) * int(pool['feeTier']) / 1e6 * 10**token0['decimals'] * fee_distribution['veRam'])
            pool['projectedFees']['tokens'][pool['token1']['id']] += int(float(day['volumeToken1']) * int(pool['feeTier']) / 1e6 * 10**token1['decimals'] * fee_distribution['veRam'])
            usd_in_range += float(day_usd_in_range)

        pool['averageUsdInRange'] = usd_in_range / len(valid_days) if len(valid_days) > 0 else 1

        # apr is in %s, 20% goes to users, 80% goes to veRAM and treasury
        try:
            pool['feeApr'] = pool['feesUSD'] / usd_in_range * 100 * fee_distribution['lp']
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

    ## placeholder for stablecoin list, move to appropiate place
    ## LOOSE_STABLECOINS = ["gDAI", "LUSD", "ERN", "DOLA", "MAI"]
    ## STABLECOINS = ["USDC", "USDC.e", "USDT", "FRAX", "DAI"]

    # calculate APRs
    for pool_address, pool in pools.items():

        # calculate LP APR
        totalUSD = 0
        for token_address in pool['gauge']['rewardTokens']:
            # reward rate reported by gauge contracts are already normalized to total unboosted liquidity
            totalUSD += _reward_rates[pool_address][token_address] * 24 * 60 * 60 * tokens[token_address]['price'] / 10 ** tokens[token_address][
                'decimals']

        # lp apr estimate uses current tick +-5%, +-0.5%, or +-0.1%
        position_usd = 0
        if (pool['price'] > 0):
            token0 = tokens[pool['token0']['id']]
            token1 = tokens[pool['token1']['id']]
          
            [position_token0_amount, position_token1_amount] = token_amounts_from_current_price(pool['sqrtPrice'], 500, pool['liquidity'])
            position_usd = (position_token0_amount * token0['price'] / 10**token0['decimals']) + (position_token1_amount * token1['price'] / 10**token1['decimals'])

            # TODO: Make this prettier
            # make range smaller if it's greater than tvl, might be stables pool
            if (position_usd > pool['tvl']):
                [position_token0_amount, position_token1_amount] = token_amounts_from_current_price(pool['sqrtPrice'], 50, pool['liquidity'])
                position_usd = (position_token0_amount * token0['price'] / 10**token0['decimals']) + (position_token1_amount * token1['price'] / 10**token1['decimals'])

                # make range smaller if it's greater than tvl, might be stables pool
                if (position_usd > pool['tvl']):
                    [position_token0_amount, position_token1_amount] = token_amounts_from_current_price(pool['sqrtPrice'], 10, pool['liquidity'])
                    position_usd = (position_token0_amount * token0['price'] / 10**token0['decimals']) + (position_token1_amount * token1['price'] / 10**token1['decimals'])

                    if (position_usd > pool['tvl']):
                        position_usd = pool['tvl']

        pool['lpApr'] = (totalUSD * 36500 / (position_usd if position_usd > 0 else 1)) + (pool['feeApr'] /50)
        pool['lpAprOld'] = 4 * totalUSD * 36500 / (pool['tvl'] if pool['tvl'] > 0 else 1)
        # print("totalUSD", totalUSD)

        # calculate vote APR
        if pool['totalVeShareByPeriod'] > 0:
            totalUSD = 0
            projected_fees_usd = 0
            for token_address, amount in pool['voteBribes'].items():
                totalUSD += amount * tokens[token_address]['price'] / 10 ** tokens[token_address]['decimals']
            pool['voteApr'] = totalUSD / 7 * 36500 / (pool['totalVeShareByPeriod'] * tokens[RAM_ADDRESS]['price'] / 1e18)
            for token_address, amount in pool['projectedFees']['tokens'].items():
                projected_fees_usd += amount * tokens[token_address]['price'] / 10 ** tokens[token_address]['decimals']
            pool['projectedFees']['apr'] = projected_fees_usd / 7 * 36500 / (pool['totalVeShareByPeriod'] * tokens[RAM_ADDRESS]['price'] / 1e18)
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
