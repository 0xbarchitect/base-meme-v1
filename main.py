import asyncio
import aioprocessing
from multiprocessing import Process
import threading
import concurrent.futures

import os
import logging
from decimal import Decimal
from time import time

from dotenv import load_dotenv
load_dotenv()
logging.basicConfig(level=logging.INFO)

from watcher import BlockWatcher
from simulator import Simulator
from executor import BuySellExecutor
from reporter import Reporter
from helpers import load_abi, timer_decorator, calculate_price, calculate_next_block_base_fee

from data import ExecutionOrder, SimulationResult, ExecutionAck, Position, TxStatus, ReportData, ReportDataType

# load config
ERC20_ABI = load_abi(f"{os.path.dirname(__file__)}/contracts/abis/ERC20.abi.json")
PAIR_ABI = load_abi(f"{os.path.dirname(__file__)}/contracts/abis/UniV2Pair.abi.json")
WETH_ABI = load_abi(f"{os.path.dirname(__file__)}/contracts/abis/WETH.abi.json")
ROUTER_ABI = load_abi(f"{os.path.dirname(__file__)}/contracts/abis/UniRouter.abi.json")
FACTORY_ABI = load_abi(f"{os.path.dirname(__file__)}/contracts/abis/UniV2Factory.abi.json")
INSPECTOR_ABI = load_abi(f"{os.path.dirname(__file__)}/contracts/abis/InspectBot.abi.json")

RESERVE_ETH_MIN_THRESHOLD = 1
SIMULATION_AMOUNT = 0.001
SLIPPAGE_MIN_THRESHOLD = 30 # in basis point
SLIPPAGE_MAX_THRESHOLD = 60
BUY_AMOUNT = 0.0001

# gas
GAS_LIMIT = 200*10**3
MAX_FEE_PER_GAS = 10**9
MAX_PRIORITY_FEE_PER_GAS = 10**9
GAS_COST = 300*100**3

DEADLINE_DELAY_SECONDS = 30

# global variables
glb_fullfilled = False # TODO
glb_liquidated = False
glb_inventory = []
glb_lock = threading.Lock()

# liquidation
TAKE_PROFIT_PERCENTAGE = 30
STOP_LOSS_PERCENTAGE = -10
HOLD_MAX_DURATION_SECONDS = 5*60

async def watching_process(watching_broker, watching_notifier):
    block_watcher = BlockWatcher(os.environ.get('HTTPS_URL'),
                                os.environ.get('WSS_URL'), 
                                watching_broker, 
                                watching_notifier,
                                os.environ.get('FACTORY_ADDRESS'),
                                FACTORY_ABI,
                                os.environ.get('WETH_ADDRESS'),
                                PAIR_ABI,
                                )
    await block_watcher.main()

async def strategy(watching_broker, execution_broker, report_broker):
    global glb_fullfilled
    global glb_liquidated
    global glb_lock
    global glb_inventory

    def calculate_pnl_percentage(position, pair, base_fee):
        #numerator = Decimal(position.amount)*(Decimal(position.buy_price) - calculate_price(pair.reserve_token, pair.reserve_eth)) - GAS_COST*base_fee/10**9
        numerator = Decimal(position.amount)*calculate_price(pair.reserve_token, pair.reserve_eth) - Decimal(BUY_AMOUNT)
        denominator = Decimal(BUY_AMOUNT)
        return (numerator / denominator) * Decimal(100)

    while True:
        block_data = await watching_broker.coro_get()

        logging.info(f"STRATEGY received block {block_data}")

        # send block report
        report_broker.put(ReportData(
            type=ReportDataType.BLOCK,
            data=block_data,
        ))

        if len(glb_inventory)>0:
            if not glb_liquidated:
                for position in glb_inventory:
                    is_liquidated = False
                    for pair in block_data.inventory:
                        if position.pair.address == pair.address:
                            pnl = calculate_pnl_percentage(position, pair, calculate_next_block_base_fee(block_data.base_fee, block_data.gas_used, block_data.gas_limit))
                            logging.info(f"Pair {position.pair} PnL {pnl}")
                            
                            if pnl > TAKE_PROFIT_PERCENTAGE or pnl < STOP_LOSS_PERCENTAGE:
                                logging.warning(f"take profit or stop loss caused by pnl {pnl}")
                                is_liquidated = True
                                break

                    if not is_liquidated and block_data.block_timestamp - position.start_time > HOLD_MAX_DURATION_SECONDS:
                        logging.warning(f"position {position} timeout")
                        is_liquidated = True

                    if is_liquidated:
                        with glb_lock:
                            glb_liquidated = True

                        logging.warning(f"liquidate position {position}")
                        execution_broker.put(ExecutionOrder(
                                    block_number=block_data.block_number,
                                    block_timestamp=block_data.block_timestamp,
                                    pair=position.pair,
                                    amount_in=position.amount,
                                    amount_out_min=0,
                                    is_buy=False,
                                ))

        elif len(block_data.pairs)>0:
            if not glb_fullfilled:
                simulation_result = simulate(block_data)

                logging.info(f"SIMULATION result {simulation_result}")

                if simulation_result is not None and isinstance(simulation_result, SimulationResult):
                    with glb_lock:
                        glb_fullfilled = True

                    logging.warning(f"send buy order {simulation_result.pair} amount {BUY_AMOUNT}")

                    execution_broker.put(ExecutionOrder(
                        block_number=block_data.block_number,
                        block_timestamp=block_data.block_timestamp,
                        pair=simulation_result.pair,
                        amount_in=BUY_AMOUNT,
                        amount_out_min=0,
                        is_buy=True,
                    ))

                else:
                    logging.info(f"simulation result is not qualified")
            else:
                logging.info(f"already fullfilled")


@timer_decorator
def simulate(block_data) -> SimulationResult:
    def inspect_pair(pair) -> SimulationResult:
        if pair.reserve_eth < RESERVE_ETH_MIN_THRESHOLD:
            return None
        
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
                                
        return simulator.inspect_pair(pair, SIMULATION_AMOUNT)
    
    best_option = None

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        pairs = block_data.pairs
        if len(block_data.pairs) > 5:
            pairs = block_data.pairs[:5]

        future_to_token = {executor.submit(inspect_pair, pair): pair.token for pair in pairs}
        for future in concurrent.futures.as_completed(future_to_token):
            token = future_to_token[future]
            try:
                result = future.result()
                logging.info(f"inspect token {token} result {result}")
                if result is not None and isinstance(result, SimulationResult):
                    if result.slippage > SLIPPAGE_MIN_THRESHOLD and result.slippage < SLIPPAGE_MAX_THRESHOLD:
                        if best_option is None:
                            best_option = result
                        elif result.slippage < best_option.slippage:
                            best_option = result
            except Exception as e:
                logging.error(f"inspect token error {e}")

    return best_option

def execution_process(execution_broker, report_broker):
    executor = BuySellExecutor(
        http_url=os.environ.get('HTTPS_URL'),
        treasury_key=os.environ.get('PRIVATE_KEY'),
        executor_keys=os.environ.get('EXECUTION_KEYS').split(','),
        order_receiver=execution_broker,
        report_sender=report_broker,
        gas_limit=GAS_LIMIT,
        max_fee_per_gas=MAX_FEE_PER_GAS,
        max_priority_fee_per_gas=MAX_PRIORITY_FEE_PER_GAS,
        deadline_delay=DEADLINE_DELAY_SECONDS,
        weth=os.environ.get('WETH_ADDRESS'),
        router=os.environ.get('ROUTER_ADDRESS'),
        router_abi=ROUTER_ABI,
        erc20_abi=ERC20_ABI,
        pair_abi=PAIR_ABI,
    )

    asyncio.run(executor.run())

async def main():
    global glb_inventory
    global glb_lock
    global glb_fullfilled

    watching_broker = aioprocessing.AioQueue()
    watching_notifier = aioprocessing.AioQueue()
    execution_broker = aioprocessing.AioQueue()
    execution_report = aioprocessing.AioQueue()
    report_broker = aioprocessing.AioQueue()
    
    # EXECUTION process
    p2 = Process(target=execution_process, args=(execution_broker,execution_report,))
    p2.start()

    # REPORTING process
    reporter = Reporter(report_broker)

    async def handle_execution_report():
        global glb_inventory
        global glb_lock
        global glb_fullfilled
        global glb_liquidated

        while True:
            report = await execution_report.coro_get()
            if report is not None and isinstance(report, ExecutionAck):
                # send execution report
                report_broker.put(ReportData(
                    type=ReportDataType.EXECUTION,
                    data=report,
                ))

                watching_notifier.put(report)

                if report.tx_status == TxStatus.SUCCESS:
                    if report.is_buy:
                        with glb_lock:
                            glb_inventory.append(Position(
                                pair=report.pair,
                                amount=report.amount_out,
                                buy_price=calculate_price(report.amount_out, report.amount_in),
                                start_time=int(time()),
                            ))
                            logging.info(f"MAIN append {report.pair} to inventory")
                    else:
                        for idx, position in enumerate(glb_inventory):
                            if position.pair.address == report.pair.address:
                                with glb_lock:
                                    glb_inventory.pop(idx)
                                    glb_fullfilled = False
                                    glb_liquidated = False
                                    logging.info(f"MAIN remove {position.pair} at index #{idx} from inventory")
                else:
                    logging.info(f"execution failed, reset lock...")
                    if report.is_buy:
                        with glb_lock:
                            glb_fullfilled = False
                    else:
                        for idx, position in enumerate(glb_inventory):
                            if position.pair.address == report.pair.address:
                                with glb_lock:
                                    glb_inventory.pop(idx)
                                    glb_fullfilled = False
                                    glb_liquidated = False
                                    logging.info(f"remove {position.pair} at index #{idx} from inventory")

    #await strategy(watching_broker, execution_broker)
    await asyncio.gather(watching_process(watching_broker, watching_notifier),
                         strategy(watching_broker, execution_broker, report_broker),
                         handle_execution_report(),
                         reporter.run(),
                         )

if __name__=="__main__":
    asyncio.run(main())