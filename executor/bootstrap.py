import os
import logging
from decimal import Decimal

from web3 import Web3
from web3.middleware import geth_poa_middleware, construct_sign_and_send_raw_middleware

import sys # for testing
sys.path.append('..')

from library import Singleton
from helpers import constants, load_abi
from factory import BotFactory

NUMBER_EXECUTOR=8
INITIAL_BALANCE=0.0006
GAS_PRICE_GWEI=0.02
TRANSFER_GAS_LIMIT=21000

class Bootstrap(metaclass=Singleton):
    def __init__(self, http_url, manager_key, bot_factory, bot_factory_abi, bot_implementation,
                 router, pair_factory, weth) -> None:
        self.w3 = Web3(Web3.HTTPProvider(http_url))
        if self.w3.is_connected() == True:
            logging.info(f"web3 provider {http_url} connected")

        self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        self.manager = self.w3.eth.account.from_key(manager_key)
        self.w3.middleware_onion.add(construct_sign_and_send_raw_middleware(self.manager))
        self.w3.eth.default_account = self.manager.address

        self.factory = BotFactory(
            http_url=os.environ.get('HTTPS_URL'),
            order_broker=None,
            result_broker=None,
            manager_key=manager_key,
            bot_factory=bot_factory,
            bot_factory_abi=bot_factory_abi,
            bot_implementation=bot_implementation,
            router=router,
            pair_factory=pair_factory,
            weth=weth,
        )

    def create_executor_and_fund(self, number):
        accts=[self.w3.eth.account.create() for i in range(number)]
        addresses=[acct.address for acct in accts]
        keys=[acct.key.hex()[2:] for acct in accts]
        print(f"EXECUTION_ADDRESSES=\"{','.join(addresses)}\"")
        print(f"EXECUTION_KEYS=\"{','.join(keys)}\"")

        self.fund_executor(addresses, INITIAL_BALANCE)

    def fund_executor(self, addresses, amount):
        try:
            for addr in addresses:
                tx_hash=self.w3.eth.send_transaction({
                    "from": self.manager.address,
                    "to": addr,
                    "value": Web3.to_wei(amount, 'ether'),
                })
                tx_receipt=self.w3.eth.wait_for_transaction_receipt(tx_hash)
                if tx_receipt['status']==constants.TX_SUCCESS_STATUS:
                    logging.info(f"BOOTSTRAP funding executor {addr} with balance {INITIAL_BALANCE} successfully")
                else:
                    logging.error(f"BOOTSTRAP funding executor {addr} failed {tx_receipt}")
        except Exception as e:
            logging.error(f"BOOTSTRAP funding error {e}")

    def create_bot(self, owner):
        self.factory.create_bot(owner)

    def withdraw(self, private_keys, to):
        try:
            for key in private_keys.split(','):
                acct=self.w3.eth.account.from_key(key)
                self.w3.middleware_onion.add(construct_sign_and_send_raw_middleware(acct))
                self.w3.eth.default_account = acct.address

                logging.info(f"BALANCE of {acct.address}: {Web3.from_wei(self.w3.eth.get_balance(acct.address), 'ether')}")
                value=Web3.from_wei(self.w3.eth.get_balance(acct.address), 'ether')-2*Decimal(TRANSFER_GAS_LIMIT)*Decimal(GAS_PRICE_GWEI*10**-9)
                logging.info(f"Widthdraw amount: {value}")

                tx_hash = self.w3.eth.send_transaction({
                    "from": acct.address,
                    "to": Web3.to_checksum_address(to),
                    "value": Web3.to_wei(value, 'ether'),
                })
                logging.debug(f"Tx hash {Web3.to_hex(tx_hash)}")

                tx_receipt=self.w3.eth.wait_for_transaction_receipt(tx_hash)
                if tx_receipt['status']==constants.TX_SUCCESS_STATUS:
                    logging.info(f"BOOTSTRAP widthraw fund from {acct.address} successfully")
                else:
                    logging.error(f"BOOTSTRAP widthdraw {acct.address} failed:: {tx_receipt}")
        except Exception as e:
            logging.error(f"BOOTSTRAP widthdraw error:: {e}")
        

if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv()
    logging.basicConfig(level=logging.INFO)

    BOT_FACTORY_ABI = load_abi(f"{os.path.dirname(__file__)}/../contracts/abis/BotFactory.abi.json")

    bootstrap=Bootstrap(
        http_url=os.environ.get('HTTPS_URL'),
        manager_key=os.environ.get('MANAGER_KEY'),
        bot_factory=os.environ.get('BOT_FACTORY'),
        bot_factory_abi=BOT_FACTORY_ABI,
        bot_implementation=os.environ.get('BOT_IMPLEMENTATION'),
        router=os.environ.get('ROUTER_ADDRESS'),
        pair_factory=os.environ.get('FACTORY_ADDRESS'),
        weth=os.environ.get('WETH_ADDRESS'),
    )

    # CREATE EXECUTORS
    #bootstrap.create_executor_and_fund(NUMBER_EXECUTOR)
    #bootstrap.create_bot('0x5E442193545F0d2608380dd1822Ea5d0CA6f24F7')

    # FUND EXECUTORS ON-DEMAND
    # bootstrap.fund_executor(['0x4209f8350A00A335ca057ccC61691655BbABd01A',
    #                          '0x3083Eb34dEE19e9374aAFC0F6ceE52AdD4ef1654',
    #                          '0xC451F31193B9994CaCA247E52A71dB38b1d09eD1'], INITIAL_BALANCE)

    # WITHDRAWAL
    withdraw_keys='a1c7ffb760ec956ca45459039adb516ac181aabe3e9f7f4ce02ee8f42e59ab42,8ac032d8a83a524f5073fc7d9ee3d7ac2f60dc924d7cf3cf78fe887fefa18f18,ce3d97d042d51d14ba5f2c6bec77f2d3bcfa587b64a6696fd84ffa1eae5a661e,cec251e3b4a4df5813f7610d1f7fd2d2ce81a11c015fe94e2ba3354663e69a5b,b5d57ec695ab006000a153395611d56b23eac39cf8b445bfe21a3d05e6bc2e85,b3079d96446d12708fe5bf2307d3b6899001ff62a9d7f6b786e78ddd9a91ab22'
    bootstrap.withdraw(withdraw_keys,'0xA0e4075e79aE82E1071B1636b8b9129877D94BfD')

