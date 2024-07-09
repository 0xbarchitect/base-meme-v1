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
JOEPAIRV1_ABI = load_abi(f"{os.path.dirname(__file__)}/contracts/abis/JoePairV1.abi.json")
JOE_ROUTER_ABI = load_abi(f"{os.path.dirname(__file__)}/contracts/abis/JoeRouterV2.abi.json")
LBROUTER_ABI = load_abi(f"{os.path.dirname(__file__)}/contracts/abis/LBRouter.abi.json")
AVEX_ABI = load_abi(f"{os.path.dirname(__file__)}/contracts/abis/AVEX.abi.json")
WAVAX_ABI = load_abi(f"{os.path.dirname(__file__)}/contracts/abis/WAVAX.abi.json")

AVAX_AMOUNT_THRESHOLD = 10**-8
SLIPPAGE_PERCENTAGE = 5

def watching_process(block_sender):
    block_watcher = BlockWatcher(os.environ.get('WSS_URL'), block_sender, os.environ.get('PAIR_ADDRESS'), JOEPAIRV1_ABI)
    asyncio.run(block_watcher.run())

async def strategy(block_receiver, execution_sender, report_sender):
    while True:
        block_data = await block_receiver.coro_get()

        print(f"strategy received block {block_data}")
        if block_data.amount1Diff >= AVAX_AMOUNT_THRESHOLD:
            print(f"qualify to trigger counter trading")
            # simulate
            amountTokenIn = calculate_amount_in(block_data.reserve0, block_data.reserve1, block_data.amount1Diff * Decimal(0.8))
            print(f"amount avex in {amountTokenIn}")

            amount_avex_out_simulated = simulate(block_data, amountTokenIn)

            if amount_avex_out_simulated > 0:
                print(f"promising profit {amount_avex_out_simulated:5f}, execute counter trade...")

                # queue execution data
                execution_sender.put(ExecutionData(
                    block_data.block_number,
                    block_data.block_timestamp,
                    amountTokenIn,
                    amount_avex_out_simulated * Decimal(100 - SLIPPAGE_PERCENTAGE) / Decimal(100),
                ))

                # send report
                report_sender.put(ReportData(
                    type = ReportDataType.BLOCK,
                    data = block_data
                ))
            else:
                print(f"bad opportunity, ignore...")
        elif block_data.amount1Diff > 0:
            print(f"amount {block_data.amount1Diff} too small")

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
    p2 = Process(target=execution_process, args=(execution_broker, report_broker,))
    p2.start()

    # REPORTING process
    p3 = Process(target=report_process, args=(report_broker,))
    p3.start()

    await strategy(watching_broker, execution_broker, report_broker)

if __name__=="__main__":
    asyncio.run(main())