import asyncio
import os
import logging
import time
import datetime
from decimal import Decimal
import requests

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
from data import Pair
from simulator import Simulator

# django
import django
from django.utils.timezone import make_aware
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "admin.settings")
django.setup()
import console.models

STATUS_CODE_SUCCESS=200
PAGE_SIZE=100
MM_TX_AMOUNT_THRESHOLD=0.001

from enum import IntEnum

class MaliciousPair(IntEnum):
    UNMALICIOUS=0
    CREATOR_BLACKLISTED=1
    CREATOR_DUPLICATED=2 

class Inspector(metaclass=Singleton):
    def __init__(self,http_url,api_key,
                 signer, 
                 router, 
                 weth,
                 bot,
                 pair_abi,
                 weth_abi,
                 bot_abi,) -> None:
        self.w3 = Web3(Web3.HTTPProvider(http_url))
        self.api_key = api_key

        self.pair_abi = pair_abi

        self.simulator = Simulator(
            http_url=http_url,
            signer=signer,
            router_address=router,
            weth=weth,
            inspector=bot,
            pair_abi=pair_abi,
            weth_abi=weth_abi,
            inspector_abi=bot_abi,
        )

    @timer_decorator
    def is_contract_verified(self, pair: Pair) -> False:
        r=requests.get(f"https://api.basescan.org/api?module=contract&action=getabi&address={pair.token}&apikey={self.api_key}")
        if r.status_code==STATUS_CODE_SUCCESS:
            res=r.json()
            if int(res['status'])==1:
                return True
            
    @timer_decorator
    def is_creator_call_token(self, pair, from_block, to_block) -> 0:
        r=requests.get(f"https://api.basescan.org/api?module=account&action=txlist&address={pair.token}&startblock={from_block}&endblock={to_block}&page=1&offset={PAGE_SIZE}&sort=asc&apikey={self.api_key}")
        if r.status_code==STATUS_CODE_SUCCESS:
            res=r.json()
            if len(res['result'])>0:
                txs = [tx for tx in res['result'] if tx['from'].lower()==pair.creator.lower() and tx['to'].lower()==pair.token.lower()]
                return len(txs)
            
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
        
    def is_malicious(self, pair) -> MaliciousPair:
        blacklist = console.models.BlackList.objects.filter(address=pair.creator.lower()).filter(created_at__gte=make_aware(datetime.datetime.now() - datetime.timedelta(30))).first()
        if blacklist is not None:
            logging.warning(f"pair {pair} is blacklisted due to rogue creator")
            return MaliciousPair.CREATOR_BLACKLISTED
        
        duplicate_pool_creator = console.models.Pair.objects.filter(creator=pair.creator.lower()).filter(created_at__gte=make_aware(datetime.datetime.now() - datetime.timedelta(30))).exclude(address=pair.address.lower()).first()
        if duplicate_pool_creator is not None:
            logging.warning(f"malicious {pair} due to the same creator with other pair {duplicate_pool_creator.address}")
            return MaliciousPair.CREATOR_DUPLICATED
        
        return MaliciousPair.UNMALICIOUS
    
    def inspect(self, pairs):
        pass
        
if __name__=="__main__":
    from dotenv import load_dotenv
    load_dotenv()
    logging.basicConfig(level=logging.INFO)

    PAIR_ABI = load_abi(f"{os.path.dirname(__file__)}/../contracts/abis/UniV2Pair.abi.json")
    WETH_ABI = load_abi(f"{os.path.dirname(__file__)}/../contracts/abis/WETH.abi.json")
    INSPECTOR_ABI = load_abi(f"{os.path.dirname(__file__)}/../contracts/abis/InspectBot.abi.json")

    inspector = Inspector(
        http_url=os.environ.get('HTTPS_URL'),
        api_key=os.environ.get('BASESCAN_API_KEY'),
        signer=os.environ.get('EXECUTION_ADDRESSES').split(',')[0],
        router=os.environ.get('ROUTER_ADDRESS'),
        weth=os.environ.get('WETH_ADDRESS'),
        bot=os.environ.get('INSPECTOR_BOT').split(',')[0],
        pair_abi=PAIR_ABI,
        weth_abi=WETH_ABI,
        bot_abi=INSPECTOR_ABI,
    )

    pair = Pair(
        address="0x022525b53d0789917c30272288392f088cc26f9d",
        token="0xf2661d67f55279f42ac34f8ccb784f9cb985d6d3",
        #token="0xf6C22b5BDE8c338E8c46B68f5fA8B0df90FFF414",
        token_index=1,
        reserve_eth=0,
        reserve_token=0,
        created_at=0,
        inspect_attempts=1,
        creator="0x7bed7b039bbda41c7822c5a520327063b53542d9",
        contract_verified=False,
        number_tx_mm=0,
        last_inspected_block=0
    )

    print("verified") if inspector.is_contract_verified(pair) else print(f"unverified")
    print(f"number called {inspector.is_creator_call_token(pair, 18441043, 18441080)}")
    print(f"number mm_tx {inspector.number_tx_mm(pair, 18441096, 18441130)}")
    print(f"is malicious {inspector.is_malicious(pair)}")

