import asyncio
import os
import logging
from datetime import datetime

import sys # for testing
sys.path.append('..')

from library import Singleton
from data import ReportData, ReportDataType, BlockData, Pair

import django
from django.utils.timezone import make_aware
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "admin.settings")
django.setup()

from console.models import Block, Transaction, WatchingList, Position
import console.models

class Reporter(metaclass=Singleton):
    def __init__(self, receiver):
        self.receiver = receiver

    async def run(self):
        logging.info(f"listen for report...")
        while True:
            report = await self.receiver.coro_get()
            logging.info(f"reporter receive {report}")

            await self.save_to_db(report)

    async def save_to_db(self, report):
        try:
            if report.type == ReportDataType.BLOCK:
                block = await Block.objects.filter(block_number=report.data.block_number).afirst()
                if block is None:
                    block = Block(
                        block_number=report.data.block_number,
                        block_timestamp=report.data.block_timestamp,
                        base_fee=report.data.base_fee,
                        gas_used=report.data.gas_used,
                        gas_limit=report.data.gas_limit,
                    )
                    await block.asave()
                    logging.info(f"block saved successfully {block.id}")
                else:
                    logging.info(f"block found id #{block.id}")

                for pair in report.data.pairs:
                    pair_ins = await console.models.Pair.objects.filter(address=pair.address).afirst()
                    if pair_ins is None:
                        pair_ins = console.models.Pair(
                            address=pair.address,
                            token=pair.token,
                            token_index=pair.token_index,
                            reserve_token=pair.reserveToken,
                            reserve_eth=pair.reserveETH,
                            deployed_at=make_aware(datetime.fromtimestamp(report.data.block_timestamp)),
                        )
                        await pair_ins.asave()
                        logging.info(f"pair saved with id #{pair_ins.id}")
                    else:
                        logging.info(f"pair exists id #{pair_ins.id}")
            else:
                raise Exception(f"report type {report.type} is unsupported")
            
        except Exception as e:
            logging.error(f"save data to db failed with error {e}")

if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv()
    logging.basicConfig(level=logging.INFO)

    import aioprocessing

    broker = aioprocessing.AioQueue()

    reporter = Reporter(broker)

    # block
    broker.put(ReportData(
        type = ReportDataType.BLOCK,
        data = BlockData(
            block_number=1,
            block_timestamp=1722669970,
            base_fee=1000,
            gas_used=10000,
            gas_limit=10**6,
            pairs=[Pair(
                address='0xfoo1',
                token='0xbar',
                token_index=1,
                reserveToken=1,
                reserveETH=1,
            )],
        )
    ))

    asyncio.run(reporter.run())
