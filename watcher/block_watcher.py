import os
import logging
from pathlib import Path
import json

import asyncio
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor

from web3 import AsyncWeb3, Web3
from web3.providers import WebsocketProviderV2, HTTPProvider

import sys # for testing
sys.path.append('..')

from library import Singleton
from data import BlockData, Pair, ExecutionAck, FilterLogs, FilterLogsType
from helpers import async_timer_decorator, load_abi, timer_decorator


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
        self.w3 = Web3(Web3.HTTPProvider(https_url))
        self.factory = self.w3.eth.contract(address=self.factory_address, abi=self.factory_abi)

    async def listen_block(self):
        async with AsyncWeb3.persistent_websocket(
            WebsocketProviderV2(self.wss_url)
        ) as w3Async:
            logging.info(f"websocket connected...")

            subscription_id = await w3Async.eth.subscribe("newHeads")

            async for response in w3Async.ws.process_subscriptions():
                logging.debug(f"new block {response}\n")
                
                block_number = Web3.to_int(hexstr=response['result']['number'])
                block_timestamp = Web3.to_int(hexstr=response['result']['timestamp'])
                base_fee = Web3.to_int(hexstr=response['result']['baseFeePerGas'])
                gas_used = Web3.to_int(hexstr=response['result']['gasUsed'])
                gas_limit = Web3.to_int(hexstr=response['result']['gasLimit'])

                logging.info(f"block number {block_number} timestamp {block_timestamp}")

                pairs = self.filter_log_in_block(block_number)

                logging.debug(f"found pairs {pairs}")

                self.block_broker.put(BlockData(
                    block_number,
                    block_timestamp,
                    base_fee,
                    gas_used,
                    gas_limit,
                    pairs,
                    self.inventory,
                ))

    @timer_decorator
    def filter_log_in_block(self, block_number):
        #block_number = 17885237 # TODO

        def filter_paircreated_log(block_number):
            pair_created_logs = self.factory.events.PairCreated().get_logs(
                fromBlock = block_number,
                toBlock = block_number,
            )
            return FilterLogs(
                type=FilterLogsType.PAIR_CREATED,
                data=pair_created_logs,
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

        pairs = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            future_to_contract = {executor.submit(filter_paircreated_log, block_number): self.factory.address}
            if len(self.inventory)>0:
                for pair in self.inventory:
                    future_to_contract[executor.submit(filter_sync_log, pair.address, block_number)] = pair.address

            for future in concurrent.futures.as_completed(future_to_contract):
                contract = future_to_contract[future]
                try:
                    result = future.result()
                    logging.debug(f"contract {contract} result {result}")

                    if result is not None and isinstance(result, FilterLogs):
                        if result.type == FilterLogsType.PAIR_CREATED:
                            if result.data != ():
                                for log in result.data:
                                    logging.debug(f"found pair created {log}")
                                    if log['args']['token0'].lower() == self.weth_address.lower() or log['args']['token1'].lower() == self.weth_address.lower():
                                        pairs.append(Pair(
                                            token=log['args']['token0'] if log['args']['token1'].lower() == self.weth_address.lower() else log['args']['token1'],
                                            token_index=0 if log['args']['token1'].lower() == self.weth_address.lower() else 1,
                                            address=log['args']['pair'],
                                        ))

                        elif result.type == FilterLogsType.SYNC:
                            if result.data != ():
                                for log in result.data:
                                    logging.debug(f"sync {log}")
                                    for pair in self.inventory:
                                        if pair.address == contract:
                                            logging.info(f"update reserves for inventory {pair.address}")
                                            pair.reserveToken = Web3.from_wei(log['args']['reserve0'], 'ether') if pair.token_index==0 else Web3.from_wei(log['args']['reserve1'], 'ether')
                                            pair.reserveETH = Web3.from_wei(log['args']['reserve1'], 'ether') if pair.token_index==0 else Web3.from_wei(log['args']['reserve0'], 'ether')
                            

                except Exception as e:
                    logging.error(f"contract {contract} error {e}")
        
        return pairs
    
    async def listen_report(self):
        while True:
            report = await self.report_broker.coro_get()

            if report is not None and isinstance(report, ExecutionAck) and report.pair is not None:
                logging.info(f"receive report {report}")
                if report.is_buy and report.pair.address not in [pair.address for pair in self.inventory]:
                    self.inventory.append(report.pair)
                    logging.debug(f"add pair {report.pair} to watching {self.inventory}")
                else:
                    for idx,pair in enumerate(self.inventory):
                        if pair.address == report.pair.address:
                            self.inventory.pop(idx)
                            logging.debug(f"remove pair {report.pair} from watching {self.inventory}")
    
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
            token='0xabc',
            token_index=1,
            address='0x6A89E43ef759677d7647bB46BF3890cdC18264BC',
        ),
        amount_in=1,
        amount_out=1,
        is_buy=True,
    ))

    report_broker.put(ExecutionAck(
        lead_block=0,
        block_number=0,
        tx_hash='0xabc',
        tx_status=1,
        pair=Pair(
            token='0xabc',
            token_index=1,
            address='0xe1D2f11C0a186A3f332967b5135FFC9a4568B15d',
        ),
        amount_in=1,
        amount_out=1,
        is_buy=True,
    ))

    report_broker.put(ExecutionAck(
        lead_block=0,
        block_number=0,
        tx_hash='0xabc',
        tx_status=1,
        pair=Pair(
            token='0xabc',
            token_index=1,
            address='0xe1D2f11C0a186A3f332967b5135FFC9a4568B15d',
        ),
        amount_in=1,
        amount_out=1,
        is_buy=False,
    ))

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
                logging.info(f"block inventory {block_data.inventory[0]}")
        await asyncio.gather(block_watcher.main(), receive_block())
    
    #asyncio.run(block_watcher.main())
    asyncio.run(run_all())


    