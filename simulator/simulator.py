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

AVEX_CODE = load_contract_bin(f"{os.path.dirname(__file__)}/bytecodes/dummy_avex.bin")
WAVAX_CODE = load_contract_bin(f"{os.path.dirname(__file__)}/bytecodes/wavax.bin")
PAIR_CODE = load_contract_bin(f"{os.path.dirname(__file__)}/bytecodes/pair.bin")
LBROUTER_CODE = load_contract_bin(f"{os.path.dirname(__file__)}/bytecodes/lbrouter.bin")

JOE_ROUTER_BIN = f"{os.path.dirname(__file__)}/bytecodes/joerouter.bin"
JOE_ROUTER_CODE = load_contract_bin(f"{os.path.dirname(__file__)}/bytecodes/joerouter.bin")
JOE_FACTORY_CODE = load_contract_bin(f"{os.path.dirname(__file__)}/bytecodes/joefactory.bin")

JOE_ROUTER_ABI = load_abi(f"{os.path.dirname(__file__)}/../contracts/abis/JoeRouterV2.abi.json")

AVAX_BALANCE = 1000
GAS_LIMIT_FLAT = 200*10**3

class Simulator:
    @timer_decorator
    def __init__(self, http_url, signer, current_block : BlockData, is_forked : bool):
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

        self.evm.set_balance(signer, Web3.to_wei(AVAX_BALANCE*2, 'ether'))

        self.avex = self.evm.deploy(signer, AVEX_CODE)
        
        #self.evm.insert_account_info(avex_address, AccountInfo(code=AVEX_CODE))
        #self.avex = avex_address
        #assert self.evm.basic(self.avex).code.hex() == AVEX_CODE.hex()

        self.wavax = self.evm.deploy(signer, WAVAX_CODE)

        #wavax_address = "0xffffffffffffffffffffffffffffffffffffffff" # fake address in order be set wavax as token1
        #self.evm.insert_account_info(wavax_address, AccountInfo(code=WAVAX_CODE))
        #self.wavax = wavax_address

        #assert self.evm.basic(self.wavax).code.hex() == WAVAX_CODE.hex()
        
        self.joefactory = self.evm.deploy(signer, JOE_FACTORY_CODE)
        
        # override factory address and wavax address in router code
        custom_router_code = load_router_contract(JOE_ROUTER_BIN, self.joefactory, self.wavax)

        self.joerouter = self.evm.deploy(signer, custom_router_code)

        result = self.evm.message_call(
            self.signer,
            self.joerouter,
            calldata=bytes.fromhex(
                func_selector('factory()')
            )
        )
        assert decode_address(result) == self.joefactory.lower()

        result = self.evm.message_call(
            self.signer,
            self.joerouter,
            calldata=bytes.fromhex(
                func_selector('WAVAX()')
            )
        )
        assert decode_address(result) == self.wavax.lower()

        # create pair by factory
        result = self.evm.message_call(
            self.signer,
            self.joefactory,
            calldata=bytes.fromhex(
                func_selector('createPair(address,address)') + f"{encode_address(self.avex)}{encode_address(self.wavax)}"
            )
        )
        #print(f"pair created at {decode_address(result)}")

        self.pair = decode_address(result)

        result = self.evm.message_call(
            self.signer,
            self.pair,
            calldata=bytes.fromhex(
                func_selector('token0()')
            )
        )
        
        #assert decode_address(result) == self.avex.lower()
        if decode_address(result) == self.avex.lower():
            self.avexTokenId = 0
        else:
            self.avexTokenId = 1

        result = self.evm.message_call(
            self.signer,
            self.pair,
            calldata=bytes.fromhex(
                func_selector('token1()')
            )
        )
        #assert decode_address(result) == self.wavax.lower()

        print(f"""
            AVEX deployed at {self.avex}
            WAVAX deployed at {self.wavax}
            JOEFACTORY deployed at {self.joefactory}
            JOEROUTER deployed at {self.joerouter}
            PAIR deployed at {self.pair}
            AVEX token is token{self.avexTokenId}
        """)        

    @timer_decorator
    def basic(self, address):
        vb_before = self.evm.basic(address)
        print(vb_before)

        fake_balance = self.evm.get_balance(address)
        print(f"fake balance {Web3.from_wei(fake_balance, 'ether')}")

    @async_timer_decorator
    async def async_basic(self, address):
        vb_before = self.evm.basic(address)
        print(vb_before)

    @timer_decorator
    def swap_token_for_native(self, reserveToken, reserveAVAX, amountTokenIn) -> int:
        try:
            # add liquidity to create reserves
            result = self.evm.message_call(
                self.signer,
                self.pair,
                calldata=bytes.fromhex(
                    func_selector('getReserves()')
                )
            )

            reserve0B, reserve1B, _ = decode_pair_reserves(result)
            print(f"before reserve0 {reserve0B} reserve1 {reserve1B}")

            result = self.evm.message_call(
                self.signer,
                self.avex,
                calldata=bytes.fromhex(
                    func_selector('balanceOf(address)') + f"{encode_address(self.signer)}"
                )
            )
            print(f"balance avex {decode_int(result, 'ether')}")

            print(f"block {self.evm.env.block}")
            assert self.evm.env.block.timestamp < 1000

            result = self.evm.message_call(
                self.signer,
                self.avex,
                calldata=bytes.fromhex(
                    func_selector('approve(address,uint256)') + f"{encode_address(self.joerouter)}{encode_uint(Web3.to_wei(Decimal(reserveToken), 'ether'))}"
                )
            )
            print(f"approve avex for router {result}")

            result = self.evm.message_call(
                self.signer,
                self.joerouter,
                calldata=bytes.fromhex(
                    func_selector('addLiquidityAVAX(address,uint256,uint256,uint256,address,uint256)')
                    + f"{encode_address(self.avex)}{encode_uint(Web3.to_wei(Decimal(reserveToken), 'ether'))}{encode_uint(Web3.to_wei(Decimal(reserveToken)*Decimal(0.5), 'ether'))}{encode_uint(Web3.to_wei(Decimal(reserveAVAX), 'ether'))}{encode_address(self.signer)}{encode_uint(Web3.to_wei(1, 'ether'))}"
                ),
                value=Web3.to_wei(Decimal(reserveAVAX), 'ether')
            )
            print(f"add liquidity result {result}")

            result = self.evm.message_call(
                self.signer,
                self.pair,
                calldata=bytes.fromhex(
                    func_selector('getReserves()')
                )
            )

            reserve0B, reserve1B, _ = decode_pair_reserves(result)
            print(f"after liquidity reserve0 {Web3.from_wei(reserve0B, 'ether')} reserve1 {Web3.from_wei(reserve1B, 'ether')}")

            # swap token for avax
            result = self.evm.message_call(
                self.signer,
                self.avex,
                calldata=bytes.fromhex(
                    func_selector('approve(address,uint256)') + f"{encode_address(self.joerouter)}{encode_uint(Web3.to_wei(Decimal(amountTokenIn), 'ether'))}"
                )
            )
            print(f"approve avex for router {result}")

            w3  = Web3()
            contract = w3.eth.contract(abi=JOE_ROUTER_ABI)

            print(f"checksum {Web3.to_checksum_address(self.avex)}")
            
            calldata = contract.encode_abi(
                "swapExactTokensForAVAX",
                [
                    Web3.to_wei(Decimal(amountTokenIn), 'ether'),
                    0,
                    [Web3.to_checksum_address(self.avex), Web3.to_checksum_address(self.wavax)],
                    self.signer,
                    Web3.to_wei(1, 'ether')
                ]
            )

            print(f"calldata {calldata} {func_selector('getReserves()')}")
            
            result = self.evm.message_call(
                self.signer,
                self.joerouter,
                calldata=bytes.fromhex(calldata[2:]),                
            )
            print(f"swap result {result}")

            result = self.evm.message_call(
                self.signer,
                self.pair,
                calldata=bytes.fromhex(
                    func_selector('getReserves()')
                )
            )

            reserve0A, reserve1A, _ = decode_pair_reserves(result)
            print(f"after swap reserve0 {Web3.from_wei(reserve0A, 'ether')} reserve1 {Web3.from_wei(reserve1A, 'ether')}")            

            amountAVAXOut = (Web3.from_wei(reserve1B, 'ether') - Web3.from_wei(reserve1A, 'ether')) if self.avexTokenId == 0 else (Web3.from_wei(reserve0B, 'ether') - Web3.from_wei(reserve0A, 'ether'))

            gas_fee = self.calculate_gas_fee(GAS_LIMIT_FLAT)

            print(f"amountAVAXOut {amountAVAXOut} gasFee {gas_fee}")
            
            return amountAVAXOut - gas_fee

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
                            BlockData(0,0,25000000000,45059,15000000,0,0,0,0),
                            False)
    
    #print(f"gas fee in avax {simulator.calculate_gas_fee(GAS_LIMIT_FLAT)}")

    amountOut = simulator.swap_token_for_native(1000000,10,800000)
    print(f"amount avax out {amountOut}")