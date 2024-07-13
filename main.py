import asyncio
import aioprocessing
from multiprocessing import Process

import os
import logging
from decimal import Decimal

from helpers import load_abi, timer_decorator, calculate_amount_out, calculate_amount_in

from dotenv import load_dotenv
load_dotenv()
logging.basicConfig(level=logging.INFO)

from watcher import BlockWatcher
from simulator import Simulator
from executor import Executor
from helpers import Reporter

from data import ExecutionData, ReportData, ReportDataType

# load config
ERC20_ABI = load_abi(f"{os.path.dirname(__file__)}/contracts/abis/ERC20.abi.json")
PAIR_ABI = load_abi(f"{os.path.dirname(__file__)}/contracts/abis/UniV2Pair.abi.json")
WETH_ABI = load_abi(f"{os.path.dirname(__file__)}/contracts/abis/WETH.abi.json")
ROUTER_ABI = load_abi(f"{os.path.dirname(__file__)}/contracts/abis/UniRouter.abi.json")
FACTORY_ABI = load_abi(f"{os.path.dirname(__file__)}/contracts/abis/UniV2Factory.abi.json")

AVAX_AMOUNT_THRESHOLD = 10**-8
SLIPPAGE_PERCENTAGE = 5

def watching_process(block_sender):
    block_watcher = BlockWatcher(os.environ.get('WSS_URL'), 
                                 block_sender, 
                                 os.environ.get('FACTORY_ADDRESS'), 
                                 FACTORY_ABI,
                                 os.environ.get('WETH_ADDRESS'),
                                 )
    asyncio.run(block_watcher.run())

async def strategy(block_receiver, execution_sender, report_sender):
    while True:
        block_data = await block_receiver.coro_get()

        print(f"strategy received block {block_data}")

@timer_decorator
def simulate(block_data, amount0In) -> int:
    simulator = Simulator(os.environ.get('HTTPS_URL'),
                            os.environ.get('SIGNER_ADDRESS'),
                            block_data,
                            False)
                            
    return simulator.swap_token_for_native(reserveToken=block_data.reserve0,
                                           reserveAVAX=block_data.reserve1,
                                           amountTokenIn=amount0In)

def execution_process(execution_receiver, report_sender):
    executor = Executor(execution_receiver,
                        report_sender,
                        os.environ.get('PRIVATE_KEY'),
                        os.environ.get('EXECUTION_KEYS').split(','),
                        os.environ.get('HTTPS_URL'),                        
                        os.environ.get('JOEROUTER_ADDRESS'),
                        os.environ.get('LBROUTER_ADDRESS'),
                        os.environ.get('AVEX_ADDRESS'),
                        os.environ.get('WAVAX_ADDRESS'),
                        JOE_ROUTER_ABI,
                        LBROUTER_ABI,
                        AVEX_ABI,
                        )
    asyncio.run(executor.run())

def report_process(reporting_receiver):
    reporter = Reporter(reporting_receiver)
    asyncio.run(reporter.run())

async def main():
    watching_broker = aioprocessing.AioQueue()
    execution_broker = aioprocessing.AioQueue()
    report_broker = aioprocessing.AioQueue()
    
    # WATCHING process
    p1 = Process(target=watching_process, args=(watching_broker,))
    p1.start()

    # EXECUTION process
    #p2 = Process(target=execution_process, args=(execution_broker, report_broker,))
    #p2.start()

    # REPORTING process

    await strategy(watching_broker, execution_broker, report_broker)

if __name__=="__main__":
    asyncio.run(main())