from django.contrib import admin
from .models import Category, Item, StockTransaction


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['category_id', 'category_name', 'description']
    search_fields = ['category_name']


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ['item_id', 'item_name', 'category', 'unit', 'quantity', 'min_quantity']
    list_filter = ['category', 'unit']
    search_fields = ['item_name', 'description']
    
    def get_readonly_fields(self, request, obj=None):
        if obj:  # Editing existing object
            return ['quantity']  # Make quantity readonly, updated via transactions
        return []


@admin.register(StockTransaction)
class StockTransactionAdmin(admin.ModelAdmin):
    list_display = ['transaction_id', 'item', 'type', 'quantity', 'user', 'timestamp']
    list_filter = ['type', 'timestamp']
    search_fields = ['item__item_name', 'notes']
    readonly_fields = ['timestamp']
