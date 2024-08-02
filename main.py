import asyncio
import aioprocessing
from multiprocessing import Process
import threading

import os
import logging
from decimal import Decimal

from dotenv import load_dotenv
load_dotenv()
logging.basicConfig(level=logging.INFO)

from watcher import BlockWatcher
from simulator import Simulator
from executor import BuySellExecutor
from helpers import Reporter
from helpers import load_abi, timer_decorator, calculate_amount_out, calculate_amount_in

from data import ExecutionOrder, SimulationResult

# load config
ERC20_ABI = load_abi(f"{os.path.dirname(__file__)}/contracts/abis/ERC20.abi.json")
PAIR_ABI = load_abi(f"{os.path.dirname(__file__)}/contracts/abis/UniV2Pair.abi.json")
WETH_ABI = load_abi(f"{os.path.dirname(__file__)}/contracts/abis/WETH.abi.json")
ROUTER_ABI = load_abi(f"{os.path.dirname(__file__)}/contracts/abis/UniRouter.abi.json")
FACTORY_ABI = load_abi(f"{os.path.dirname(__file__)}/contracts/abis/UniV2Factory.abi.json")
INSPECTOR_ABI = load_abi(f"{os.path.dirname(__file__)}/contracts/abis/InspectBot.abi.json")

SIMULATION_AMOUNT = 0.001
SLIPPAGE_THRESHOLD = 30 # in basis point
BUY_AMOUNT = 0.0003

# gas
GAS_LIMIT = 200*100**3
MAX_FEE_PER_GAS = 10**9
MAX_PRIORITY_FEE_PER_GAS = 10**9
DEADLINE_DELAY_SECONDS = 30

# global variables
glb_fullfilled = False
glb_lock = threading.Lock()

async def watching_process(watching_broker, report_broker):
    block_watcher = BlockWatcher(os.environ.get('WSS_URL'), 
                                 watching_broker, 
                                 report_broker,
                                 os.environ.get('FACTORY_ADDRESS'),
                                 FACTORY_ABI,
                                 os.environ.get('WETH_ADDRESS'),
                                 )
    await block_watcher.main()

async def strategy(watching_broker, execution_broker, report_broker):
    global glb_fullfilled
    global glb_lock

    while True:
        block_data = await watching_broker.coro_get()

        logging.info(f"STRATEGY received block {block_data}")
        if len(block_data.pairs)>0:
            simulation = simulate(block_data)
            logging.info(f"SIMULATION result {simulation}")

            if simulation is not None and simulation.slippage < SLIPPAGE_THRESHOLD:
                if not glb_fullfilled:
                    with glb_lock:
                        glb_fullfilled = True

                    execution_broker.put(ExecutionOrder(
                        block_number=block_data.block_number,
                        block_timestamp=block_data.block_timestamp,
                        token=simulation.token,
                        amount_in=BUY_AMOUNT,
                        amount_out_min=0,
                        is_buy=True,
                    ))
                else:
                    logging.info(f"already fullfilled")
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
    executor = BuySellExecutor(
        http_url=os.environ.get('HTTPS_URL'),
        treasury_key=os.environ.get('PRIVATE_KEY'),
        executor_keys=os.environ.get('EXECUTION_KEYS').split(','),
        order_receiver=execution_broker,
        report_sender=report_broker,
        orderack_sender=report_broker,
        gas_limit=GAS_LIMIT,
        max_fee_per_gas=MAX_FEE_PER_GAS,
        max_priority_fee_per_gas=MAX_PRIORITY_FEE_PER_GAS,
        deadline_delay=DEADLINE_DELAY_SECONDS,
        weth=os.environ.get('WETH_ADDRESS'),
        router=os.environ.get('ROUTER_ADDRESS'),
        router_abi=ROUTER_ABI,
        erc20_abi=ERC20_ABI,
    )

    asyncio.run(executor.run())

def report_process(reporting_receiver):
    reporter = Reporter(reporting_receiver)
    asyncio.run(reporter.run())

async def main():
    watching_broker = aioprocessing.AioQueue()
    execution_broker = aioprocessing.AioQueue()
    report_broker = aioprocessing.AioQueue()
    
    # EXECUTION process
    p2 = Process(target=execution_process, args=(execution_broker,report_broker,))
    p2.start()

    # TODO: REPORTING process

    #await strategy(watching_broker, execution_broker)
    await asyncio.gather(watching_process(watching_broker),
                         strategy(watching_broker, execution_broker, report_broker))

if __name__=="__main__":
    asyncio.run(main())