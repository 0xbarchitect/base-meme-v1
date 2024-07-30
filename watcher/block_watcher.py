import os
import logging
from pathlib import Path
import json

import sys # for testing
sys.path.append('..')

from library import Singleton
from data import BlockData, Pair

import asyncio
from web3 import AsyncWeb3, Web3
from web3.providers import WebsocketProviderV2, HTTPProvider

class BlockWatcher(metaclass=Singleton):
    def __init__(self, wss_url, queue, factory_address, factory_abi, weth_address) -> None:
        self.wss_url = wss_url
        self.queue = queue

        self.factory_address = factory_address
        self.factory_abi = factory_abi
        self.weth_address = weth_address

    async def run(self):
        async with AsyncWeb3.persistent_websocket(
            WebsocketProviderV2(self.wss_url)
        ) as w3Async:
            print(f"websocket connected")
            self.factory = w3Async.eth.contract(address=self.factory_address, abi=self.factory_abi)

            subscription_id = await w3Async.eth.subscribe("newHeads")

            async for response in w3Async.ws.process_subscriptions():
                #print(f"new block {response}\n")
                
                block_number = Web3.to_int(hexstr=response['result']['number'])
                block_timestamp = Web3.to_int(hexstr=response['result']['timestamp'])
                base_fee = Web3.to_int(hexstr=response['result']['baseFeePerGas'])
                gas_used = Web3.to_int(hexstr=response['result']['gasUsed'])
                gas_limit = Web3.to_int(hexstr=response['result']['gasLimit'])

                print(f"block number {block_number} timestamp {block_timestamp}")

                pairs = await self.filter_log_in_block(block_number)

                #print(f"found pairs {pairs}")
                self.queue.put(BlockData(
                    block_number,
                    block_timestamp,
                    base_fee,
                    gas_used,
                    gas_limit,
                    pairs,
                ))

    async def filter_log_in_block(self, block_number):
        #block_number = 34513052 # TODO

        logs = await self.factory.events.PairCreated().get_logs(
            fromBlock = block_number,
            toBlock = block_number,
        )

        pairs = []

        if logs != ():
            for log in logs:
                print(f"found pair created {log}")
                if log['args']['token0'].lower() == self.weth_address.lower() or log['args']['token1'].lower() == self.weth_address.lower():
                    pairs.append(Pair(
                        token0=log['args']['token0'],
                        token1=log['args']['token1'],
                        address=log['args']['pair']
                    ))

        return pairs

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    _DIR = Path(os.path.dirname(os.path.abspath(__file__)))
    ABI_PATH = _DIR / '../contracts' / 'abis'
    FACTORY_ABI = json.load(open(ABI_PATH / 'UniV2Factory.abi.json', 'r'))

    import aioprocessing

    queue = aioprocessing.AioQueue()
    block_watcher = BlockWatcher(os.environ.get('WSS_URL'), 
                                 queue, 
                                 os.environ.get('FACTORY_ADDRESS'), 
                                 FACTORY_ABI,
                                 os.environ.get('WETH_ADDRESS'),
                                 )

    asyncio.run(block_watcher.run())


    