import asyncio
import os
import logging
import time
from decimal import Decimal

from concurrent.futures import ThreadPoolExecutor
from web3 import Web3
from web3.logs import STRICT, IGNORE, DISCARD, WARN

import sys # for testing
sys.path.append('..')

from helpers import timer_decorator, load_abi
from executor import BaseExecutor
from data import ExecutionOrder, Pair, ExecutionAck, TxStatus

class BuySellExecutor(BaseExecutor):
    def __init__(self, http_url, treasury_key, executor_keys, order_receiver, report_sender, \
                gas_limit, max_fee_per_gas, max_priority_fee_per_gas, deadline_delay, \
                weth, router, router_abi, erc20_abi, pair_abi, bot = None, bot_abi = None) -> None:
        super().__init__(http_url, treasury_key, executor_keys, order_receiver, report_sender, gas_limit, max_fee_per_gas, max_priority_fee_per_gas, deadline_delay)
        self.weth = weth
        self.router = self.w3.eth.contract(address=router, abi=router_abi)
        self.erc20_abi = erc20_abi
        self.pair_abi = pair_abi

        self.bot = []
        if len(bot)>0 and bot_abi is not None:
            self.bot = [self.w3.eth.contract(address=bot_address, abi=bot_abi) for bot_address in bot]
        
        logging.info(f"EXECUTOR bots {self.bot}")

    @timer_decorator
    def execute(self, account_id, lead_block, is_buy, pair, amount_in, amount_out_min, deadline):
        def prepare_tx_bot(signer, bot, nonce):
            tx = None            
            if is_buy:
                tx = bot.functions.buy(pair.token, deadline).build_transaction({
                    "from": signer,
                    "nonce": nonce,
                    "gas": self.gas_limit,
                    "value": Web3.to_wei(amount_in, 'ether'),
                })
            else:
                tx = bot.functions.sell(pair.token, signer, deadline).build_transaction({
                    "from": signer,
                    "nonce": nonce,
                    "gas": self.gas_limit,
                })

            return tx
        
        signer = self.accounts[account_id].w3_account.address
        priv_key = self.accounts[account_id].private_key
        bot = self.bot[account_id]

        try:
            logging.info(f"account address {self.accounts[account_id].w3_account.address} in {amount_in} outMin {amount_out_min} deadline {deadline} isBuy {is_buy}")

            # get nonce onchain
            nonce = self.w3.eth.get_transaction_count(signer)

            tx = prepare_tx_bot(signer, bot, nonce)
            
            if tx is None:
                raise Exception(f"create tx failed")
            
            # send raw tx
            signed = self.w3.eth.account.sign_transaction(tx, priv_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed.rawTransaction)
            logging.debug(f"created tx hash {Web3.to_hex(tx_hash)}")

            tx_receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

            logging.debug(f"tx receipt {tx_receipt}")
            logging.info(f"{amount_in} tx hash {Web3.to_hex(tx_hash)} in block #{tx_receipt['blockNumber']} with status {tx_receipt['status']}")

            # send acknowledgement
            amount_out = 0
            if tx_receipt['status'] == TxStatus.SUCCESS:
                pair_contract = self.w3.eth.contract(address=pair.address, abi=self.pair_abi)
                swap_logs = pair_contract.events.Swap().process_receipt(tx_receipt, errors=DISCARD)
                logging.debug(f"swap logs {swap_logs[0]}")

                swap_logs = swap_logs[0]

                amount_out = Web3.from_wei(swap_logs['args']['amount0Out'], 'ether') if pair.token_index==0 else Web3.from_wei(swap_logs['args']['amount1Out'], 'ether')
                if not is_buy:
                    amount_out = Web3.from_wei(swap_logs['args']['amount1Out'], 'ether') if pair.token_index==0 else Web3.from_wei(swap_logs['args']['amount0Out'], 'ether')

            ack = ExecutionAck(
                lead_block=lead_block,
                block_number=tx_receipt['blockNumber'],
                tx_hash=Web3.to_hex(tx_hash),
                tx_status=tx_receipt['status'],
                pair=pair,
                amount_in=amount_in,
                amount_out=amount_out,
                is_buy=is_buy,
                signer=signer,
                bot=bot.address,
            )

            logging.info(f"EXECUTOR ack {ack}")
            self.report_sender.put(ack)

            return
        except Exception as e:
            logging.error(f"EXECUTOR order {pair} amountIn {amount_in} isBuy {is_buy} catch exception {e}")

        ack = ExecutionAck(
            lead_block=lead_block,
            block_number=lead_block,
            tx_hash='0x',
            tx_status=TxStatus.FAILED,
            pair=pair,
            amount_in=amount_in,
            amount_out=0,
            is_buy=is_buy,
            signer=signer,
            bot=bot.address,
        )

        logging.info(f"EXECUTOR failed execution ack {ack}")
        self.report_sender.put(ack)

    async def run(self):
        logging.info(f"EXECUTOR listen for order...")
        executor = ThreadPoolExecutor(max_workers=len(self.accounts))
        counter = 0
        while True:
            execution_data = await self.order_receiver.coro_get()

            if execution_data is not None and isinstance(execution_data, ExecutionOrder):
                logging.info(f"EXECUTOR receive order #{counter} {execution_data}")
                deadline = execution_data.block_timestamp + self.deadline_delay if execution_data.block_timestamp > 0 else self.get_block_timestamp() + self.deadline_delay
                
                if execution_data.signer is None:
                    counter += 1
                    future = executor.submit(self.execute, 
                                            (counter - 1) % len(self.accounts),
                                            execution_data.block_number,
                                            execution_data.is_buy,
                                            execution_data.pair,
                                            execution_data.amount_in,
                                            execution_data.amount_out_min, 
                                            deadline,
                                            )
                else:
                    idx = None
                    for idx, acct in enumerate(self.accounts):
                        if acct.w3_account.address.lower() == execution_data.signer.lower():
                            id = idx
                            break
                    if idx is not None:
                        future = executor.submit(self.execute,
                            idx,
                            execution_data.block_number,
                            execution_data.is_buy,
                            execution_data.pair,
                            execution_data.amount_in,
                            execution_data.amount_out_min, 
                            deadline,
                        )
                    else:
                        logging.error(f"EXECUTOR not found signer for order {execution_data}")
            else:
                logging.warning(f"invalid order {execution_data}")


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    logging.basicConfig(level=logging.INFO)

    ROUTER_ABI = load_abi(f"{os.path.dirname(__file__)}/../contracts/abis/UniRouter.abi.json")
    WETH_ABI = load_abi(f"{os.path.dirname(__file__)}/../contracts/abis/WETH.abi.json")
    ERC20_ABI = load_abi(f"{os.path.dirname(__file__)}/../contracts/abis/ERC20.abi.json")
    PAIR_ABI = load_abi(f"{os.path.dirname(__file__)}/../contracts/abis/UniV2Pair.abi.json")
    BOT_ABI = load_abi(f"{os.path.dirname(__file__)}/../contracts/abis/InspectBot.abi.json")

    import aioprocessing

    order_receiver = aioprocessing.AioQueue()
    report_sender = aioprocessing.AioQueue()

    executor = BuySellExecutor(
        http_url=os.environ.get('HTTPS_URL'),
        treasury_key=os.environ.get('PRIVATE_KEY'),
        executor_keys=os.environ.get('EXECUTION_KEYS').split(','),
        order_receiver=order_receiver,
        report_sender=report_sender,
        gas_limit=250*10**3,
        max_fee_per_gas=0.01*10**9,
        max_priority_fee_per_gas=25*10**9,
        deadline_delay=30,
        weth=os.environ.get('WETH_ADDRESS'),
        router=os.environ.get('ROUTER_ADDRESS'),
        router_abi=ROUTER_ABI,
        erc20_abi=ERC20_ABI,
        pair_abi=PAIR_ABI,
        bot=os.environ.get('INSPECTOR_BOT').split(','),
        bot_abi=BOT_ABI,
    )

    # queue jobs
    # order_receiver.put(ExecutionOrder(
    #     block_number=0, 
    #     block_timestamp=0, 
    #     pair=Pair(
    #         address='0x36F344CB80236a072516E04c9a1962D98A36a447',
    #         token='0xC92ac7514057bE21789BF3662Ed7Ee645c0D402a',
    #         token_index=1,
    #     ) , 
    #     amount_in=0.00001,
    #     amount_out_min=0,
    #     is_buy=True))
    
    # order_receiver.put(ExecutionOrder(
    #     block_number=0, 
    #     block_timestamp=0, 
    #     pair=Pair(
    #         address='0x36F344CB80236a072516E04c9a1962D98A36a447',
    #         token='0xC92ac7514057bE21789BF3662Ed7Ee645c0D402a',
    #         token_index=1,
    #     ) , 
    #     amount_in=0.00001,
    #     amount_out_min=0,
    #     is_buy=True))
    
    # order_receiver.put(ExecutionOrder(
    #     block_number=0, 
    #     block_timestamp=0, 
    #     pair=Pair(
    #         address='0x36F344CB80236a072516E04c9a1962D98A36a447',
    #         token='0xC92ac7514057bE21789BF3662Ed7Ee645c0D402a',
    #         token_index=1,
    #     ) , 
    #     amount_in=0.00001,
    #     amount_out_min=0,
    #     is_buy=True))
    
    order_receiver.put(ExecutionOrder(
        block_number=0,
        block_timestamp=0,
        pair=Pair(
            address='0x36F344CB80236a072516E04c9a1962D98A36a447',
            token='0xC92ac7514057bE21789BF3662Ed7Ee645c0D402a',
            token_index=1,
        ),
        amount_in=0,
        amount_out_min=0,
        is_buy=False,
        signer='0xe980767788694BFbD5934a51E508c1987bD29cD4',
        bot='0xBCd8d2824B815285b1E8E8574737fCb911efeAE4',        
        ))

    asyncio.run(executor.run())