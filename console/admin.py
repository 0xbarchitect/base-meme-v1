from django.contrib import admin
from django.utils.html import format_html

from console.models import Block, Transaction, SwapTokenForNative, SwapEvent

class ConsoleAdminSite(admin.AdminSite):
    index_title = "Console homepage"

class NoDeletePermissionModelAdmin(admin.ModelAdmin):
    def has_delete_permission(self, request, obj=None):
        return False
    
    def has_add_permission(self, request):
        return False
    
class BlockAdmin(NoDeletePermissionModelAdmin):
    list_filter = ['is_deleted']
    list_display = ('id', 'block_number', 'block_timestamp', 'amount0_diff', 'amount1_diff', 'buttons')
    fields = ('block_number', 'block_timestamp', 'base_fee', 'gas_used', 'gas_limit', 'amount0_diff', 'amount1_diff', 'reserve0', 'reserve1',)
    readonly_fields = ('block_number', 'block_timestamp', 'base_fee', 'gas_used', 'gas_limit', 'amount0_diff', 'amount1_diff', 'reserve0', 'reserve1',)
    
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
    
class SwapTokenForNativeAdmin(NoDeletePermissionModelAdmin):
    list_filter = ['is_deleted']
    list_display = ('id', 'lead_block', 'block', 'transaction', 'amount_in', 'amount_out_min_native', 'to', 'deadline', 'status', 'buttons')
    fields = ('lead_block', 'block', 'transaction', 'amount_in', 'amount_out_min_native', 'to', 'deadline', 'status')
    readonly_fields = ('lead_block', 'block', 'transaction', 'amount_in', 'amount_out_min_native', 'to', 'deadline', 'status')
    
    @admin.display(description='Actions')
    def buttons(self, obj):
        return format_html(f"""
        <button><a class="btn" href="/admin/console/swaptokenfornative/{obj.id}/change/">Edit</a></button>&emsp;
        """)
    
    def block(self, obj):
        return format_html(f"{obj.transaction.block}")
    
    def status(self, obj):
        return format_html(f"{obj.transaction.status}")
    
class SwapEventAdmin(NoDeletePermissionModelAdmin):
    list_filter = ['is_deleted']
    list_display = ('id', 'block', 'transaction', 'sender', 'to', 'amount0_in', 'amount1_in', 'amount0_out', 'amount1_out', 'buttons')
    fields = ('block', 'transaction', 'sender', 'to', 'amount0_in', 'amount1_in', 'amount0_out', 'amount1_out',)
    readonly_fields = ('block', 'transaction', 'sender', 'to', 'amount0_in', 'amount1_in', 'amount0_out', 'amount1_out',)
    
    @admin.display(description='Actions')
    def buttons(self, obj):
        return format_html(f"""
        <button><a class="btn" href="/admin/console/swapevent/{obj.id}/change/">Edit</a></button>&emsp;
        """)
    
    def block(self, obj):
        return format_html(f"{obj.transaction.block}")
    
    def transaction(self, obj):
        return format_html(f"{obj.transaction}")

console_admin_site = ConsoleAdminSite(name="console_admin")
#console_admin_site.disable_action('delete_selected')

console_admin_site.register(Block, BlockAdmin)
console_admin_site.register(Transaction, TransactionAdmin)
console_admin_site.register(SwapTokenForNative, SwapTokenForNativeAdmin)
console_admin_site.register(SwapEvent, SwapEventAdmin)
