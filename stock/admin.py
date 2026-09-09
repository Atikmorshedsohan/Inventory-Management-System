from django.contrib import admin

from .models import (
    PendingStockTransaction,
    RoomItemHistory,
    StockImportBatch,
    StockTransaction,
)


@admin.register(StockTransaction)
class StockTransactionAdmin(admin.ModelAdmin):
    list_display = ("transaction_id", "item", "type", "quantity", "user", "timestamp")
    list_filter = ("type", "timestamp")
    search_fields = ("item__item_name", "user__name")
    readonly_fields = ("timestamp",)
    ordering = ("-timestamp",)


@admin.register(RoomItemHistory)
class RoomItemHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "history_id", "item", "transfer_type", "quantity", "from_room", "to_room",
        "user", "moved_at",
    )
    list_filter = ("transfer_type", "moved_at", "from_room", "to_room")
    search_fields = ("item__item_name",)


@admin.register(StockImportBatch)
class StockImportBatchAdmin(admin.ModelAdmin):
    list_display = (
        "batch_id", "filename", "uploaded_by", "total_rows", "success_count",
        "error_count", "created_at",
    )
    list_filter = ("created_at",)
    search_fields = ("filename", "uploaded_by__name")
    readonly_fields = ("created_at", "report")
    ordering = ("-created_at",)


@admin.register(PendingStockTransaction)
class PendingStockTransactionAdmin(admin.ModelAdmin):
    list_display = ("pending_id", "item", "type", "quantity", "room", "requested_by", "status", "requested_at")
    list_filter = ("status", "type", "requested_at", "room")
    search_fields = ("item__item_name", "requested_by__name")
    readonly_fields = ("requested_at", "approved_at")
    ordering = ("-requested_at",)
