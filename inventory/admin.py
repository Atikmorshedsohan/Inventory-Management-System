from django.contrib import admin
from . import models

@admin.register(models.User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("user_id", "name", "email", "role", "is_staff", "created_at")
    search_fields = ("name", "email")
    list_filter = ("role", "is_staff")

@admin.register(models.Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("category_id", "category_name")
    search_fields = ("category_name",)

@admin.register(models.Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("item_id", "item_name", "category", "room", "unit", "quantity", "min_quantity")
    list_filter = ("category", "room")
    search_fields = ("item_name",)

@admin.register(models.StockTransaction)
class StockTransactionAdmin(admin.ModelAdmin):
    list_display = ("transaction_id", "item", "type", "quantity", "user", "timestamp")
    list_filter = ("type", "timestamp")
    search_fields = ("item__item_name", "user__name")
    readonly_fields = ("timestamp",)
    ordering = ("-timestamp",)

@admin.register(models.Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ("room_id", "room_name", "room_type", "room_key", "location")
    search_fields = ("room_name", "location")
    list_filter = ("room_type",)

@admin.register(models.Requisition)
class RequisitionAdmin(admin.ModelAdmin):
    list_display = ("req_id", "user", "status", "created_at")
    list_filter = ("status", "created_at")

@admin.register(models.RequisitionItem)
class RequisitionItemAdmin(admin.ModelAdmin):
    list_display = ("req_item_id", "requisition", "item", "quantity")

@admin.register(models.AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("log_id", "user", "action", "timestamp")
    list_filter = ("timestamp",)

@admin.register(models.RoomItemHistory)
class RoomItemHistoryAdmin(admin.ModelAdmin):
    list_display = ("history_id", "item", "from_room", "to_room", "user", "moved_at")
    list_filter = ("moved_at", "from_room", "to_room")

@admin.register(models.PendingStockTransaction)
class PendingStockTransactionAdmin(admin.ModelAdmin):
    list_display = ("pending_id", "item", "type", "quantity", "room", "requested_by", "status", "requested_at")
    list_filter = ("status", "type", "requested_at", "room")
    search_fields = ("item__item_name", "requested_by__name")
    readonly_fields = ("requested_at", "approved_at")
    ordering = ("-requested_at",)

@admin.register(models.PendingItem)
class PendingItemAdmin(admin.ModelAdmin):
    list_display = ("pending_item_id", "item_name", "category", "quantity", "requested_by", "status", "requested_at")
    list_filter = ("status", "requested_at")
    search_fields = ("item_name",)
    readonly_fields = ("requested_at",)