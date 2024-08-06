import asyncio
import aioprocessing
from multiprocessing import Process
import threading
import concurrent.futures

import os
import logging
from decimal import Decimal
from time import time
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()
logging.basicConfig(level=logging.INFO)

from watcher import BlockWatcher
from simulator import Simulator
from executor import BuySellExecutor
from reporter import Reporter
from helpers import load_abi, timer_decorator, calculate_price, calculate_next_block_base_fee

from data import ExecutionOrder, SimulationResult, ExecutionAck, Position, TxStatus, ReportData, ReportDataType

# global variables
glb_fullfilled = False # TODO
glb_liquidated = False
glb_watchlist = []
glb_inventory = []
glb_daily_pnl = (datetime.now(), 0)
glb_auto_run = True # TODO
glb_lock = threading.Lock()

# load config
ERC20_ABI = load_abi(f"{os.path.dirname(__file__)}/contracts/abis/ERC20.abi.json")
PAIR_ABI = load_abi(f"{os.path.dirname(__file__)}/contracts/abis/UniV2Pair.abi.json")
WETH_ABI = load_abi(f"{os.path.dirname(__file__)}/contracts/abis/WETH.abi.json")
ROUTER_ABI = load_abi(f"{os.path.dirname(__file__)}/contracts/abis/UniRouter.abi.json")
FACTORY_ABI = load_abi(f"{os.path.dirname(__file__)}/contracts/abis/UniV2Factory.abi.json")
BOT_ABI = load_abi(f"{os.path.dirname(__file__)}/contracts/abis/InspectBot.abi.json")

# simulation conditions
RESERVE_ETH_MIN_THRESHOLD = 5
SIMULATION_AMOUNT = 0.001
SLIPPAGE_MIN_THRESHOLD = 30 # in basis points
SLIPPAGE_MAX_THRESHOLD = 100 # in basis points

# watchlist config
MAX_INSPECT_ATTEMPTS = 5
INSPECT_INTERVAL_SECONDS = 5*60
WATCHLIST_CAPACITY = 50

# buy/sell tx config
BUY_AMOUNT = 0.0001
DEADLINE_DELAY_SECONDS = 30
GAS_LIMIT = 250*10**3
MAX_FEE_PER_GAS = 10**9
MAX_PRIORITY_FEE_PER_GAS = 10**9
GAS_COST = 300*100**3

# liquidation conditions
TAKE_PROFIT_PERCENTAGE = 50
STOP_LOSS_PERCENTAGE = -10
HOLD_MAX_DURATION_SECONDS = 5*60
HARD_STOP_PNL_THRESHOLD = -199

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

async def strategy(watching_broker, execution_broker, report_broker, watching_notifier,):
    global glb_fullfilled
    global glb_liquidated
    global glb_lock
    global glb_inventory
    global glb_watchlist
    global glb_daily_pnl
    global glb_auto_run

    def calculate_pnl_percentage(position, pair, base_fee):
        #numerator = Decimal(position.amount)*(Decimal(position.buy_price) - calculate_price(pair.reserve_token, pair.reserve_eth)) - GAS_COST*base_fee/10**9
        
        numerator = Decimal(position.amount)*calculate_price(pair.reserve_token, pair.reserve_eth) - Decimal(BUY_AMOUNT)
        denominator = Decimal(BUY_AMOUNT)
        return (numerator / denominator) * Decimal(100)

    while True:
        block_data = await watching_broker.coro_get()

        logging.info(f"STRATEGY received block {block_data}")
        
        # send block report
        if len(block_data.pairs) > 0:
            report_broker.put(ReportData(
                type=ReportDataType.BLOCK,
                data=block_data,
            ))

        # hardstop based on pnl
        logging.info(f"[{glb_daily_pnl[0].strftime('%Y-%m-%d %H:00:00')}] PnL {glb_daily_pnl[1]}")

        if glb_daily_pnl[1] < HARD_STOP_PNL_THRESHOLD:
            with glb_lock:
                glb_auto_run = False
                logging.warning(f"MAIN stop auto run...")

        if not glb_auto_run:
            logging.info(f"MAIN auto-run is disabled")
            continue

        if glb_daily_pnl[0].strftime('%Y-%m-%d %H') != datetime.now().strftime('%Y-%m-%d %H'):
            with glb_lock:
                glb_daily_pnl = (datetime.now(), 0)
                logging.info(f"MAIN reset daily pnl at time {glb_daily_pnl[0].strftime('%Y-%m-%d %H:00:00')}")


        if len(glb_inventory)>0:
            if not glb_liquidated:
                for position in glb_inventory:
                    is_liquidated = False
                    for pair in block_data.inventory:
                        if position.pair.address == pair.address:
                            position.pnl = calculate_pnl_percentage(position, pair, calculate_next_block_base_fee(block_data.base_fee, block_data.gas_used, block_data.gas_limit))
                            logging.info(f"{position} update PnL {position.pnl}")
                            
                            if position.pnl > TAKE_PROFIT_PERCENTAGE or position.pnl < STOP_LOSS_PERCENTAGE:
                                logging.warning(f"{position} take profit or stop loss caused by pnl {position.pnl}")
                                is_liquidated = True
                                break

                    if not is_liquidated and block_data.block_timestamp - position.start_time > HOLD_MAX_DURATION_SECONDS:
                        logging.warning(f"MAIN {position} liquidation call caused by timeout {HOLD_MAX_DURATION_SECONDS}")
                        is_liquidated = True

                    if is_liquidated:
                        with glb_lock:
                            glb_liquidated = True

                        logging.warning(f"MAIN liquidate {position}")
                        execution_broker.put(ExecutionOrder(
                                    block_number=block_data.block_number,
                                    block_timestamp=block_data.block_timestamp,
                                    pair=position.pair,
                                    amount_in=position.amount,
                                    amount_out_min=0,
                                    is_buy=False,
                                ))
        
        if len(glb_watchlist)>0:
            logging.info(f"MAIN watching list {len(glb_watchlist)}")

            inspection_batch=[]
            for pair in glb_watchlist:
                if (block_data.block_timestamp - pair.created_at) > pair.inspect_attempts*INSPECT_INTERVAL_SECONDS:
                    logging.info(f"MAIN pair {pair} inspect time #{pair.inspect_attempts + 1} elapsed")
                    inspection_batch.append(pair)

            if len(inspection_batch)>0:
                simulation_results = simulate(inspection_batch)
                logging.info(f"MAIN watchlist simulation result {simulation_results}")

                for result in simulation_results:
                    for idx,pair in enumerate(glb_watchlist):
                        if result.pair.address == pair.address:
                            with glb_lock:
                                pair.inspect_attempts+=1
                            logging.info(f"MAIN update {pair} inspect attempts {pair.inspect_attempts}")

                        if pair.inspect_attempts >= MAX_INSPECT_ATTEMPTS:   
                            with glb_lock:
                                glb_watchlist.pop(idx)
                            logging.warning(f"remove pair {pair} from watching list at index #{idx} caused by reaching max attempts {MAX_INSPECT_ATTEMPTS}")

                            if not glb_fullfilled:
                                with glb_lock:
                                    glb_fullfilled = True

                                # send execution order
                                logging.warning(f"MAIN send buy-order of {pair} amount {BUY_AMOUNT}")
                                execution_broker.put(ExecutionOrder(
                                    block_number=block_data.block_number,
                                    block_timestamp=block_data.block_timestamp,
                                    pair=pair,
                                    amount_in=BUY_AMOUNT,
                                    amount_out_min=0,
                                    is_buy=True,
                                ))

                # remove simulation failed pair
                failed_pairs = [pair.address for pair in inspection_batch if pair.address not in [result.pair.address for result in simulation_results]]
                for idx,pair in enumerate(glb_watchlist):
                    if pair.address in failed_pairs:
                        with glb_lock:
                            glb_watchlist.pop(idx)

                        logging.warning(f"MAIN remove pair {pair} from watchlist at index #{idx} due to simulation failed")


        if  len(block_data.pairs)>0:
            if len(glb_watchlist)<WATCHLIST_CAPACITY:
                simulation_results = simulate(block_data.pairs)
                logging.debug(f"SIMULATION result {simulation_results}")

                for result in simulation_results:
                    with glb_lock:
                        # append to watchlist
                        pair=result.pair
                        pair.inspect_attempts=1

                        glb_watchlist.append(pair)

                        logging.info(f"MAIN add pair {pair} to watchlist")
            else:
                logging.info(f"MAIN watchlist is already full capacity")


@timer_decorator
def simulate(pairs) -> SimulationResult:
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
            inspector_abi=BOT_ABI,
        )
                                
        return simulator.inspect_pair(pair, SIMULATION_AMOUNT)
    
    results = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_token = {executor.submit(inspect_pair, pair): pair.token for pair in pairs}
        for future in concurrent.futures.as_completed(future_to_token):
            token = future_to_token[future]
            try:
                result = future.result()
                logging.info(f"inspect token {token} result {result}")
                if result is not None and isinstance(result, SimulationResult):
                    if result.slippage > SLIPPAGE_MIN_THRESHOLD and result.slippage < SLIPPAGE_MAX_THRESHOLD:
                        results.append(result)
            except Exception as e:
                logging.error(f"inspect token {token} error {e}")

    return results

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
        bot=os.environ.get('INSPECTOR_BOT'),
        bot_abi=BOT_ABI,
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
        global glb_daily_pnl

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

                                    pnl = (Decimal(report.amount_out)-Decimal(BUY_AMOUNT))/Decimal(BUY_AMOUNT)*Decimal(100)
                                    glb_daily_pnl = (glb_daily_pnl[0], glb_daily_pnl[1] + pnl)

                                    logging.info(f"MAIN remove {position} at index #{idx} from inventory, update PnL {glb_daily_pnl}")
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
                                    glb_daily_pnl = (glb_daily_pnl[0], glb_daily_pnl[1] - 100)

                                    logging.info(f"MAIN remove {position} at index #{idx} from inventory, update PnL {glb_daily_pnl}")

    #await strategy(watching_broker, execution_broker)
    await asyncio.gather(watching_process(watching_broker, watching_notifier),
                         strategy(watching_broker, execution_broker, report_broker, watching_notifier,),
                         handle_execution_report(),
                         reporter.run(),
                         )

if __name__=="__main__":
    asyncio.run(main())