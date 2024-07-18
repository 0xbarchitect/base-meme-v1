import asyncio
import os
import logging
import time
from decimal import Decimal

import sys # for testing
sys.path.append('..')

from library import Singleton
from helpers.decorators import timer_decorator, async_timer_decorator
from helpers.utils import load_contract_bin, encode_address, encode_uint, func_selector, \
                            decode_address, decode_pair_reserves, decode_int, load_router_contract, \
                            load_abi, calculate_next_block_base_fee

from data import BlockData, SimulationResult

from web3 import Web3
from pyrevm import EVM, AccountInfo
from uniswap_universal_router_decoder import FunctionRecipient, RouterCodec
import eth_abi

class Simulator:
    @timer_decorator
    def __init__(self, 
                 http_url, 
                 signer, 
                 router_address, 
                 weth,
                 fee_collector,
                 sweep_receiver,
                 inspector,
                 pair_abi,
                 weth_abi,
                 inspector_abi,
                 current_block : BlockData, 
                 is_forked : bool):
        logging.info(f"start simulation...")

        self.http_url = http_url
        self.signer = signer
        self.current_block = current_block

        if is_forked == True:
            self.evm = EVM(
                # can fork from a remote node
                fork_url=http_url,
                # can set tracing to true/false
                #tracing=True,
                # can configure the environment
                # env=Env(
                #     block=BlockEnv(timestamp=100)
                # )
            )
        else:
            self.evm = EVM()

        self.codec = RouterCodec()

        self.evm.set_balance(signer, Web3.to_wei(ETH_BALANCE*2, 'ether'))
        self.router_address = router_address
        #self.permit2_address = permit2_address
        self.weth = weth
        self.fee_collector = fee_collector
        self.sweep_receiver = sweep_receiver

        self.w3 = Web3(Web3.HTTPProvider(http_url))
        self.pair_abi = pair_abi
        self.weth_contract = self.w3.eth.contract(address=weth, abi=weth_abi)
        self.inspector = self.w3.eth.contract(address=inspector, abi=inspector_abi)
        
    @timer_decorator
    def inspect_token(self, token, amount) -> SimulationResult:
        try:
            #pair_contract = self.w3.eth.contract(address=pair,abi=self.pair_abi)
            # state_override = {
            #     self.weth: {
            #         'stateDiff': {
            #             '0xf0a2fd871c1ccff2b6103f26750c36cdd8b9b18309aa61141e14477bacf69014': (hex(1000000))
            #         }
            #     }
            # }
            # result = self.w3.eth.call({
            #     'from':self.signer,
            #     'to':self.weth,
            #     'data':'0x70a08231000000000000000000000000C9b0D9125bD2C029F812776C043ECD05Ad4610dd'
            # },'latest',state_override)
            
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
                    func_selector('inspect(address)') + encode_address(token)
                )
            }, 'latest', state_override)

            result = eth_abi.decode(['(uint256,uint256)'], result)
            slippage = (Decimal(result[0][0]) - Decimal(result[0][1]))/Decimal(result[0][0])*Decimal(1000) # in basis points
            slippage = round(slippage,3)
            
            logging.info(f"""result
                    ETH In {Web3.from_wei(result[0][0], 'ether')}
                    ETH Out {Web3.from_wei(result[0][1], 'ether')}
                  """)
            
            return SimulationResult(
                token=token,
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
                            os.environ.get('FEE_COLLECTOR'),
                            os.environ.get('SWEEP_RECEIVER'),
                            os.environ.get('INSPECTOR_BOT'),
                            PAIR_ABI,
                            WETH_ABI,
                            INSPECTOR_ABI,
                            BlockData(0,0,25000000000,45059,15000000,[]),
                            False)
    
    #result=simulator.inspect_token('0xB1a03EdA10342529bBF8EB700a06C60441fEf25d', 0.001)
    result=simulator.inspect_token('0xccb0f8DfB77C86a393165E2c35C79fff2940Cdc0', 0.001)
    logging.info(f"Simulation result {result}")
