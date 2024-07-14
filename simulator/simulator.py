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

    @timer_decorator
    def inspect_token(self, token0, token1, amount) -> int:
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

            result = self.evm.message_call(
                self.signer,
                path[1],
                calldata=bytes.fromhex(
                    func_selector('approve(address,uint256)') + f"{encode_address(self.router_address)}{encode_uint(Web3.to_wei(10**12, 'ether'))}"
                )
            )
            print(f"approval result {Web3.to_hex(result)}")
            
            encoded_data = self.codec.encode.chain() \
                                .wrap_eth(FunctionRecipient.ROUTER, Web3.to_wei(amount, 'ether')) \
                                .v2_swap_exact_in(FunctionRecipient.ROUTER, Web3.to_wei(amount, 'ether'), 0, path, payer_is_sender=False) \
                                .pay_portion(FunctionRecipient.CUSTOM, path[1], FEE_BPS, self.fee_collector) \
                                .sweep(FunctionRecipient.SENDER, path[1], 0) \
                                .build(1730919049)
            print(f"encoded data {encoded_data}")

            result = self.evm.message_call(
                self.signer,
                self.router_address,
                calldata=bytes.fromhex(encoded_data[2:]),
                value=Web3.to_wei(amount, 'ether'),
            )
            print(f"wrap eth result {Web3.to_hex(result)}")

            result = self.evm.message_call(
                self.signer,
                path[1],
                calldata=bytes.fromhex(
                    func_selector('balanceOf(address)') + f"{encode_address(self.signer)}"
                )
            )
            print(f"after balance {decode_int(result, 'ether')}")
        except Exception as e:
            print(f"catch exception {e}")

            return 0
        
    def calculate_gas_fee(self, gas_limit):
        # set priority gas equal base gas
        gas_fee = calculate_next_block_base_fee(self.current_block.base_fee, self.current_block.gas_used, self.current_block.gas_limit) * Decimal(2) * Decimal(gas_limit)
        return Web3.from_wei(gas_fee, 'ether')

if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv()

    simulator = Simulator(os.environ.get('HTTPS_URL'),
                            os.environ.get('SIGNER_ADDRESS'),
                            os.environ.get('ROUTER_ADDRESS'),
                            os.environ.get('WETH_ADDRESS'),
                            os.environ.get('FEE_COLLECTOR'),
                            os.environ.get('SWEEP_RECEIVER'),
                            BlockData(0,0,25000000000,45059,15000000,[]),
                            True)
    
    simulator.inspect_token('0xB1A42447eA19676141D16eEA27dB1E350711Cee9',os.environ.get('WETH_ADDRESS'),0.0003)
