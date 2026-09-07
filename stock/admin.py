from django.contrib import admin

from .models import PendingStockTransaction, RoomItemHistory, StockTransaction


@admin.register(StockTransaction)
class StockTransactionAdmin(admin.ModelAdmin):
    list_display = ("transaction_id", "item", "type", "quantity", "user", "timestamp")
    list_filter = ("type", "timestamp")
    search_fields = ("item__item_name", "user__name")
    readonly_fields = ("timestamp",)
    ordering = ("-timestamp",)


@admin.register(RoomItemHistory)
class RoomItemHistoryAdmin(admin.ModelAdmin):
    list_display = ("history_id", "item", "from_room", "to_room", "user", "moved_at")
    list_filter = ("moved_at", "from_room", "to_room")


@admin.register(PendingStockTransaction)
class PendingStockTransactionAdmin(admin.ModelAdmin):
    list_display = ("pending_id", "item", "type", "quantity", "room", "requested_by", "status", "requested_at")
    list_filter = ("status", "type", "requested_at", "room")
    search_fields = ("item__item_name", "requested_by__name")
    readonly_fields = ("requested_at", "approved_at")
    ordering = ("-requested_at",)
