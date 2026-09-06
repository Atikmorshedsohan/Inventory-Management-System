from django.contrib import admin
from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 1


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['order_number', 'customer', 'status', 'total_amount', 'created_by', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['order_number', 'customer__name']
    inlines = [OrderItemInline]
