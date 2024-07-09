import asyncio
import os
import logging

import sys # for testing
sys.path.append('..')

from library import Singleton
from data import ReportData, ReportDataType, BlockData

import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "admin.settings")
django.setup()

from console.models import Block, Transaction, SwapTokenForNative

class Reporter(metaclass=Singleton):
    def __init__(self, receiver):
        self.receiver = receiver

    async def run(self):
        print(f"listen for report...")
        while True:
            report = await self.receiver.coro_get()
            print(f"reporter receive {report}")

            await self.save_to_db(report)

    async def save_to_db(self, report):
        try:
            if report.type == ReportDataType.BLOCK:
                block = await Block.objects.filter(block_number=report.data.block_number).afirst()
                if block is None:
                    block = Block(
                        block_number=report.data.block_number,
                        block_timestamp=report.data.block_timestamp,
                        amount0_diff=report.data.amount0Diff,
                        amount1_diff=report.data.amount1Diff,
                        reserve0=report.data.reserve0,
                        reserve1=report.data.reserve1,
                    )
                    await block.asave()
                    print(f"block saved successfully {block.id}")
                else:
                    print(f"block found id #{block.id}")
                                    
            elif report.type == ReportDataType.COUNTER_TRADE:
                lead_block = await Block.objects.filter(block_number=report.data.lead_block).afirst()
                if lead_block is None:
                    print(f"not found lead_block {report.data.lead_block}, create new one...")
                    lead_block = Block(
                        block_number=report.data.lead_block
                    )
                    await lead_block.asave()
                    print(f"lead_block saved id #{lead_block.id}")
                else:
                    print(f"lead_block found id #{lead_block.id}")

                block = await Block.objects.filter(block_number=report.data.block_number).afirst()
                if block is None:
                    print(f"not found block {report.data.block_number}, create new one...")
                    block = Block(
                        block_number=report.data.block_number
                    )
                    await block.asave()
                    print(f"block saved id #{block.id}")
                else:
                    print(f"block found id #{block.id}")                

                tx = Transaction(
                    block=block,
                    tx_hash=report.data.tx_hash,
                    sender=report.data.sender,
                    status=report.data.status,
                )
                await tx.asave()
                print(f"transaction saved id #{tx.id}")

                swap_token_for_native = SwapTokenForNative(
                    lead_block=lead_block,
                    transaction=tx,
                    to=report.data.sender,
                    amount_in=report.data.amount0_in,
                    amount_out_min_native=report.data.amount1_out_min,
                    deadline=report.data.deadline,
                )
                await swap_token_for_native.asave()
                print(f"swap token for native saved id #{swap_token_for_native.id}")

            else:
                raise Exception(f"report type {report.type} is unsupported")
        except Exception as e:
            print(f"save data to db failed with error {e}")

    def dummy(self):
        block = Block(block_number=1,block_timestamp=1,)
        block.save()

        all_blocks = Block.objects.all()
        print(f"total {len(all_blocks)}")

if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv()

    import aioprocessing

    queue = aioprocessing.AioQueue()

    reporter = Reporter(queue)
    #reporter.dummy()

    queue.put(ReportData(
        type = ReportDataType.BLOCK,
        data = BlockData(
            block_number=2,
            block_timestamp=1,
            base_fee=1000,
            gas_used=10000,
            gas_limit=10**6,
            amount0Diff=0,
            amount1Diff=0,
            reserve0=1,
            reserve1=1,
        )
    ))

    queue.put(ReportData(
        type = ReportDataType.BLOCK,
        data = BlockData(
            block_number=3,
            block_timestamp=1,
            base_fee=1000,
            gas_used=10000,
            gas_limit=10**6,
            amount0Diff=0,
            amount1Diff=0,
            reserve0=1,
            reserve1=1,
        )
    ))

    queue.put(ReportData(
        type = ReportDataType.BLOCK,
        data = BlockData(
            block_number=4,
            block_timestamp=1,
            base_fee=1000,
            gas_used=10000,
            gas_limit=10**6,
            amount0Diff=0,
            amount1Diff=0,
            reserve0=1,
            reserve1=1,
        )
    ))

    asyncio.run(reporter.run())
