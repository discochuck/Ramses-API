from multicall_backtest import Call, Multicall
from web3 import Web3

RAM = "0xAAA6C1E32C55A7Bfa8066A6FAE9b42650F262418"
XRAM = "0xAAA1eE8DC1864AE49185C368e8c64Dd780a50Fb7"
BACKTEST_LENS = "0xf12eC3419CBaa7F63A46610ec439a9E307874b1c"
LENS_ABI = '[{"inputs":[],"name":"RAM","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"owner","type":"address"}],"name":"clDataOfOwner","outputs":[{"components":[{"internalType":"uint256","name":"nft_id","type":"uint256"},{"internalType":"address","name":"token0","type":"address"},{"internalType":"address","name":"token1","type":"address"},{"internalType":"string","name":"symbol0","type":"string"},{"internalType":"string","name":"symbol1","type":"string"},{"internalType":"uint24","name":"fee","type":"uint24"},{"internalType":"address","name":"pool_address","type":"address"},{"internalType":"address","name":"gauge_address","type":"address"},{"internalType":"uint256","name":"pool_liquidity","type":"uint256"},{"internalType":"uint256","name":"pool_boostedliq","type":"uint256"},{"internalType":"uint256","name":"boostedliq","type":"uint256"},{"internalType":"int24","name":"tick","type":"int24"},{"internalType":"int24","name":"tick_lower","type":"int24"},{"internalType":"int24","name":"tick_upper","type":"int24"},{"internalType":"uint128","name":"liquidity","type":"uint128"},{"internalType":"uint256","name":"earned","type":"uint256"},{"internalType":"uint256","name":"earned_xram","type":"uint256"}],"internalType":"structClData[]","name":"","type":"tuple[]"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"uint256","name":"nft_id","type":"uint256"}],"name":"getClData","outputs":[{"components":[{"internalType":"uint256","name":"nft_id","type":"uint256"},{"internalType":"address","name":"token0","type":"address"},{"internalType":"address","name":"token1","type":"address"},{"internalType":"string","name":"symbol0","type":"string"},{"internalType":"string","name":"symbol1","type":"string"},{"internalType":"uint24","name":"fee","type":"uint24"},{"internalType":"address","name":"pool_address","type":"address"},{"internalType":"address","name":"gauge_address","type":"address"},{"internalType":"uint256","name":"pool_liquidity","type":"uint256"},{"internalType":"uint256","name":"pool_boostedliq","type":"uint256"},{"internalType":"uint256","name":"boostedliq","type":"uint256"},{"internalType":"int24","name":"tick","type":"int24"},{"internalType":"int24","name":"tick_lower","type":"int24"},{"internalType":"int24","name":"tick_upper","type":"int24"},{"internalType":"uint128","name":"liquidity","type":"uint128"},{"internalType":"uint256","name":"earned","type":"uint256"},{"internalType":"uint256","name":"earned_xram","type":"uint256"}],"internalType":"structClData","name":"","type":"tuple"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"uint256[]","name":"nft_ids","type":"uint256[]"}],"name":"getClDataBatched","outputs":[{"components":[{"internalType":"uint256","name":"nft_id","type":"uint256"},{"internalType":"address","name":"token0","type":"address"},{"internalType":"address","name":"token1","type":"address"},{"internalType":"string","name":"symbol0","type":"string"},{"internalType":"string","name":"symbol1","type":"string"},{"internalType":"uint24","name":"fee","type":"uint24"},{"internalType":"address","name":"pool_address","type":"address"},{"internalType":"address","name":"gauge_address","type":"address"},{"internalType":"uint256","name":"pool_liquidity","type":"uint256"},{"internalType":"uint256","name":"pool_boostedliq","type":"uint256"},{"internalType":"uint256","name":"boostedliq","type":"uint256"},{"internalType":"int24","name":"tick","type":"int24"},{"internalType":"int24","name":"tick_lower","type":"int24"},{"internalType":"int24","name":"tick_upper","type":"int24"},{"internalType":"uint128","name":"liquidity","type":"uint128"},{"internalType":"uint256","name":"earned","type":"uint256"},{"internalType":"uint256","name":"earned_xram","type":"uint256"}],"internalType":"structClData[]","name":"","type":"tuple[]"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"initialize","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"owner","type":"address"}],"name":"nftIdsOfOwner","outputs":[{"internalType":"uint256[]","name":"","type":"uint256[]"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"ramsesClFactory","outputs":[{"internalType":"contractIRamsesClFactory","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"ramsesNfpManager","outputs":[{"internalType":"contractIRamsesNfpManager","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"ramsesVoter","outputs":[{"internalType":"contractIRamsesVoter","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"xRAM","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"}]'

web3 = Web3(Web3.HTTPProvider("https://arb1.arbitrum.io/rpc"))


def multichunker(call_groups, chunks=1, _block="latest"):
    flattened_calls = [call for group in call_groups for call in group]  # flatten 2d list
    chunk_size = max(1, len(flattened_calls) // chunks)

    # List to hold all results
    all_results = []

    for i in range(0, len(flattened_calls), chunk_size):
        chunk_calls = flattened_calls[i : i + chunk_size]
        multicall_result = Multicall(chunk_calls, _w3=web3, block=_block)()

        # Store the results in the all_results list
        all_results.extend(multicall_result)

    result = [
        all_results[i * len(group) : (i + 1) * len(group)] for i, group in enumerate(call_groups)
    ]  # deflatten back to original

    return result


def get_arbi_block_time():
    LAST_BLOCKS = 10_000
    block_now = web3.eth.get_block("latest")
    block_then = web3.eth.get_block(block_now.number - LAST_BLOCKS)
    average_block_time = (block_now.timestamp - block_then.timestamp) / LAST_BLOCKS

    return average_block_time


def get_ram_earnt_per_day_estimation(data, current_block, block_diff=250):
    # APR estimation based on real data
    nft_ids = [x[0] for x in data]
    gauges = [x[7] for x in data]
    earneds_now = [x[15] for x in data]
    earneds_xram_now = [x[16] for x in data]
    earneds_now_total = [a + b for a, b in zip(earneds_now, earneds_xram_now)]

    blocks_per_day = 24 * 60 * 60 / get_arbi_block_time()

    earneds_past, earneds_xram_past = multichunker(
        [
            [Call(g, ["earned(address,uint256)(uint256)", RAM, id]) for g, id in zip(gauges, nft_ids)],
            [Call(g, ["earned(address,uint256)(uint256)", XRAM, id]) for g, id in zip(gauges, nft_ids)],
        ],
        _block=current_block - block_diff,
    )
    earneds_past_total = [a + b for a, b in zip(earneds_past, earneds_xram_past)]

    earneds_per_block = [
        (earnedB - earnedA) / block_diff for earnedA, earnedB in zip(earneds_past_total, earneds_now_total)
    ]
    rams_per_day = [earned_per_block * blocks_per_day / 1e18 for earned_per_block in earneds_per_block]

    return rams_per_day


def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def get_backtested_cl_data(nft_ids):
    contract = web3.eth.contract(address=BACKTEST_LENS, abi=LENS_ABI)
    # sync all calls on same block
    current_block = web3.eth.block_number

    # Chunk the nft_ids into batches
    chunk_size = 40
    nft_id_chunks = list(chunks(nft_ids, chunk_size))
    all_data = []

    # For each chunk, get the data and append to all_data
    for nft_chunk in nft_id_chunks:
        data_chunk = contract.functions.getClDataBatched(nft_chunk).call(block_identifier=current_block)
        all_data.extend(data_chunk)

    apr_estimations = get_ram_earnt_per_day_estimation(all_data, current_block=current_block)

    result = []
    for i, pos in enumerate(all_data):
        (
            nft_id,
            token0,
            token1,
            symbol0,
            symbol1,
            fee,
            pool_address,
            gauge_address,
            pool_liquidity,
            pool_boostedliq,
            boosted_liq,
            tick,
            tick_lower,
            tick_upper,
            liquidity,
            earned,
            earned_xram,
        ) = pos

        result.append(
            {
                "token0": token0,
                "token1": token1,
                "symbol0": symbol0,
                "symbol1": symbol1,
                "fee": fee,
                "min_tick": tick_lower,
                "max_tick": tick_upper,
                "liquidity": liquidity,
                "pool_liquidity": pool_liquidity,
                "pool_address": pool_address,
                "nft_id": nft_id,
                "tick": tick,
                "gauge_address": gauge_address,
                "boost": boosted_liq / liquidity + 1 if liquidity else 0,
                "earned": earned,
                "earned_xram": earned_xram,
                "boosted_liq": boosted_liq,
                "pool_boostedliq": pool_boostedliq,
                "ram_per_day": apr_estimations[i],
            }
        )

    return result


print(get_backtested_cl_data([8571]))
