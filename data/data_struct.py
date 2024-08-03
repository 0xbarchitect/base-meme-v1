import os
from decimal import Decimal

class Pair:
    def __init__(self, token, token_index, address, reserveToken=0, reserveETH=0) -> None:
        self.token = token
        self.token_index = token_index
        self.address = address
        self.reserveToken = reserveToken
        self.reserveETH = reserveETH

    def price(self):
        if self.reserveToken != 0 and self.reserveETH != 0:
            return Decimal(self.reserveETH) / Decimal(self.reserveToken)
        return 0

    def  __str__(self) -> str:
        return f"Pair {self.address} token {self.token} tokenIndex {self.token_index} reserveToken {self.reserveToken} reserveETH {self.reserveETH}"

class BlockData:
    def __init__(self, block_number, block_timestamp, base_fee, gas_used, gas_limit, pairs = [], inventory = []) -> None:
        self.block_number = block_number
        self.block_timestamp = block_timestamp
        self.base_fee = base_fee
        self.gas_used = gas_used
        self.gas_limit = gas_limit
        self.pairs = pairs
        self.inventory = inventory

    def __str__(self) -> str:
        return f"""
        Block #{self.block_number} timestamp {self.block_timestamp} baseFee {self.base_fee} gasUsed {self.gas_used} gasLimit {self.gas_limit}
        Pairs created {len(self.pairs)} Inventory {len(self.inventory)}
        """

class ExecutionOrder:
    def __init__(self, block_number, block_timestamp, pair: Pair, amount_in, amount_out_min, is_buy) -> None:
        self.block_number = block_number
        self.block_timestamp = block_timestamp
        self.pair = pair
        self.amount_in = amount_in
        self.amount_out_min = amount_out_min
        self.is_buy = is_buy

    def __str__(self) -> str:
        return f"""
        Execution order block #{self.block_number} token {self.token} amountIn {self.amount_in} amountOutMin {self.amount_out_min} isBuy {self.is_buy}
        """
    
class ExecutionAck:
    def __init__(self, lead_block, block_number, tx_hash, tx_status, pair: Pair, amount_in, amount_out, is_buy) -> None:
        self.lead_block = lead_block
        self.block_number = block_number
        self.tx_hash = tx_hash
        self.tx_status = tx_status
        self.pair = pair
        self.amount_in = amount_in
        self.amount_out = amount_out
        self.is_buy = is_buy

    def __str__(self) -> str:
        return f"""
        Execution acknowledgement lead #{self.lead_block} realized #{self.block_number} tx {self.tx_hash} status {self.tx_status}
        Pair {self.pair} AmountIn {self.amount_in} AmountOut {self.amount_out} IsBuy {self.is_buy}
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

class W3Account:
    def __init__(self, w3_account, private_key, nonce) -> None:
        self.w3_account = w3_account
        self.private_key = private_key
        self.nonce = nonce

class SimulationResult:
    def __init__(self, pair, amount_in, amount_out, slippage) -> None:
        self.pair = pair
        self.amount_in = amount_in
        self.amount_out = amount_out
        self.slippage = slippage

    def __str__(self) -> str:
        return f"Simulation result {self.pair} slippage {self.slippage} amount in {self.amount_in} amount out {self.amount_out}"
    
class FilterLogsType(IntEnum):
    PAIR_CREATED = 0
    SYNC = 1

class FilterLogs:
    def __init__(self, type: FilterLogsType, data) -> None:
        self.type = type
        self.data = data
    
    def __str__(self) -> str:
        return f"FilterLogs type {self.type} data {self.data}"
    
class Position:
    def __init__(self, pair, amount, buy_price, start_time) -> None:
        self.pair = pair
        self.amount = amount
        self.buy_price = buy_price
        self.start_time = start_time

    def __str__(self) -> str:
        return f"Position {self.pair} amount {self.amount} buy price {self.buy_price} start time {self.start_time}"
    
class TxStatus(IntEnum):
    PENDING = 0
    SUCCESS = 1
    FAILED = -1