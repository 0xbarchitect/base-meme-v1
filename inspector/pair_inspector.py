import asyncio
import os
import logging
import time
import datetime
from decimal import Decimal
import requests
import concurrent.futures

from web3 import Web3
from uniswap_universal_router_decoder import FunctionRecipient, RouterCodec
import eth_abi

import sys # for testing
sys.path.append('..')

from library import Singleton
from helpers.decorators import timer_decorator, async_timer_decorator
from helpers.utils import load_contract_bin, encode_address, encode_uint, func_selector, \
                            decode_address, decode_pair_reserves, decode_int, load_router_contract, \
                            load_abi, calculate_next_block_base_fee, calculate_balance_storage_index, rpad_int, \
                            calculate_allowance_storage_index
from data import Pair, MaliciousPair, InspectionResult, SimulationResult
from inspector import Simulator

# django
import django
from django.utils.timezone import make_aware
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "admin.settings")
django.setup()
import console.models

STATUS_CODE_SUCCESS=200
PAGE_SIZE=100
MM_TX_AMOUNT_THRESHOLD=0.001

SIMULATION_AMOUNT=0.001
SLIPPAGE_MIN_THRESHOLD = 30 # in basis points
SLIPPAGE_MAX_THRESHOLD = 100 # in basis points

RESERVE_ETH_MIN_THRESHOLD=float(os.environ.get('RESERVE_ETH_MIN_THRESHOLD'))
RESERVE_ETH_MAX_THRESHOLD=float(os.environ.get('RESERVE_ETH_MAX_THRESHOLD'))

from enum import IntEnum

class PairInspector(metaclass=Singleton):
    def __init__(self,http_url,api_key,
                 signer, 
                 router, 
                 weth,
                 bot,
                 pair_abi,
                 weth_abi,
                 bot_abi,) -> None:
        
        self.http_url = http_url
        self.w3 = Web3(Web3.HTTPProvider(http_url))
        self.api_key = api_key

        self.signer = signer
        self.router = router
        self.weth = weth
        self.bot = bot

        self.pair_abi = pair_abi
        self.weth_abi = weth_abi
        self.bot_abi = bot_abi

    @timer_decorator
    def is_contract_verified(self, pair: Pair) -> False:
        if pair.contract_verified:
            return True

        #r=requests.get(f"https://api.basescan.org/api?module=contract&action=getabi&address={pair.token}&apikey={self.api_key}")
        r=requests.get(f"https://api.basescan.org/api?module=contract&action=getsourcecode&address={pair.token}&apikey={self.api_key}")
        if r.status_code==STATUS_CODE_SUCCESS:
            res=r.json()
            if int(res['status'])==1 and len(res['result'][0].get('Library',''))==0:
                return True
                
            
    @timer_decorator
    def is_creator_call_contract(self, pair, from_block, to_block) -> 0:
        r=requests.get(f"https://api.basescan.org/api?module=account&action=txlist&address={pair.token}&startblock={from_block}&endblock={to_block}&page=1&offset={PAGE_SIZE}&sort=asc&apikey={self.api_key}")
        if r.status_code==STATUS_CODE_SUCCESS:
            res=r.json()
            if len(res['result'])>0:
                txs = [tx for tx in res['result'] if tx['from'].lower()==pair.creator.lower() and tx['to'].lower()==pair.token.lower()]
                return len(txs)
            
        return 0
            
    @timer_decorator
    def number_tx_mm(self, pair, from_block, to_block) -> 0:
        contract=self.w3.eth.contract(address=Web3.to_checksum_address(pair.address),abi=self.pair_abi)
        logs = contract.events.Swap().get_logs(
                fromBlock = from_block,
                toBlock = to_block,
            )
        if logs != ():
            txs=[log for log in logs if (Web3.from_wei(log['args']['amount0In'], 'ether')>MM_TX_AMOUNT_THRESHOLD and pair.token_index==1) or (Web3.from_wei(log['args']['amount1In'], 'ether')>MM_TX_AMOUNT_THRESHOLD and pair.token_index==0)]
            return len(txs)
        
        return 0
        
    def is_malicious(self, pair) -> MaliciousPair:
        blacklist = console.models.BlackList.objects.filter(address=pair.creator.lower()).filter(created_at__gte=make_aware(datetime.datetime.now() - datetime.timedelta(30))).first()
        if blacklist is not None:
            logging.warning(f"INSPECTOR pair {pair.address} is blacklisted due to rogue creator")
            return MaliciousPair.CREATOR_BLACKLISTED
        
        # TODO: consider rules of duplication creator
        # duplicate_pool_creator = console.models.Pair.objects.filter(creator=pair.creator.lower()).filter(created_at__gte=make_aware(datetime.datetime.now() - datetime.timedelta(30))).exclude(address=pair.address.lower()).first()
        # if duplicate_pool_creator is not None:
        #     logging.warning(f"INSPECTOR malicious pair {pair.address} due to the same creator with other pair {duplicate_pool_creator.address}")
        #     return MaliciousPair.CREATOR_DUPLICATED
        
        return MaliciousPair.UNMALICIOUS
    
    @timer_decorator
    def inspect_pair(self, pair: Pair, block_number, is_initial=False) -> InspectionResult:
        from_block=pair.last_inspected_block+1 if pair.last_inspected_block>0 else block_number

        result = InspectionResult(
            pair=pair,
            from_block=from_block,
            to_block=block_number,
        )

        if pair.reserve_eth>=RESERVE_ETH_MIN_THRESHOLD and pair.reserve_eth<=RESERVE_ETH_MAX_THRESHOLD:
            result.reserve_inrange=True

        if is_initial and not result.reserve_inrange:
            return result        

        result.is_malicious=self.is_malicious(pair)
        if result.is_malicious != MaliciousPair.UNMALICIOUS:
            return result

        result.contract_verified=self.is_contract_verified(pair)
        if not result.contract_verified:
            return result
        
        if not is_initial:
            result.is_creator_call_contract=self.is_creator_call_contract(pair,from_block,block_number)
            if result.is_creator_call_contract>0:
                return result
        
            result.number_tx_mm=self.number_tx_mm(pair,from_block,block_number)

        simulator = Simulator(
            http_url=self.http_url,
            signer=self.signer,
            router_address=self.router,
            weth=self.weth,
            bot=self.bot,
            pair_abi=self.pair_abi,
            weth_abi=self.weth_abi,
            bot_abi=self.bot_abi,
        )

        simulation_result = simulator.inspect_pair(pair, SIMULATION_AMOUNT)
        if simulation_result is not None:
            if simulation_result.slippage > SLIPPAGE_MIN_THRESHOLD and simulation_result.slippage < SLIPPAGE_MAX_THRESHOLD:
                result.simulation_result=simulation_result
            else:
                logging.warning(f"INSPECTOR simulation result rejected due to high slippage {simulation_result.slippage}")

        return result
    
    @timer_decorator
    def inspect_batch(self, pairs, block_number, is_initial=False):
        results = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            future_to_pair = {executor.submit(self.inspect_pair,pair,block_number,is_initial): pair.address for pair in pairs}
            for future in concurrent.futures.as_completed(future_to_pair):
                pair = future_to_pair[future]
                try:
                    result = future.result()
                    logging.info(f"INSPECTOR inspect pair {pair} {result}")
                    results.append(result)
                except Exception as e:
                    logging.error(f"INSPECTOR inspect pair {pair} error {e}")

        return results
        
if __name__=="__main__":
    from dotenv import load_dotenv
    load_dotenv()
    logging.basicConfig(level=logging.INFO)

    PAIR_ABI = load_abi(f"{os.path.dirname(__file__)}/../contracts/abis/UniV2Pair.abi.json")
    WETH_ABI = load_abi(f"{os.path.dirname(__file__)}/../contracts/abis/WETH.abi.json")
    BOT_ABI = load_abi(f"{os.path.dirname(__file__)}/../contracts/abis/SnipeBot.abi.json")

    inspector = PairInspector(
        http_url=os.environ.get('HTTPS_URL'),
        api_key=os.environ.get('BASESCAN_API_KEY'),
        signer=Web3.to_checksum_address(os.environ.get('EXECUTION_ADDRESSES').split(',')[0]),
        router=Web3.to_checksum_address(os.environ.get('ROUTER_ADDRESS')),
        weth=Web3.to_checksum_address(os.environ.get('WETH_ADDRESS')),
        bot=Web3.to_checksum_address(os.environ.get('INSPECTOR_BOT').split(',')[0]),
        pair_abi=PAIR_ABI,
        weth_abi=WETH_ABI,
        bot_abi=BOT_ABI,
    )

    pair = Pair(
        address="0x137eb40b169a30367fa352f1a5f3069a77c9a3f0",
        token="0x1b0db1b116967ec132830e47b3fa8439a50ee417",
        token_index=1,
        reserve_eth=3,
        reserve_token=0,
        created_at=0,
        inspect_attempts=1,
        creator="0x9b5cd354a9f370241bcd56a6c6c7bba4d8e263e1",
        contract_verified=False,
        number_tx_mm=0,
        last_inspected_block=0,
    )

    #print("verified") if inspector.is_contract_verified(pair) else print(f"unverified")
    # print(f"number called {inspector.is_creator_call_contract(pair, 18441043, 18441080)}")
    # print(f"number mm_tx {inspector.number_tx_mm(pair, 18441096, 18441130)}")
    # print(f"is malicious {inspector.is_malicious(pair)}")

    inspector.inspect_batch([pair], 18441043, True)

