import asyncio
import os
import logging
import time
from decimal import Decimal

from web3 import Web3
from uniswap_universal_router_decoder import FunctionRecipient, RouterCodec
import eth_abi

import sys # for testing
sys.path.append('..')

from library import Singleton
from helpers.decorators import timer_decorator, async_timer_decorator
from helpers.utils import load_contract_bin, encode_address, encode_uint, func_selector, \
                            decode_address, decode_pair_reserves, decode_int, load_router_contract, \
                            load_abi, calculate_next_block_base_fee

from data import BlockData, SimulationResult, Pair

class Simulator:
    @timer_decorator
    def __init__(self, 
                 http_url, 
                 signer, 
                 router_address, 
                 weth,
                 inspector,
                 pair_abi,
                 weth_abi,
                 inspector_abi,
                 current_block : BlockData,):
        logging.info(f"start simulation...")

        self.http_url = http_url
        self.signer = signer
        self.current_block = current_block

        self.router_address = router_address
        self.weth = weth

        self.w3 = Web3(Web3.HTTPProvider(http_url))
        self.pair_abi = pair_abi
        self.weth_contract = self.w3.eth.contract(address=weth, abi=weth_abi)
        self.inspector = self.w3.eth.contract(address=inspector, abi=inspector_abi)
        
    @timer_decorator
    def inspect_pair(self, pair: Pair, amount):
        try:
            state_override={
                self.signer : {
                    'balance': (hex(1000*10**18))
                }
            }

            result = self.w3.eth.call({
                'from': self.signer,
                'to': self.inspector.address,
                'value': Web3.to_wei(amount, 'ether'),
                'data': bytes.fromhex(
                    func_selector('inspect(address)') + encode_address(pair.token)
                )
            }, 'latest', state_override)

            result = eth_abi.decode(['(uint256,uint256)'], result)
            slippage = (Decimal(result[0][0]) - Decimal(result[0][1]))/Decimal(result[0][0])*Decimal(10_000) # in basis points
            slippage = round(slippage,3)
            
            logging.info(f"""result
                    ETH In {Web3.from_wei(result[0][0], 'ether')}
                    ETH Out {Web3.from_wei(result[0][1], 'ether')}
                  """)
            
            return SimulationResult(
                pair=pair,
                amount_in=round(amount, 7),
                amount_out=round(Web3.from_wei(result[0][1], 'ether'), 7),
                slippage=slippage)
        except Exception as e:
            logging.error(f"simulate error {e}")

        return None
        
    def calculate_gas_fee(self, gas_limit):
        # set priority gas equal base gas
        gas_fee = calculate_next_block_base_fee(self.current_block.base_fee, self.current_block.gas_used, self.current_block.gas_limit) * Decimal(2) * Decimal(gas_limit)
        return Web3.from_wei(gas_fee, 'ether')
    
    async def main():
        pass

if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv()
    logging.basicConfig(level=logging.INFO)

    PAIR_ABI = load_abi(f"{os.path.dirname(__file__)}/../contracts/abis/UniV2Pair.abi.json")
    WETH_ABI = load_abi(f"{os.path.dirname(__file__)}/../contracts/abis/WETH.abi.json")
    INSPECTOR_ABI = load_abi(f"{os.path.dirname(__file__)}/../contracts/abis/InspectBot.abi.json")

    ETH_BALANCE = 1000
    GAS_LIMIT = 200*10**3
    FEE_BPS = 25

    simulator = Simulator(os.environ.get('HTTPS_URL'),
                            os.environ.get('SIGNER_ADDRESS'),
                            os.environ.get('ROUTER_ADDRESS'),
                            os.environ.get('WETH_ADDRESS'),
                            os.environ.get('INSPECTOR_BOT'),
                            PAIR_ABI,
                            WETH_ABI,
                            INSPECTOR_ABI,
                            BlockData(0,0,25000000000,45059,15000000,[]),)
    
    result=simulator.inspect_pair(Pair(
        address='0xccA6946D9ab268D7C76C71428c983e1Ec8484552',
        token='0xA01538254Ed4330A672e90A44e05012355A04f07',
        token_index=1,
        reserveToken=0,
        reserveETH=0
    ), 0.0003)

    logging.info(f"{result}")
