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

from data import ExecutionData, ReportData, ReportDataType, SimulationResult

# load config
ERC20_ABI = load_abi(f"{os.path.dirname(__file__)}/contracts/abis/ERC20.abi.json")
PAIR_ABI = load_abi(f"{os.path.dirname(__file__)}/contracts/abis/UniV2Pair.abi.json")
WETH_ABI = load_abi(f"{os.path.dirname(__file__)}/contracts/abis/WETH.abi.json")
ROUTER_ABI = load_abi(f"{os.path.dirname(__file__)}/contracts/abis/UniRouter.abi.json")
FACTORY_ABI = load_abi(f"{os.path.dirname(__file__)}/contracts/abis/UniV2Factory.abi.json")
INSPECTOR_ABI = load_abi(f"{os.path.dirname(__file__)}/contracts/abis/InspectBot.abi.json")

SIMULATION_AMOUNT = 0.001
SLIPPAGE_THRESHOLD = 10 # in basis point

async def watching_process(watching_broker):
    block_watcher = BlockWatcher(os.environ.get('WSS_URL'), 
                                 watching_broker, 
                                 os.environ.get('FACTORY_ADDRESS'),
                                 FACTORY_ABI,
                                 os.environ.get('WETH_ADDRESS'),
                                 )
    #asyncio.run(block_watcher.run())
    await block_watcher.run()

async def strategy(watching_broker, execution_broker, report_broker):
    while True:
        block_data = await watching_broker.coro_get()

        logging.info(f"STRATEGY received block {block_data}")
        if len(block_data.pairs)>0:
            simulation = simulate(block_data)
            logging.info(f"SIMULATION result {simulation}")

            if simulation is not None and simulation.slippage < SLIPPAGE_THRESHOLD:
                execution_broker.put(simulation)
            else:
                logging.info(f"simulation result is not qualified")


@timer_decorator
def simulate(block_data) -> SimulationResult:
    simulator = Simulator(
        http_url=os.environ.get('HTTPS_URL'),
        signer=os.environ.get('SIGNER_ADDRESS'),
        router_address=os.environ.get('ROUTER_ADDRESS'),
        weth=os.environ.get('WETH_ADDRESS'),
        inspector=os.environ.get('INSPECTOR_BOT'),
        pair_abi=PAIR_ABI,
        weth_abi=WETH_ABI,
        inspector_abi=INSPECTOR_ABI,
        current_block=block_data,
    )
                            
    return simulator.inspect_token(block_data.pairs[0].token, SIMULATION_AMOUNT)

def execution_process(execution_broker, report_broker):
    # executor = Executor(execution_receiver,
    #                     report_sender,
    #                     os.environ.get('PRIVATE_KEY'),
    #                     os.environ.get('EXECUTION_KEYS').split(','),
    #                     os.environ.get('HTTPS_URL'),                        
    #                     os.environ.get('JOEROUTER_ADDRESS'),
    #                     os.environ.get('LBROUTER_ADDRESS'),
    #                     os.environ.get('AVEX_ADDRESS'),
    #                     os.environ.get('WAVAX_ADDRESS'),
    #                     JOE_ROUTER_ABI,
    #                     LBROUTER_ABI,
    #                     AVEX_ABI,
    #                     )
    # asyncio.run(executor.run())
    pass

def report_process(reporting_receiver):
    reporter = Reporter(reporting_receiver)
    asyncio.run(reporter.run())

async def main():
    watching_broker = aioprocessing.AioQueue()
    execution_broker = aioprocessing.AioQueue()
    report_broker = aioprocessing.AioQueue()
    
    # WATCHING process
    #p1 = Process(target=watching_process, args=(watching_broker,))
    #p1.start()

    # EXECUTION process
    p2 = Process(target=execution_process, args=(execution_broker,report_broker,))
    p2.start()

    # TODO: REPORTING process

    #await strategy(watching_broker, execution_broker)
    await asyncio.gather(watching_process(watching_broker),
                         strategy(watching_broker, execution_broker, report_broker))

if __name__=="__main__":
    asyncio.run(main())