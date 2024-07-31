import asyncio
import os
import logging
import time
from decimal import Decimal

from concurrent.futures import ThreadPoolExecutor

import sys # for testing
sys.path.append('..')

from helpers import timer_decorator, load_abi
from executor import BaseExecutor
from data import ExecutionOrder

class BuySellExecutor(BaseExecutor):
    def __init__(self, http_url, treasury_key, executor_keys, order_receiver, report_sender, orderack_sender, gas_limit, max_fee_per_gas, max_priority_fee_per_gas, deadline_delay, weth, router, router_abi, erc20_abi) -> None:
        super().__init__(http_url, treasury_key, executor_keys, order_receiver, report_sender, orderack_sender, gas_limit, max_fee_per_gas, max_priority_fee_per_gas, deadline_delay)
        self.weth = weth
        self.router = self.w3.eth.contract(address=router, abi=router_abi)
        self.erc20_abi = erc20_abi

    @timer_decorator
    def execute(self, account_id, is_buy, token, amount_in, amount_out_min, deadline):
        try:
            logging.info(f"account address {self.accounts[account_id].w3_account.address} in {amount_in} outMin {amount_out_min} deadline {deadline} isBuy {is_buy}")

            signer = self.accounts[account_id].w3_account.address
            priv_key = self.accounts[account_id].private_key

            # get nonce onchain
            nonce = self.w3.eth.get_transaction_count(signer)

            if is_buy:
                tx = self.router.functions.swapExactETHForTokens(
                    Web3.to_wei(amount_out_min, 'ether'),
                    [self.weth, token],
                    signer,
                    deadline).build_transaction({
                        "from": signer,
                        "nonce": nonce,
                        "gas": self.gas_limit,
                        "value": Web3.to_wei(amount_in, 'ether')
                        })
            else:
                # allowance
                token_contract = self.w3.eth.contract(address=token, abi=self.erc20_abi)
                tx = token_contract.functions.approve(self.router.address, Web3.to_wei(10**12, 'ether')).build_transaction({'from': signer, 'nonce': nonce})

                tx_signed = self.w3.eth.account.sign_transaction(tx, priv_key)
                tx_hash = self.w3.eth.send_raw_transaction(tx_signed.rawTransaction)
                tx_receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

                logging.info(f"{signer} approve token for router {self.router.address} status {tx_receipt['status']}")

                if tx_receipt['status'] != 1:
                    raise Exception(f"token {token} allowance failed")

                tx = self.router.functions.swapExactTokensForETH(
                    Web3.to_wei(amount_in, 'ether'),
                    Web3.to_wei(amount_out_min, 'ether'),            
                    [token, self.weth],
                    signer,
                    deadline).build_transaction({
                        "from": signer,
                        "nonce": nonce+1,
                        "gas": self.gas_limit,
                        })
            
            # send raw tx
            signed = self.w3.eth.account.sign_transaction(tx, priv_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed.rawTransaction)
            tx_receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

            logging.info(f"{amount_in} tx hash {Web3.to_hex(tx_hash)} in block #{tx_receipt['blockNumber']} with status {tx_receipt['status']}")

            # send report
        
        except Exception as e:
            logging.error(f"{amount_in} catch exception {e}")

    async def run(self):
        logging.info(f"listen for execution...")
        executor = ThreadPoolExecutor(max_workers=len(self.accounts))
        counter = 0
        while True:
            execution_data = await self.order_receiver.coro_get()
            counter += 1
            logging.info(f"receive execution order #{counter} {execution_data.block_number} {execution_data.block_timestamp} {execution_data.amount_in} {execution_data.amount_out_min}")

            deadline = execution_data.block_timestamp + self.deadline_delay if execution_data.block_timestamp > 0 else self.get_block_timestamp() + self.deadline_delay
            future = executor.submit(self.execute, 
                                     (counter - 1) % len(self.accounts), 
                                     execution_data.is_buy,
                                     execution_data.token,
                                     execution_data.amount_in, 
                                     execution_data.amount_out_min, 
                                     deadline,
                                     )

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    logging.basicConfig(level=logging.INFO)

    ROUTER_ABI = load_abi(f"{os.path.dirname(__file__)}/../contracts/abis/UniRouter.abi.json")
    WETH_ABI = load_abi(f"{os.path.dirname(__file__)}/../contracts/abis/WETH.abi.json")
    ERC20_ABI = load_abi(f"{os.path.dirname(__file__)}/../contracts/abis/ERC20.abi.json")

    import aioprocessing

    order_receiver = aioprocessing.AioQueue()
    report_sender = aioprocessing.AioQueue()

    executor = BuySellExecutor(
        http_url=os.environ.get('HTTPS_URL'),
        treasury_key=os.environ.get('PRIVATE_KEY'),
        executor_keys=os.environ.get('EXECUTION_KEYS').split(','),
        order_receiver=order_receiver,
        report_sender=report_sender,
        orderack_sender=report_sender,
        gas_limit=200*10**3,
        max_fee_per_gas=0.01*10**9,
        max_priority_fee_per_gas=25*10**9,
        deadline_delay=30,
        weth=os.environ.get('WETH_ADDRESS'),
        router=os.environ.get('ROUTER_ADDRESS'),
        router_abi=ROUTER_ABI,
        erc20_abi=ERC20_ABI,
    )
    #executor.execute(0, 0, 100000)

    #print(f"block timestamp {executor.get_block_timestamp()}")

    # queue jobs
    # order_receiver.put(ExecutionData(
    #     block_number=0, 
    #     block_timestamp=0, 
    #     token="0xe1D2f11C0a186A3f332967b5135FFC9a4568B15d", 
    #     amount_in=0.0003, 
    #     amount_out_min=0,
    #     is_buy=True))
    
    order_receiver.put(ExecutionOrder(
        block_number=0, 
        block_timestamp=0, 
        token="0xe1D2f11C0a186A3f332967b5135FFC9a4568B15d", 
        amount_in=72839918,
        amount_out_min=0,
        is_buy=False))

    asyncio.run(executor.run())