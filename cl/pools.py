import datetime
import json
from pprint import pprint

from multicall import Multicall, Call
from utils import w3, db, log, RAM_ADDRESS
from cl.subgraph import get_cl_subgraph_tokens, get_cl_subgraph_pools


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
            pool['liquidity'] = float(pool['liquidity'])
            pool['tvl'] = float(pool['totalValueLockedUSD'])
            pool['reserve0'] = float(pool['totalValueLockedToken0'])
            pool['reserve1'] = float(pool['totalValueLockedToken1'])
            pools[pool['id']] = pool

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

    # calculate APRs
    for pool_address, pool in pools.items():
        # calculate vote APR
        if pool['totalVeShareByPeriod'] > 0:
            totalUSD = 0
            for token_address, amount in pool['voteBribes'].items():
                totalUSD += amount * tokens[token_address]['price'] / 10 ** tokens[token_address]['decimals']
            pool['voteApr'] = totalUSD / 7 * 36500 / (pool['totalVeShareByPeriod'] * tokens[RAM_ADDRESS]['price'] / 1e18)
        else:
            pool['voteApr'] = 0

        # calculate LP APR
        if pool['liquidity'] > 0:
            totalUSD = 0
            for token_address in pool['gauge']['rewardTokens']:
                # reward rate reported by gauge contracts are already normalized to total unboosted liquidity
                totalUSD += _reward_rates[pool_address][token_address] * 24 * 60 * 60 * tokens[token_address]['price'] / 10 ** tokens[token_address][
                    'decimals']
            # using TVL is conservative, since not all TVL is in range
            # TODO: only use in range value for APR
            pool['lpApr'] = totalUSD * 36500 / pool['tvl']
        else:
            pool['lpApr'] = 0

    # convert floats to strings
    for pool_address, pool in pools.items():
        for key in pool.keys():
            if isinstance(pool[key], float) or (isinstance(pool[key], int) and not isinstance(pool[key], bool)):
                pool[key] = "{:.18f}".format(pool[key])

        for token_address, amount in pool['voteBribes'].items():
            pool['voteBribes'][token_address] = "{:.18f}".format(amount)

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


if __name__ == '__main__':
    p = get_cl_pools(True)

    pprint(p['pools'])
