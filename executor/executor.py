import asyncio
import os
import logging
import time
from decimal import Decimal

from web3 import Web3
from web3.middleware import geth_poa_middleware, construct_sign_and_send_raw_middleware

import sys # for testing
sys.path.append('..')

from helpers.decorators import timer_decorator, async_timer_decorator
from helpers.utils import load_abi

from library import Singleton
from data import ExecutionData, W3Account, ReportData, ReportDataType, SwapNativeForTokenData

from concurrent.futures import ThreadPoolExecutor

MAX_WORKER_NUMBER = 5
ALLOWANCE_TOKEN_AMOUNT = 10**9
MINIMUM_TOKEN_BALANCE = 20*10**6
MINIMUM_AVAX_BALANCE = 0.1

GAS_LIMIT = 200*10**3
MAX_PRIORIRY_FEE_PER_GAS = 25*10**9
MAX_FEE_PER_GAS = 50*10**9
DEADLINE_DELAY_SECONDS = 6 # 5 blocks latency

class Executor(metaclass=Singleton):
    @timer_decorator
    def __init__(self, order_receiver, report_sender, treasury_key, private_keys, http_url, router_address,
                 lbrouter_address, avex_address, wavax_address, router_abi, lbrouter_abi, avex_abi):
        self.order_receiver = order_receiver
        self.report_sender = report_sender

        self.w3 = Web3(Web3.HTTPProvider(http_url))
        self.avex_address = avex_address
        self.wavax_address = wavax_address

        if self.w3.is_connected() == True:
            print(f"web3 provider {http_url} connected")

        self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)

        self.treasury = self.w3.eth.account.from_key(treasury_key)
        self.w3.middleware_onion.add(construct_sign_and_send_raw_middleware(self.treasury))
        self.w3.eth.default_account = self.treasury.address
        #print(f"default account {self.w3.eth.default_account}")

        self.joerouter = self.w3.eth.contract(address=router_address, abi=router_abi)
        self.lbrouter = self.w3.eth.contract(address=lbrouter_address, abi=lbrouter_abi)
        self.avex = self.w3.eth.contract(address=avex_address, abi=avex_abi)

        self.accounts = [self.build_w3_account(priv_key) for priv_key in private_keys]
        [self.funding_executor(account) for account in self.accounts]
        [self.update_account_nonce(id) for id in range(len(self.accounts))]

    def build_w3_account(self, private_key) -> W3Account:
        acct = self.w3.eth.account.from_key(private_key)
        return W3Account(
            acct,
            private_key,
            self.w3.eth.get_transaction_count(acct.address)
        )
    
    def update_account_nonce(self, id):
        self.accounts[id].nonce = self.w3.eth.get_transaction_count(self.accounts[id].w3_account.address)

    def funding_executor(self, account):
        try:
            print(f"funding account {account.w3_account.address}...")

            address = account.w3_account.address

            # wavax
            balance = self.w3.eth.get_balance(address)
            if Web3.from_wei(balance, 'ether') < Decimal(MINIMUM_AVAX_BALANCE):
                tx_hash = self.w3.eth.send_transaction({
                    'from': self.treasury.address,
                    'to': address,
                    'value': Web3.to_wei(Decimal(MINIMUM_AVAX_BALANCE)*Decimal(1.5) - Web3.from_wei(balance, 'ether'), 'ether')
                })
                tx_receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
                print(f"fund AVAX to account {address} succesfully")
            else:
                print(f"account {address} AVAX balance is sufficient")

            # token
            token_balance = self.avex.functions.balanceOf(address).call()
            if Web3.from_wei(token_balance, 'ether') < Decimal(MINIMUM_TOKEN_BALANCE):                
                tx = self.avex.functions.transfer(address, Web3.to_wei(Decimal(MINIMUM_TOKEN_BALANCE)*Decimal(1.5) - Web3.from_wei(token_balance, 'ether'), 'ether')).build_transaction()
                tx_hash = self.w3.eth.send_transaction(tx)
                tx_receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
                print(f"fund token to {address} successfully")
            else:
                print(f"account {address} token balance sufficient")

            # token approval
            allowance = self.avex.functions.allowance(address, self.lbrouter.address).call()
            if Web3.from_wei(allowance, 'ether') < Decimal(ALLOWANCE_TOKEN_AMOUNT):
                nonce = self.w3.eth.get_transaction_count(address)
                tx = self.avex.functions.approve(self.lbrouter.address, Web3.to_wei(Decimal(ALLOWANCE_TOKEN_AMOUNT), 'ether')).build_transaction({'from': address, 'nonce': nonce})
                tx_signed = self.w3.eth.account.sign_transaction(tx, account.private_key)
                tx_hash = self.w3.eth.send_raw_transaction(tx_signed.rawTransaction)
                tx_receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
                print(f"{address} approve token successfully")
            else:
                print(f"account {address} approved sufficiently")

        except Exception as e:
            print(f"funding account {address} error {e}")
            raise e


    @timer_decorator
    def execute(self, account_id, block_number, amountIn, amountOutMin, deadline):
        try:
            print(f"account address {self.accounts[account_id].w3_account.address} in {amountIn} outMin {amountOutMin} deadline {deadline}")

            signer = self.accounts[account_id].w3_account.address
            priv_key = self.accounts[account_id].private_key

            # get nonce onchain
            #nonce = self.w3.eth.get_transaction_count(signer)

            # increment nonce offchain to reduce latency
            self.accounts[account_id].nonce += 1

            # tx = self.joerouter.functions.swapExactTokensForAVAX(
            #     Web3.to_wei(amountIn, 'ether'),
            #     0,            
            #     [self.avex_address, self.wavax_address],
            #     signer,
            #     (int(time.time()) + 1000000)).build_transaction({
            #         "from": signer, 
            #         "nonce": self.accounts[account_id].nonce - 1,
            #         "maxFeePerGas": 50000000000,
            #         "maxPriorityFeePerGas": 25000000000,
            #         })
            
            tx = self.lbrouter.functions.swapExactTokensForNATIVE(
                Web3.to_wei(amountIn, 'ether'),
                Web3.to_wei(amountOutMin, 'ether'),
                {
                    'pairBinSteps': [0],
                    'versions': [0],
                    'tokenPath': [self.avex_address, self.wavax_address]
                }, 
                signer,
                deadline).build_transaction({
                    "from": signer, 
                    "nonce": self.accounts[account_id].nonce - 1,
                    "gas": GAS_LIMIT,
                    "maxFeePerGas": MAX_FEE_PER_GAS,
                    "maxPriorityFeePerGas": MAX_PRIORIRY_FEE_PER_GAS,
                })
            
            #send_tx = self.w3.eth.send_transaction(tx)

            # send raw tx
            signed = self.w3.eth.account.sign_transaction(tx, priv_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed.rawTransaction)
            tx_receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

            #print(f"tx hash {Web3.to_hex(tx_receipt['transactionHash'])}")
            print(f"{amountIn} tx hash {Web3.to_hex(tx_hash)} in block #{tx_receipt['blockNumber']} with status {tx_receipt['status']}")

            # send report
            self.report_sender.put(ReportData(
                type = ReportDataType.COUNTER_TRADE,
                data = SwapNativeForTokenData(
                    lead_block=block_number,
                    block_number=tx_receipt['blockNumber'],
                    tx_hash=Web3.to_hex(tx_hash),
                    sender=signer,
                    amount0_in=amountIn,
                    amount1_out_min=amountOutMin,
                    deadline=deadline,
                    status=tx_receipt['status'],
                )
            ))
        
        except Exception as e:
            print(f"{amountIn} catch exception {e}")

    def get_block_timestamp(self):
        block = self.w3.eth.get_block('latest')        
        return block['timestamp']

    async def run(self):
        print(f"listen for execution...")
        executor = ThreadPoolExecutor(max_workers=len(self.accounts))
        counter = 0
        while True:
            execution_data = await self.order_receiver.coro_get()
            counter += 1
            print(f"receive execution order #{counter} {execution_data.block_number} {execution_data.block_timestamp} {execution_data.amount0In} {execution_data.amount1Min}")
            #future = executor.submit(self.dummy_execute, 15 - execution_data.amount0In)

            deadline = execution_data.block_timestamp + DEADLINE_DELAY_SECONDS if execution_data.block_timestamp > 0 else self.get_block_timestamp() + DEADLINE_DELAY_SECONDS

            future = executor.submit(self.execute, (counter - 1) % len(self.accounts), execution_data.block_number, execution_data.amount0In, execution_data.amount1Min, deadline)

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    JOE_ROUTER_ABI = load_abi(f"{os.path.dirname(__file__)}/../contracts/abis/JoeRouterV2.abi.json")
    LBROUTER_ABI = load_abi(f"{os.path.dirname(__file__)}/../contracts/abis/LBRouter.abi.json")
    AVEX_ABI = load_abi(f"{os.path.dirname(__file__)}/../contracts/abis/AVEX.abi.json")
    WAVAX_ABI = load_abi(f"{os.path.dirname(__file__)}/../contracts/abis/WAVAX.abi.json")

    import aioprocessing

    order_receiver = aioprocessing.AioQueue()
    report_sender = aioprocessing.AioQueue()

    executor = Executor(order_receiver,
                        report_sender,
                        os.environ.get('PRIVATE_KEY'),
                        os.environ.get('EXECUTION_KEYS').split(','),
                        os.environ.get('HTTPS_URL'),
                        os.environ.get('JOEROUTER_ADDRESS'),
                        os.environ.get('LBROUTER_ADDRESS'),
                        os.environ.get('AVEX_ADDRESS'),
                        os.environ.get('WAVAX_ADDRESS'),
                        JOE_ROUTER_ABI,
                        LBROUTER_ABI,
                        AVEX_ABI,
                        )
    #executor.execute(0, 0, 100000)

    #print(f"block timestamp {executor.get_block_timestamp()}")

    # queue 10 jobs
    #queue.put(ExecutionData(34690439, 1720254002, 348224.4117120113911083142))
    order_receiver.put(ExecutionData(0, 0, 100000, 0))
    order_receiver.put(ExecutionData(0, 0, 100001, 0))
    order_receiver.put(ExecutionData(0, 0, 100002, 0))
    # queue.put(ExecutionData(0,0,1003))
    # queue.put(ExecutionData(0,0,1004))
    # queue.put(ExecutionData(0,0,1005))
    # queue.put(ExecutionData(0,0,1006))
    # queue.put(ExecutionData(0,0,1007))
    # queue.put(ExecutionData(0,0,1008))
    # queue.put(ExecutionData(0,0,1009))

    asyncio.run(executor.run())