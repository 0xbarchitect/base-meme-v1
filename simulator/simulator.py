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

from data import BlockData

from web3 import Web3
from pyrevm import EVM, AccountInfo
from uniswap_universal_router_decoder import FunctionRecipient, RouterCodec

ETH_BALANCE = 1000
GAS_LIMIT_FLAT = 200*10**3
FEE_BPS = 25

class Simulator:
    @timer_decorator
    def __init__(self, 
                 http_url, 
                 signer, 
                 router_address, 
                 weth, 
                 fee_collector,
                 sweep_receiver,
                 pair_abi,
                 weth_abi, 
                 current_block : BlockData, 
                 is_forked : bool):
        print(f"start simulation...")

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

    @timer_decorator
    def inspect_token(self, token0, token1, pair, amount) -> int:
        try:
            path = [token0, token1] if token0.lower == self.weth else [token1, token0]

            # approve
            result = self.evm.message_call(
                self.signer,
                path[1],
                calldata=bytes.fromhex(
                    func_selector('balanceOf(address)') + f"{encode_address(self.signer)}"
                )
            )
            print(f"before balance {decode_int(result, 'ether')}")

            # result = self.evm.message_call(
            #     self.signer,
            #     path[1],
            #     calldata=bytes.fromhex(
            #         func_selector('approve(address,uint256)') + f"{encode_address(self.router_address)}{encode_uint(Web3.to_wei(10**12, 'ether'))}"
            #     )
            # )
            # print(f"approval result {Web3.to_hex(result)}")
            
            # encoded_data = self.codec.encode.chain() \
            #                     .wrap_eth(FunctionRecipient.ROUTER, Web3.to_wei(amount, 'ether')) \
            #                     .v2_swap_exact_in(FunctionRecipient.ROUTER, Web3.to_wei(amount, 'ether'), 0, path, payer_is_sender=False) \
            #                     .pay_portion(FunctionRecipient.CUSTOM, path[1], FEE_BPS, self.fee_collector) \
            #                     .sweep(FunctionRecipient.SENDER, path[1], 0) \
            #                     .build(1730919049)
            # print(f"encoded data {encoded_data}")

            # result = self.evm.message_call(
            #     self.signer,
            #     self.router_address,
            #     calldata=bytes.fromhex(encoded_data[2:]),
            #     value=Web3.to_wei(amount, 'ether'),
            # )
            # print(f"wrap eth result {Web3.to_hex(result)}")

            result = self.evm.message_call(
                self.signer,
                pair,
                calldata=bytes.fromhex(
                    func_selector('getReserves()')
                )
            )
            print(f"get reserves {Web3.to_hex(result)}")

            # result = self.evm.message_call(
            #     self.signer,
            #     path[1],
            #     calldata=bytes.fromhex(
            #         func_selector('balanceOf(address)') + f"{encode_address(self.signer)}"
            #     )
            # )
            # print(f"after balance {decode_int(result, 'ether')}")
        except Exception as e:
            print(f"catch exception {e}")

            return 0
        
    @timer_decorator
    def inspect_http(self, token0, token1, pair, amount) -> None:
        try:
            #pair_contract = self.w3.eth.contract(address=pair,abi=self.pair_abi)
            # result = self.weth_contract.functions.balanceOf(self.signer).call(
            #     state_override={
            #         self.weth: {
            #             'stateDiff': {
            #                 '0xf0a2fd871c1ccff2b6103f26750c36cdd8b9b18309aa61141e14477bacf69014': (hex(1000000))
            #             }
            #         }
            #     }
            # )

            state_override = {
                self.weth: {
                    'stateDiff': {
                        '0xf0a2fd871c1ccff2b6103f26750c36cdd8b9b18309aa61141e14477bacf69014': (hex(1000000))
                    }
                }
            }
            
            result = self.w3.eth.call({'from':self.signer,'to':self.weth,'data':'0x70a08231000000000000000000000000C9b0D9125bD2C029F812776C043ECD05Ad4610dd'},'latest',state_override)
            print(f"result {Web3.to_hex(result)}")
        except Exception as e:
            print(f"simulate error {e}")

        
    def calculate_gas_fee(self, gas_limit):
        # set priority gas equal base gas
        gas_fee = calculate_next_block_base_fee(self.current_block.base_fee, self.current_block.gas_used, self.current_block.gas_limit) * Decimal(2) * Decimal(gas_limit)
        return Web3.from_wei(gas_fee, 'ether')

if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv()

    PAIR_ABI = load_abi(f"{os.path.dirname(__file__)}/../contracts/abis/UniV2Pair.abi.json")
    WETH_ABI = load_abi(f"{os.path.dirname(__file__)}/../contracts/abis/WETH.abi.json")

    simulator = Simulator(os.environ.get('HTTPS_URL'),
                            os.environ.get('SIGNER_ADDRESS'),
                            os.environ.get('ROUTER_ADDRESS'),
                            os.environ.get('WETH_ADDRESS'),
                            os.environ.get('FEE_COLLECTOR'),
                            os.environ.get('SWEEP_RECEIVER'),
                            PAIR_ABI,
                            WETH_ABI,
                            BlockData(0,0,25000000000,45059,15000000,[]),
                            False)
    
    simulator.inspect_http('0xB1A42447eA19676141D16eEA27dB1E350711Cee9',os.environ.get('WETH_ADDRESS'), '0xf8bD9187909700a100f5739be914d0B7a235cc08', 0.0003)
