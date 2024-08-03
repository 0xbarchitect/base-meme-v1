from django.contrib import admin
from django.utils.html import format_html

from console.models import Block, Transaction

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

console_admin_site = ConsoleAdminSite(name="console_admin")

console_admin_site.register(Block, BlockAdmin)
console_admin_site.register(Transaction, TransactionAdmin)
