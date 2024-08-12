import os
import logging
from pathlib import Path
import json

import asyncio
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
import threading
import websockets

from web3 import AsyncWeb3, Web3
from web3.providers import WebsocketProviderV2, HTTPProvider

import sys # for testing
sys.path.append('..')

from library import Singleton
from data import BlockData, Pair, ExecutionAck, FilterLogs, FilterLogsType, ReportData, ReportDataType, TxStatus
from helpers import async_timer_decorator, load_abi, timer_decorator

RESERVE_ETH_MIN_THRESHOLD=float(os.environ.get('RESERVE_ETH_MIN_THRESHOLD'))
RESERVE_ETH_MAX_THRESHOLD=float(os.environ.get('RESERVE_ETH_MAX_THRESHOLD'))
BUYSELL_INSPECT_INTERVAL_SECONDS=int(os.environ.get('BUYSELL_INSPECT_INTERVAL_SECONDS'))

WATCHLIST_CAPACITY=10
glb_lock = threading.Lock()

class BlockWatcher(metaclass=Singleton):
    def __init__(self, https_url, wss_url, block_broker, report_broker, factory_address, factory_abi, weth_address, pair_abi) -> None:
        self.wss_url = wss_url
        self.block_broker = block_broker
        self.report_broker = report_broker

        self.factory_address = factory_address
        self.factory_abi = factory_abi
        self.weth_address = weth_address
        self.pair_abi = pair_abi

        self.inventory = []
        self.watchlist = []
        self.w3 = Web3(Web3.HTTPProvider(https_url))
        self.factory = self.w3.eth.contract(address=self.factory_address, abi=self.factory_abi)

    async def listen_block(self):
        global glb_lock

        async for w3Async in AsyncWeb3.persistent_websocket(WebsocketProviderV2(self.wss_url)):
            try:
                logging.info(f"websocket connected...")

                subscription_id = await w3Async.eth.subscribe("newHeads")
                async for response in w3Async.ws.process_subscriptions():
                    logging.debug(f"new block {response}\n")
                    
                    block_number = Web3.to_int(hexstr=response['result']['number'])
                    block_timestamp = Web3.to_int(hexstr=response['result']['timestamp'])
                    base_fee = Web3.to_int(hexstr=response['result']['baseFeePerGas'])
                    gas_used = Web3.to_int(hexstr=response['result']['gasUsed'])
                    gas_limit = Web3.to_int(hexstr=response['result']['gasLimit'])

                    logging.debug(f"block number {block_number} timestamp {block_timestamp}")

                    for idx,pair in enumerate(self.watchlist):
                        if block_timestamp-pair.created_at>BUYSELL_INSPECT_INTERVAL_SECONDS:
                            with glb_lock:
                                self.watchlist.pop(idx)
                            logging.info(f"WATCHER remove {pair} from watchlist due to timeout")

                    pairs = self.filter_log_in_block(block_number, block_timestamp)

                    logging.debug(f"found pairs {pairs}")
                    for pair in pairs:
                        if pair.reserve_eth>RESERVE_ETH_MIN_THRESHOLD and pair.reserve_eth<RESERVE_ETH_MAX_THRESHOLD and len(self.watchlist)<WATCHLIST_CAPACITY:
                            with glb_lock:
                                self.watchlist.append(pair)
                            logging.info(f"WATCHER add {pair} to watchlist")

                    self.block_broker.put(BlockData(
                        block_number,
                        block_timestamp,
                        base_fee,
                        gas_used,
                        gas_limit,
                        pairs,
                        self.inventory,
                        self.watchlist,
                    ))

            except websockets.ConnectionClosed:
                logging.error(f"websocket connection closed, reconnect...")
                continue

    @timer_decorator
    def get_reserves(self, pair_address):
        contract = self.w3.eth.contract(address=pair_address, abi=self.pair_abi)
        reserves = contract.functions.getReserves().call()
        return reserves
    
    @timer_decorator
    def filter_log_in_block(self, block_number, block_timestamp):
        #block_number = 17918019 # TODO

        def filter_paircreated_log(block_number):
            pair_created_logs = self.factory.events.PairCreated().get_logs(
                fromBlock = block_number,
                toBlock = block_number,
            )

            pairs = []
            if pair_created_logs != ():
                for log in pair_created_logs:
                    logging.debug(f"found pair created {log}")
                    if log['args']['token0'].lower() == self.weth_address.lower() or log['args']['token1'].lower() == self.weth_address.lower():
                        pairs.append(Pair(
                            token=log['args']['token0'] if log['args']['token1'].lower() == self.weth_address.lower() else log['args']['token1'],
                            token_index=0 if log['args']['token1'].lower() == self.weth_address.lower() else 1,
                            address=log['args']['pair'],
                            created_at=block_timestamp,
                        ))

            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                future_to_pair = {executor.submit(self.get_reserves, pair.address): idx for idx,pair in enumerate(pairs)}
                for future in concurrent.futures.as_completed(future_to_pair):
                    idx = future_to_pair[future]
                    try:
                        result = future.result()
                        logging.debug(f"getReserves {pairs[idx].address} result {result}")
                        pairs[idx].reserve_token = Web3.from_wei(result[0],'ether') if pairs[idx].token_index == 0 else Web3.from_wei(result[1], 'ether')
                        pairs[idx].reserve_eth = Web3.from_wei(result[1],'ether') if pairs[idx].token_index == 0 else Web3.from_wei(result[0], 'ether')
                    except Exception as e:
                        logging.error(f"getReserves {pair} error {e}")

            return FilterLogs(
                type=FilterLogsType.PAIR_CREATED,
                data=pairs,
            )

        def filter_sync_log(pair, block_number) -> None:
            pair_contract = self.w3.eth.contract(address=pair, abi=self.pair_abi)
            sync_logs = pair_contract.events.Sync().get_logs(
                fromBlock = block_number,
                toBlock = block_number,
            )

            return FilterLogs(
                type=FilterLogsType.SYNC,
                data=sync_logs,
            )
        
        def filter_swap_log(pair, block_number) -> None:
            pair_contract = self.w3.eth.contract(address=pair, abi=self.pair_abi)
            sync_logs = pair_contract.events.Swap().get_logs(
                fromBlock = block_number,
                toBlock = block_number,
            )

            return FilterLogs(
                type=FilterLogsType.SWAP,
                data=sync_logs,
            )

        pairs = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            future_to_contract = {executor.submit(filter_paircreated_log, block_number): self.factory.address}

            if len(self.inventory)>0:
                for pair in self.inventory:
                    future_to_contract[executor.submit(filter_sync_log, pair.address, block_number)] = pair.address

            if len(self.watchlist)>0:
                for pair in self.watchlist:
                    future_to_contract[executor.submit(filter_swap_log, pair.address, block_number)] = pair.address

            for future in concurrent.futures.as_completed(future_to_contract):
                contract = future_to_contract[future]
                try:
                    result = future.result()
                    logging.debug(f"contract {contract} result {result}")

                    if result is not None and isinstance(result, FilterLogs):
                        if result.type == FilterLogsType.PAIR_CREATED:
                            if len(result.data)>0:
                                pairs = result.data

                        elif result.type == FilterLogsType.SYNC:
                            if result.data != ():
                                for log in result.data:
                                    logging.debug(f"sync {log}")

                                    for pair in self.inventory:
                                        if pair.address == contract:
                                            logging.info(f"update reserves for inventory {pair.address}")
                                            pair.reserve_token = Web3.from_wei(log['args']['reserve0'], 'ether') if pair.token_index==0 else Web3.from_wei(log['args']['reserve1'], 'ether')
                                            pair.reserve_eth = Web3.from_wei(log['args']['reserve1'], 'ether') if pair.token_index==0 else Web3.from_wei(log['args']['reserve0'], 'ether')
                            
                        elif result.type == FilterLogsType.SWAP:
                            if result.data != ():
                                for log in result.data:

                                    for pair in self.watchlist:
                                        if pair.address == contract:
                                            logging.info(f"{pair} swap event {log}")
                                            if pair.token_index == 0 and Web3.from_wei(log['args']['amount1In'])>0 and Web3.from_wei(log['args']['amount0Out'])>0:
                                                pair.has_buy = True
                                            elif pair.token_index == 0 and Web3.from_wei(log['args']['amount0In'])>0 and Web3.from_wei(log['args']['amount1Out'])>0:
                                                pair.has_sell = True
                                            elif pair.token_index == 1 and Web3.from_wei(log['args']['amount0In'])>0 and Web3.from_wei(log['args']['amount1Out'])>0:
                                                pair.has_buy = True
                                            elif pair.token_index == 1 and Web3.from_wei(log['args']['amount1In'])>0 and Web3.from_wei(log['args']['amount0Out'])>0:
                                                pair.has_sell = True

                except Exception as e:
                    logging.error(f"contract {contract} error {e}")
        
        return pairs
    
    async def listen_report(self):
        global glb_lock

        def add_pair_to_watchlist(pair):
            # sync current reserves
            result = self.get_reserves(pair.address)
            logging.info(f"get reserves {pair} result {result}")

            pair.reserve_token = Web3.from_wei(result[0],'ether') if pair.token_index == 0 else Web3.from_wei(result[1], 'ether')
            pair.reserve_eth = Web3.from_wei(result[1],'ether') if pair.token_index == 0 else Web3.from_wei(result[0], 'ether')

            with glb_lock:
                self.inventory.append(pair)
            logging.info(f"WATCHER add pair {pair} to watching {len(self.inventory)}")

        def remove_pair_from_watchlist(pair):
            for idx,pr in enumerate(self.inventory):
                if pr.address == pair.address:
                    with glb_lock:
                        self.inventory.pop(idx)
                        logging.info(f"WATCHER remove pair {pair} from watching {len(self.inventory)}")

        while True:
            report = await self.report_broker.coro_get()

            if report is not None and isinstance(report, ExecutionAck) and report.pair is not None:
                logging.info(f"WATCHER receive report {report}")
                if report.is_buy and report.tx_status == TxStatus.SUCCESS:
                    if report.pair.address not in [pair.address for pair in self.inventory]:
                        add_pair_to_watchlist(report.pair)
                else:
                    remove_pair_from_watchlist(report.pair)

    
    async def main(self):
        await asyncio.gather(
            self.listen_block(),
            self.listen_report(),
        )

if __name__ == "__main__":     
    from dotenv import load_dotenv
    load_dotenv()
    logging.basicConfig(level=logging.INFO)

    FACTORY_ABI = load_abi(f"{os.path.dirname(__file__)}/../contracts/abis/UniV2Factory.abi.json")
    PAIR_ABI = load_abi(f"{os.path.dirname(__file__)}/../contracts/abis/UniV2Pair.abi.json")
    
    import aioprocessing

    block_broker = aioprocessing.AioQueue()
    report_broker = aioprocessing.AioQueue()

    report_broker.put(ExecutionAck(
        lead_block=0,
        block_number=0,
        tx_hash='0xabc',
        tx_status=1,
        pair=Pair(
            address='0x9694DE8E322212ECf96e9276B8ab5c0b2f7a3a24',            
            token='0x2E5387d321b358e8161C8F2ec00436006A7D07E2',
            token_index=0,
        ),
        amount_in=1,
        amount_out=1,
        is_buy=True,
    ))

    # report_broker.put(ExecutionAck(
    #     lead_block=0,
    #     block_number=0,
    #     tx_hash='0xabc',
    #     tx_status=1,
    #     pair=Pair(
    #         token='0xabc',
    #         token_index=1,
    #         address='0xe1D2f11C0a186A3f332967b5135FFC9a4568B15d',
    #     ),
    #     amount_in=1,
    #     amount_out=1,
    #     is_buy=True,
    # ))

    # report_broker.put(ExecutionAck(
    #     lead_block=0,
    #     block_number=0,
    #     tx_hash='0xabc',
    #     tx_status=1,
    #     pair=Pair(
    #         token='0xabc',
    #         token_index=1,
    #         address='0xe1D2f11C0a186A3f332967b5135FFC9a4568B15d',
    #     ),
    #     amount_in=1,
    #     amount_out=1,
    #     is_buy=False,
    # ))

    block_watcher = BlockWatcher(
                                https_url=os.environ.get('HTTPS_URL'),
                                wss_url=os.environ.get('WSS_URL'),
                                block_broker=block_broker,
                                report_broker=report_broker,
                                factory_address=os.environ.get('FACTORY_ADDRESS'),
                                factory_abi=FACTORY_ABI,
                                weth_address=os.environ.get('WETH_ADDRESS'),
                                pair_abi=PAIR_ABI,
                                )
    
    async def run_all():
        async def receive_block():
            while True:
                block_data = await block_broker.coro_get()
                logging.info(f"receive block {block_data}")
                if len(block_data.pairs)>0:
                    logging.info(f"pair {block_data.pairs[0]}")
                #logging.info(f"block inventory {block_data.inventory[0]}")

        await asyncio.gather(block_watcher.main(), receive_block())
    
    #asyncio.run(block_watcher.main())
    asyncio.run(run_all())


    