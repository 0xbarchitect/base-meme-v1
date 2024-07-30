import os

class Pair:
    def __init__(self, token0, token1, address) -> None:
        self.token0 = token0
        self.token1 = token1
        self.address = address

    def  __str__(self) -> str:
        return f"{self.address}"

class BlockData:
    def __init__(self, block_number, block_timestamp, base_fee, gas_used, gas_limit, pairs) -> None:
        self.block_number = block_number
        self.block_timestamp = block_timestamp
        self.base_fee = base_fee
        self.gas_used = gas_used
        self.gas_limit = gas_limit
        self.pairs = pairs

    def __str__(self) -> str:
        return f"""
        Block #{self.block_number} timestamp {self.block_timestamp} baseFee {self.base_fee} gasUsed {self.gas_used} gasLimit {self.gas_limit}
        Pairs created {len(self.pairs)}
        """

class ExecutionData:
    def __init__(self, block_number, block_timestamp, amount0In, amount1Min = 0) -> None:
        self.block_number = block_number
        self.block_timestamp = block_timestamp
        self.amount0In = amount0In
        self.amount1Min = amount1Min

    def __str__(self) -> str:
        return f"""
        Execution order block #{self.block_number} amount0In {self.amount0In} amount1Min {self.amount1Min}
        """

from enum import IntEnum

class ReportDataType(IntEnum):
    BLOCK = 0
    COUNTER_TRADE = 1

class ReportData:
    def __init__(self, type, data) -> None:
        self.type = type
        self.data = data

    def __str__(self) -> str:
        return f"""
        Report type #{self.type} data {self.data}
        """
    
class SwapNativeForTokenData:
    def __init__(self, lead_block, block_number, tx_hash, sender, amount0_in, amount1_out_min, deadline, status) -> None:
        self.lead_block = lead_block
        self.block_number = block_number
        self.tx_hash = tx_hash
        self.sender = sender
        self.amount0_in = amount0_in
        self.amount1_out_min = amount1_out_min
        self.deadline = deadline
        self.status = status

    def __str__(self) -> str:
        return f"""
        SwapNativeForToken leadBlock #{self.lead_block} block #{self.block_number} tx {self.tx_hash} status {self.status}
        Sender {self.sender} Amount0In {self.amount0_in} Amount1OutMin {self.amount1_out_min} Deadline {self.deadline}
        """

class W3Account:
    def __init__(self, w3_account, private_key, nonce) -> None:
        self.w3_account = w3_account
        self.private_key = private_key
        self.nonce = nonce

class SimulationResult:
    def __init__(self, token, amount_in, amount_out, slippage) -> None:
        self.token = token
        self.amount_in = amount_in
        self.amount_out = amount_out
        self.slippage = slippage

    def __str__(self) -> str:
        return f"Simulation result {self.token} slippage {self.slippage} amount in {self.amount_in} amount out {self.amount_out}"