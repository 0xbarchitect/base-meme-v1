import asyncio
import os
import logging
from datetime import datetime
from decimal import Decimal
from time import time

import sys # for testing
sys.path.append('..')

from library import Singleton
from data import ReportData, ReportDataType, BlockData, Pair, ExecutionAck

import django
from django.utils.timezone import make_aware
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "admin.settings")
django.setup()

from console.models import Block, Transaction, Position, PositionTransaction
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
        async def save_block(report):
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
                        reserve_token=pair.reserve_token,
                        reserve_eth=pair.reserve_eth,
                        deployed_at=make_aware(datetime.fromtimestamp(report.data.block_timestamp)),
                    )
                    await pair_ins.asave()
                    logging.info(f"pair saved with id #{pair_ins.id}")
                else:
                    logging.info(f"pair exists id #{pair_ins.id}")

        async def save_position(execution_ack):
            block = await Block.objects.filter(block_number=execution_ack.block_number).afirst()
            if block is None:
                block = Block(
                    block_number=execution_ack.block_number,
                )
                await block.asave()
                logging.info(f"block saved successfully {block.id}")
            else:
                logging.info(f"block found id #{block.id}")

            tx = await Transaction.objects.filter(tx_hash=execution_ack.tx_hash).afirst()
            if tx is None:
                tx = Transaction(
                    block=block,
                    tx_hash=execution_ack.tx_hash,
                    status=execution_ack.tx_status,
                )
                await tx.asave()
                logging.info(f"tx saved id #{tx.id}")
            else:
                logging.info(f"tx exists id #{tx.id}")

            pair = await console.models.Pair.objects.filter(address=execution_ack.pair.address,token=execution_ack.pair.token).afirst()
            if pair is None:
                pair = console.models.Pair(
                    address=execution_ack.pair.address,
                    token=execution_ack.pair.token,
                )
                await pair.asave()
                logging.info(f"pair saved id #{pair.id}")
            else:
                logging.info(f"pair exists id #{pair.id}")

            position = await Position.objects.filter(pair__address=execution_ack.pair.address, is_deleted=0).afirst()
            if position is None:
                position = Position(
                    pair=pair,
                    amount=execution_ack.amount_out if execution_ack.is_buy else 0,
                    buy_price=Decimal(execution_ack.amount_in)/Decimal(execution_ack.amount_out) if execution_ack.amount_out>0 and execution_ack.is_buy else 0,
                    purchased_at=make_aware(datetime.fromtimestamp(int(time()))),
                    is_liquidated=0 if execution_ack.is_buy else 1,
                    sell_price=Decimal(execution_ack.amount_out)/Decimal(execution_ack.amount_in) if execution_ack.amount_in>0 and not execution_ack.is_buy else 0,
                    liquidation_attempts=0,
                    pnl=0,
                )
                await position.asave()
                logging.info(f"position saved id #{position.id}")
            else:
                logging.info(f"position exists id #{position.id}, update...")

                if not execution_ack.is_buy:
                    position.is_liquidated=1
                    position.liquidated_at=make_aware(datetime.fromtimestamp(int(time())))
                    position.sell_price=Decimal(execution_ack.amount_out)/Decimal(execution_ack.amount_in) if execution_ack.amount_in>0 and not execution_ack.is_buy else 0
                    position.liquidation_attempts=position.liquidation_attempts+1
                    position.pnl=(Decimal(position.sell_price)/Decimal(position.buy_price)-Decimal(1))*Decimal(100)

                    await position.asave()

            position_tx = await PositionTransaction.objects.filter(position__id=position.id, transaction__id=tx.id).afirst()
            if position_tx is None:
                position_tx = PositionTransaction(
                    position=position,
                    transaction=tx,
                    is_buy=execution_ack.is_buy,
                )
                await position_tx.asave()
                logging.info(f"position tx saved id #{position_tx.id}")
            else:
                logging.info(f"position tx exists id #{position_tx.id}")

        try:
            if report.type == ReportDataType.BLOCK:
                await save_block(report)
            elif report.type == ReportDataType.EXECUTION:
                if report.data is not None and isinstance(report.data, ExecutionAck):
                    await save_position(report.data)
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
    # broker.put(ReportData(
    #     type = ReportDataType.BLOCK,
    #     data = BlockData(
    #         block_number=1,
    #         block_timestamp=1722669970,
    #         base_fee=1000,
    #         gas_used=10000,
    #         gas_limit=10**6,
    #         pairs=[Pair(
    #             address='0xfoo1',
    #             token='0xbar',
    #             token_index=1,
    #             reserve_token=1,
    #             reserve_eth=1,
    #         )],
    #     )
    # ))

    # execution
    broker.put(ReportData(
        type = ReportDataType.EXECUTION,
        data = ExecutionAck(
            lead_block=1,
            block_number=2,
            tx_hash='0xabc',
            tx_status=1,
            pair=Pair(
                token='0xfoo',
                token_index=1,
                address='0xbar',
                reserve_eth=1,
                reserve_token=1,
            ),
            amount_in=1,
            amount_out=1000,
            is_buy=True,
        )
    ))

    asyncio.run(reporter.run())
