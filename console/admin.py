from django.contrib import admin
from django.utils.html import format_html

from console.models import Block, Transaction, Pair, Position, PositionTransaction, BlackList, Bot

class ConsoleAdminSite(admin.AdminSite):
    index_title = "Console"

class NoDeletePermissionModelAdmin(admin.ModelAdmin):
    def has_delete_permission(self, request, obj=None):
        return False
    
    def has_add_permission(self, request):
        return False
    
class FullPermissionModelAdmin(admin.ModelAdmin):
    def has_delete_permission(self, request, obj=None):
        return True
    
    def has_add_permission(self, request):
        return True
    
class BlockAdmin(FullPermissionModelAdmin):
    list_filter = ['is_deleted']
    list_display = ('id', 'block_number', 'block_timestamp', 'base_fee', 'gas_used', 'buttons')
    fields = ('block_number', 'block_timestamp', 'base_fee', 'gas_used', 'gas_limit',)
    readonly_fields = ('block_number', 'block_timestamp', 'base_fee', 'gas_used', 'gas_limit',)
    
    @admin.display(description='Actions')
    def buttons(self, obj):
        return format_html(f"""
        <button><a class="btn" href="/admin/console/block/{obj.id}/change/">Edit</a></button>&emsp;
        """)
    
class TransactionAdmin(FullPermissionModelAdmin):
    list_filter = ['is_deleted']
    list_display = ('id', 'block', 'tx_hash', 'sender', 'status', 'buttons')
    fields = ('block', 'tx_hash', 'sender', 'to', 'value', 'gas_limit', 'max_priority_fee_per_gas', 'max_fee_per_gas', 'status',)
    readonly_fields = ('block', 'tx_hash', 'sender', 'to', 'value', 'gas_limit', 'max_priority_fee_per_gas', 'max_fee_per_gas', 'status')
    
    @admin.display(description='Actions')
    def buttons(self, obj):
        return format_html(f"""
        <button><a class="btn" href="/admin/console/transaction/{obj.id}/change/">Edit</a></button>&emsp;
        """)

class PairAdmin(FullPermissionModelAdmin):
    list_filter = ['is_deleted']
    list_display = ('id', 'address', 'token', 'creator', 'reserve_token', 'reserve_eth', 'deployed_at', 'buttons')
    fields = ('address', 'token', 'token_index', 'creator', 'reserve_token', 'reserve_eth', 'deployed_at',)
    readonly_fields = ('address', 'token', 'token_index', 'creator', 'reserve_token', 'reserve_eth', 'deployed_at',)
    
    @admin.display(description='Actions')
    def buttons(self, obj):
        return format_html(f"""
        <button><a class="btn" href="/admin/console/pair/{obj.id}/change/">Edit</a></button>&emsp;
        """)
    
class PositionTransactionInline(admin.TabularInline):
    model = PositionTransaction

class PositionAdmin(FullPermissionModelAdmin):
    inlines = [PositionTransactionInline]

    list_filter = ['is_deleted']
    list_display = ('id', 'pair', 'bot', 'amount', 'purchased_at', 'is_liquidated', 'liquidated_at', 'liquidation_attempts', 'pnl', 'buttons')
    fields = ('pair', 'signer', 'bot', 'amount', 'buy_price', 'purchased_at', 'is_liquidated', 'sell_price', 'liquidated_at', 'liquidation_attempts', 'pnl',)
    readonly_fields = ('pair', 'signer', 'bot', 'amount', 'buy_price', 'purchased_at', 'is_liquidated', 'sell_price', 'liquidated_at', 'liquidation_attempts', 'pnl',)
    
    @admin.display(description='Actions')
    def buttons(self, obj):
        return format_html(f"""
        <button><a class="btn" href="/admin/console/position/{obj.id}/change/">Edit</a></button>&emsp;
        """)
    
class BlacklistAdmin(FullPermissionModelAdmin):
    list_filter = ['is_deleted']
    list_display = ('id', 'address', 'buttons')
    fields = ('address',)
    
    @admin.display(description='Actions')
    def buttons(self, obj):
        return format_html(f"""
        <button><a class="btn" href="/admin/console/blacklist/{obj.id}/change/">Edit</a></button>&emsp;
        """)
    
class BotAdmin(FullPermissionModelAdmin):
    list_filter = ['is_deleted']
    list_display = ('id', 'address', 'owner', 'deployed_at', 'number_used', 'is_failed', 'buttons')
    fields = ('address', 'owner', 'deployed_at', 'number_used', 'is_failed')
    
    @admin.display(description='Actions')
    def buttons(self, obj):
        return format_html(f"""
        <button><a class="btn" href="/admin/console/bot/{obj.id}/change/">Edit</a></button>&emsp;
        """)
    
admin_site = ConsoleAdminSite(name="console_admin")

admin_site.register(Block, BlockAdmin)
admin_site.register(Transaction, TransactionAdmin)
admin_site.register(Pair, PairAdmin)
admin_site.register(Position, PositionAdmin)
admin_site.register(BlackList, BlacklistAdmin)
admin_site.register(Bot, BotAdmin)