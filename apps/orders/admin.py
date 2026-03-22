from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline
from .models import Order, OrderItem


class OrderItemInline(TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product', 'quantity', 'price', 'subtotal')

    def subtotal(self, obj):
        return obj.subtotal
    subtotal.short_description = 'Сума'


@admin.register(Order)
class OrderAdmin(ModelAdmin):
    list_display = ('__str__', 'name', 'phone', 'delivery_type', 'payment_method', 'is_paid', 'status', 'grand_total', 'created_at')
    list_filter = ('status', 'delivery_type', 'payment_method', 'is_paid', 'created_at')
    list_editable = ('status',)
    search_fields = ('name', 'phone', 'email', 'address', 'monobank_invoice_id')
    readonly_fields = ('session_key', 'created_at', 'grand_total', 'monobank_invoice_id', 'is_paid')
    inlines = [OrderItemInline]
    date_hierarchy = 'created_at'

    def grand_total(self, obj):
        return obj.grand_total
    grand_total.short_description = 'Загальна сума'
