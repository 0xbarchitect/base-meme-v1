from django.contrib import admin
from django.utils.html import format_html

from console.models import Block, Transaction, Pair, WatchingList, Position

class ConsoleAdminSite(admin.AdminSite):
    index_title = "Console homepage"

class NoDeletePermissionModelAdmin(admin.ModelAdmin):
    def has_delete_permission(self, request, obj=None):
        return False
    
    def has_add_permission(self, request):
        return False
    
class BlockAdmin(NoDeletePermissionModelAdmin):
    list_filter = ['is_deleted']
    list_display = ('id', 'block_number', 'block_timestamp', 'base_fee', 'gas_used', 'buttons')
    fields = ('block_number', 'block_timestamp', 'base_fee', 'gas_used', 'gas_limit',)
    readonly_fields = ('block_number', 'block_timestamp', 'base_fee', 'gas_used', 'gas_limit',)
    
    @admin.display(description='Actions')
    def buttons(self, obj):
        return format_html(f"""
        <button><a class="btn" href="/admin/console/block/{obj.id}/change/">Edit</a></button>&emsp;
        """)
    
class TransactionAdmin(NoDeletePermissionModelAdmin):
    list_filter = ['is_deleted']
    list_display = ('id', 'block', 'tx_hash', 'sender', 'status', 'buttons')
    fields = ('block', 'tx_hash', 'sender', 'to', 'value', 'gas_limit', 'max_priority_fee_per_gas', 'max_fee_per_gas', 'status',)
    readonly_fields = ('block', 'tx_hash', 'sender', 'to', 'value', 'gas_limit', 'max_priority_fee_per_gas', 'max_fee_per_gas', 'status')
    
    @admin.display(description='Actions')
    def buttons(self, obj):
        return format_html(f"""
        <button><a class="btn" href="/admin/console/transaction/{obj.id}/change/">Edit</a></button>&emsp;
        """)

class PairAdmin(NoDeletePermissionModelAdmin):
    list_filter = ['is_deleted']
    list_display = ('id', 'address', 'token', 'token_index', 'reserve_token', 'reserve_eth', 'deployed_at', 'buttons')
    fields = ('address', 'token', 'token_index', 'reserve_token', 'reserve_eth', 'deployed_at',)
    readonly_fields = ('address', 'token', 'token_index', 'reserve_token', 'reserve_eth', 'deployed_at',)
    
    @admin.display(description='Actions')
    def buttons(self, obj):
        return format_html(f"""
        <button><a class="btn" href="/admin/console/pair/{obj.id}/change/">Edit</a></button>&emsp;
        """)
    
class WatchingListAdmin(NoDeletePermissionModelAdmin):
    list_filter = ['is_deleted']
    list_display = ('id', 'pair',  'buttons')
    fields = ('pair',)
    readonly_fields = ('pair',)
    
    @admin.display(description='Actions')
    def buttons(self, obj):
        return format_html(f"""
        <button><a class="btn" href="/admin/console/watchinglist/{obj.id}/change/">Edit</a></button>&emsp;
        """)
    
class PositionAdmin(NoDeletePermissionModelAdmin):
    list_filter = ['is_deleted']
    list_display = ('id', 'pair', 'amount', 'buy_price', 'purchased_at', 'is_liquidated', 'sell_price', 'liquidation_attempts', 'pnl', 'buttons')
    fields = ('pair', 'amount', 'buy_price', 'purchased_at', 'is_liquidated', 'sell_price', 'liquidation_attempts', 'pnl',)
    readonly_fields = ('pair', 'amount', 'buy_price', 'purchased_at', 'is_liquidated', 'sell_price', 'liquidation_attempts', 'pnl',)
    
    @admin.display(description='Actions')
    def buttons(self, obj):
        return format_html(f"""
        <button><a class="btn" href="/admin/console/position/{obj.id}/change/">Edit</a></button>&emsp;
        """)
    
admin_site = ConsoleAdminSite(name="console_admin")

admin_site.register(Block, BlockAdmin)
admin_site.register(Transaction, TransactionAdmin)
admin_site.register(Pair, PairAdmin)
admin_site.register(WatchingList, WatchingListAdmin)
admin_site.register(Position, PositionAdmin)
