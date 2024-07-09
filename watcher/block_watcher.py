import os
import logging
from pathlib import Path
import json

import sys # for testing
sys.path.append('..')

from library import Singleton
from data import BlockData

import asyncio
from web3 import AsyncWeb3, Web3
from web3.providers import WebsocketProviderV2, HTTPProvider

class BlockWatcher(metaclass=Singleton):
    def __init__(self, wss_url, queue, pair_address, abi) -> None:
        self.wss_url = wss_url
        self.queue = queue

        self.pair_address = pair_address
        self.abi = abi

    async def run(self):
        async with AsyncWeb3.persistent_websocket(
            WebsocketProviderV2(self.wss_url)
        ) as w3Async:
            print(f"websocket connected")
            pair_contract_async = w3Async.eth.contract(address=self.pair_address, abi=self.abi)

            subscription_id = await w3Async.eth.subscribe("newHeads")

            async for response in w3Async.ws.process_subscriptions():
                #print(f"new block {response}\n")
                
                block_number = Web3.to_int(hexstr=response['result']['number'])
                block_timestamp = Web3.to_int(hexstr=response['result']['timestamp'])
                base_fee = Web3.to_int(hexstr=response['result']['baseFeePerGas'])
                gas_used = Web3.to_int(hexstr=response['result']['gasUsed'])
                gas_limit = Web3.to_int(hexstr=response['result']['gasLimit'])

                print(f"block number {block_number} timestamp {block_timestamp}")

                amount0Diff, amount1Diff, reserve0, reserve1 = await self.filter_log_in_block(pair_contract_async, block_number)

                # queue block data
                self.queue.put(BlockData(
                    block_number,
                    block_timestamp,
                    base_fee,
                    gas_used,
                    gas_limit,
                    amount0Diff,
                    amount1Diff,
                    reserve0,
                    reserve1
                ))

    async def filter_log_in_block(self, contract, block_number):
        #block_number = 34513052 # TODO

        logs = await contract.events.Swap().get_logs(
            fromBlock = block_number,
            toBlock = block_number,
        )

        amount0Diff = 0
        amount1Diff = 0

        reserve0 = 0
        reserve1 = 0

        if logs != ():
            for log in logs:
                ## TODO: need to filter out all MM tx
                print(f"swap log {log}")
                
                amount0Diff += Web3.from_wei(log['args']['amount0In'], 'ether') - Web3.from_wei(log['args']['amount0Out'], 'ether')
                amount1Diff += Web3.from_wei(log['args']['amount1In'], 'ether') - Web3.from_wei(log['args']['amount1Out'], 'ether')

        logs = await contract.events.Sync().get_logs(
            fromBlock = block_number,
            toBlock = block_number,
        )

        if logs != ():
            for log in logs:
                ## TODO: need to filter out all MM tx
                print(f"sync log {log}")

                reserve0 = Web3.from_wei(log['args']['reserve0'], 'ether')
                reserve1 = Web3.from_wei(log['args']['reserve1'], 'ether')

        return amount0Diff, amount1Diff, reserve0, reserve1

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    _DIR = Path(os.path.dirname(os.path.abspath(__file__)))
    ABI_PATH = _DIR / '../contracts' / 'abis'

    JOEPAIRV1_ABI = json.load(open(ABI_PATH / 'JoePairV1.abi.json', 'r'))

    import aioprocessing

    queue = aioprocessing.AioQueue()
    block_watcher = BlockWatcher(os.environ.get('WSS_URL'), queue, os.environ.get('PAIR_ADDRESS'), JOEPAIRV1_ABI)

    asyncio.run(block_watcher.run())


    