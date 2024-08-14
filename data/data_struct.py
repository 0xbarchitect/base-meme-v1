import os
from decimal import Decimal

class Pair:
    def __init__(self, token, token_index, address, reserve_token=0, reserve_eth=0, created_at=0, inspect_attempts=0, has_buy=False, has_sell=False, creator=None) -> None:
        self.token = token
        self.token_index = token_index
        self.address = address
        self.reserve_token = reserve_token
        self.reserve_eth = reserve_eth
        self.created_at = created_at
        self.inspect_attempts = inspect_attempts
        self.has_buy = False
        self.has_sell = False
        self.creator = creator

    def price(self):
        if self.reserve_token != 0 and self.reserve_eth != 0:
            return Decimal(self.reserve_eth) / Decimal(self.reserve_token)
        return 0

    def  __str__(self) -> str:
        return f"Pair {self.address} token {self.token} tokenIndex {self.token_index} reserve_token {self.reserve_token} reserve_eth {self.reserve_eth} creator {self.creator} createdAt {self.created_at} inspectAttempts {self.inspect_attempts}"

class BlockData:
    def __init__(self, block_number, block_timestamp, base_fee, gas_used, gas_limit, pairs=[], inventory=[], watchlist=[]) -> None:
        self.block_number = block_number
        self.block_timestamp = block_timestamp
        self.base_fee = base_fee
        self.gas_used = gas_used
        self.gas_limit = gas_limit
        self.pairs = pairs
        self.inventory = inventory
        self.watchlist = watchlist

    def __str__(self) -> str:
        return f"""
        Block #{self.block_number} timestamp {self.block_timestamp} baseFee {self.base_fee} gasUsed {self.gas_used} gasLimit {self.gas_limit}
        Pairs created {len(self.pairs)} Inventory {len(self.inventory)} Watchlist {len(self.watchlist)}
        """

class ExecutionOrder:
    def __init__(self, block_number, block_timestamp, pair: Pair, amount_in, amount_out_min, is_buy, signer=None, bot=None) -> None:
        self.block_number = block_number
        self.block_timestamp = block_timestamp
        self.pair = pair
        self.amount_in = amount_in
        self.amount_out_min = amount_out_min
        self.is_buy = is_buy
        self.signer = signer
        self.bot = bot

    def __str__(self) -> str:
        return f"Execution order block #{self.block_number} pair {self.pair} amountIn {self.amount_in} amountOutMin {self.amount_out_min} signer {self.signer} bot {self.bot} isBuy {self.is_buy}"
    
class ExecutionAck:
    def __init__(self, lead_block, block_number, tx_hash, tx_status, pair: Pair, amount_in, amount_out, is_buy, signer=None, bot=None) -> None:
        self.lead_block = lead_block
        self.block_number = block_number
        self.tx_hash = tx_hash
        self.tx_status = tx_status
        self.pair = pair
        self.amount_in = amount_in
        self.amount_out = amount_out
        self.is_buy = is_buy
        self.signer = signer
        self.bot = bot

    def __str__(self) -> str:
        return f"""
        Execution acknowledgement lead #{self.lead_block} realized #{self.block_number} tx {self.tx_hash} status {self.tx_status}
        Pair {self.pair} AmountIn {self.amount_in} AmountOut {self.amount_out} Signer {self.signer} Bot {self.bot} IsBuy {self.is_buy}
        """
from enum import IntEnum

class ReportDataType(IntEnum):
    BLOCK = 0
    EXECUTION = 1
    WATCHLIST_ADDED = 2
    WATCHLIST_REMOVED = 3
    BLACKLIST_BOOTSTRAP = 4
    BLACKLIST_ADDED = 5

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
    def __init__(self, pair, amount_in, amount_out, slippage, amount_token=0) -> None:
        self.pair = pair
        self.amount_in = amount_in
        self.amount_out = amount_out
        self.slippage = slippage
        self.amount_token = amount_token

    def __str__(self) -> str:
        return f"Simulation result {self.pair} slippage {self.slippage} amountIn {self.amount_in} amountOut {self.amount_out} amountToken {self.amount_token}"
    
class FilterLogsType(IntEnum):
    PAIR_CREATED = 0
    SYNC = 1
    SWAP = 2

class FilterLogs:
    def __init__(self, type: FilterLogsType, data) -> None:
        self.type = type
        self.data = data
    
    def __str__(self) -> str:
        return f"FilterLogs type {self.type} data {self.data}"
    
class Position:
    def __init__(self, pair, amount, buy_price, start_time, pnl=0, signer=None, bot=None) -> None:
        self.pair = pair
        self.amount = amount
        self.buy_price = buy_price
        self.start_time = start_time
        self.pnl = pnl
        self.signer = signer
        self.bot = bot

    def __str__(self) -> str:
        return f"Position {self.pair} amount {self.amount} buyPrice {self.buy_price} startTime {self.start_time} signer {self.signer} bot {self.bot} pnl {self.pnl}"
    
class TxStatus(IntEnum):
    FAILED = 0
    SUCCESS = 1