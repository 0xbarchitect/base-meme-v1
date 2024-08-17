import os
import logging
from decimal import Decimal
import time

from web3 import Web3
from web3.middleware import geth_poa_middleware, construct_sign_and_send_raw_middleware

import sys # for testing
sys.path.append('..')

from library import Singleton
from data import W3Account
from helpers import timer_decorator, load_abi

GAS_LIMIT = 200*10**3
TX_SUCCESS_STATUS = 1

class BotFactory(metaclass=Singleton):
    @timer_decorator
    def __init__(self, http_url, manager_key, bot_factory, bot_factory_abi, bot_implementation, router, pair_factory, weth) -> None:
        self.http_url = http_url
        self.w3 = Web3(Web3.HTTPProvider(http_url))
        if self.w3.is_connected() == True:
            logging.info(f"FACTORY web3 provider {http_url} connected")

        self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)

        self.manager = self.w3.eth.account.from_key(manager_key)
        self.w3.middleware_onion.add(construct_sign_and_send_raw_middleware(self.manager))
        self.w3.eth.default_account = self.manager.address

        self.bot_factory = self.w3.eth.contract(address=bot_factory,abi=bot_factory_abi)
        self.bot_implementation = bot_implementation

        self.router = router
        self.pair_factory = pair_factory
        self.weth = weth

    @timer_decorator
    def create_bot(self, owner) -> None:
        try:
            nonce = self.w3.eth.get_transaction_count(self.manager.address)

            tx = self.bot_factory.functions.createBot(Web3.to_checksum_address(self.bot_implementation),
                                                    Web3.keccak(text=str(time.time())),
                                                    Web3.to_checksum_address(owner),
                                                    Web3.to_checksum_address(self.router),
                                                    Web3.to_checksum_address(self.pair_factory),
                                                    Web3.to_checksum_address(self.weth),
                                                    ).build_transaction({
                                                        "from": self.manager.address,
                                                        "nonce": nonce,
                                                        "gas": GAS_LIMIT,
                                                    })
            tx_hash = self.w3.eth.send_transaction(tx)
            tx_receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            if tx_receipt['status'] == TX_SUCCESS_STATUS:
                bot_created_logs = self.bot_factory.events.BotCreated().process_receipt(tx_receipt)
                logging.info(f"FACTORY successfully create bot with owner {owner} at {bot_created_logs[0]['args']['bot']}")
            else:
                logging.error(f"FACTORY create bot with owner {owner} failed {tx_receipt}")

        except Exception as e:
            logging.error(f"FACTORY create bot with owner {owner} error {e}")

if __name__=="__main__":
    from dotenv import load_dotenv
    load_dotenv()
    logging.basicConfig(level=logging.INFO)

    BOT_FACTORY_ABI = load_abi(f"{os.path.dirname(__file__)}/../contracts/abis/BotFactory.abi.json")

    factory = BotFactory(
        http_url=os.environ.get('HTTPS_URL'),
        manager_key=os.environ.get('MANAGER_KEY'),
        bot_factory=os.environ.get('BOT_FACTORY'),
        bot_factory_abi=BOT_FACTORY_ABI,
        bot_implementation=os.environ.get('BOT_IMPLEMENTATION'),
        router=os.environ.get('ROUTER_ADDRESS'),
        pair_factory=os.environ.get('FACTORY_ADDRESS'),
        weth=os.environ.get('WETH_ADDRESS'),
    )

    factory.create_bot("0xe980767788694BFbD5934a51E508c1987bD29cD4")