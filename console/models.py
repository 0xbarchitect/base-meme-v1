from django.db import models

# Create your models here.
class Block(models.Model):
    class Meta():
        db_table = 'block'

    id = models.BigAutoField(primary_key=True)
    block_number = models.BigIntegerField(unique=True)
    block_timestamp = models.BigIntegerField(null=True, default=0)
    base_fee = models.BigIntegerField(null=True, default=0)
    gas_used = models.BigIntegerField(null=True, default=0)
    gas_limit = models.BigIntegerField(null=True, default=0)
    reserve0 = models.FloatField(null=True, default=0)
    reserve1 = models.FloatField(null=True, default=0)
    amount0_diff = models.FloatField(null=True, default=0)
    amount1_diff = models.FloatField(null=True, default=0)

    created_at = models.DateTimeField(null=True,auto_now_add=True)
    updated_at = models.DateTimeField(null=True,auto_now=True)
    is_deleted = models.IntegerField(null=True,default=0)

    def __str__(self) -> str:
        return str(self.block_number)
    

class Transaction(models.Model):
    class Meta():
        db_table = 'transaction'

    id = models.BigAutoField(primary_key=True)
    tx_hash = models.CharField(max_length=66, unique=True)
    block = models.ForeignKey(Block, on_delete=models.DO_NOTHING)
    sender = models.CharField(max_length=42, null=True)
    to = models.CharField(max_length=42, null=True)    
    value = models.FloatField(null=True, default=0)
    gas_limit = models.FloatField(null=True, default=0)
    max_priority_fee_per_gas = models.FloatField(null=True, default=0)
    max_fee_per_gas = models.FloatField(null=True, default=0)
    status = models.IntegerField(null=True, default=0)

    created_at = models.DateTimeField(null=True,auto_now_add=True)
    updated_at = models.DateTimeField(null=True,auto_now=True)
    is_deleted = models.IntegerField(null=True,default=0)

    def __str__(self) -> str:
        return str(self.tx_hash)
    
class SwapTokenForNative(models.Model):
    class Meta():
        db_table = 'swap_token_for_native'

    id = models.BigAutoField(primary_key=True)
    transaction = models.ForeignKey(Transaction, on_delete=models.DO_NOTHING)
    lead_block = models.ForeignKey(Block, on_delete=models.DO_NOTHING, null=True)

    amount_in = models.FloatField(null=True, default=0)
    amount_out_min_native = models.FloatField(null=True, default=0)
    to = models.CharField(max_length=42, null=True)
    deadline = models.BigIntegerField(null=True, default=0)

    created_at = models.DateTimeField(null=True,auto_now_add=True)
    updated_at = models.DateTimeField(null=True,auto_now=True)
    is_deleted = models.IntegerField(null=True,default=0)

    def __str__(self) -> str:
        return f"{str(self.transaction.block.block_number)}_{str(self.transaction.tx_hash)}"
    
class SwapEvent(models.Model):
    class Meta():
        db_table = 'swap_event'

    id = models.BigAutoField(primary_key=True)
    transaction = models.ForeignKey(Transaction, on_delete=models.DO_NOTHING)

    sender = models.CharField(max_length=42, null=True)
    to = models.CharField(max_length=42, null=True)
    amount0_in = models.FloatField(null=True, default=0)
    amount1_in = models.FloatField(null=True, default=0)
    amount0_out = models.FloatField(null=True, default=0)
    amount1_out = models.FloatField(null=True, default=0)

    created_at = models.DateTimeField(null=True,auto_now_add=True)
    updated_at = models.DateTimeField(null=True,auto_now=True)
    is_deleted = models.IntegerField(null=True,default=0)

    def __str__(self) -> str:
        return f"{str(self.transaction.block.block_number)}_{str(self.transaction.tx_hash)}"
    

