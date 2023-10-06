from typing import List

from web3 import Web3

from multicall_backtest import Call
from multicall_backtest.constants import MULTICALL_ADDRESSES


class Multicall:
    def __init__(self, calls: List[Call], chain=None, strict=False, _w3=None, block="latest"):
        self.calls = calls
        self.chain = chain
        self.strict = strict
        self.w3 = _w3
        self.block = block

    def __call__(self):
        aggregate = Call(
            MULTICALL_ADDRESSES[self.w3.eth.chain_id],
            "aggregate((address,bytes)[],bool)(uint256,(bool,bytes)[])",
            None,
            chain=self.chain,
            _w3=self.w3,
            block=self.block,
        )
        args = [[[call.target, call.data] for call in self.calls], self.strict]
        block, outputs = aggregate(args)
        result = []

        for call, output in zip(self.calls, outputs):
            if output[0] == True:
                result.append(call.decode_output(output[1]))

        return result
