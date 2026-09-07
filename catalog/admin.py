from django.contrib import admin

from .models import Category, Item, PendingItem, Room


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("category_id", "category_name")
    search_fields = ("category_name",)


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ("room_id", "room_name", "room_type", "room_key", "location")
    search_fields = ("room_name", "location")
    list_filter = ("room_type",)


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("item_id", "item_name", "category", "room", "unit", "quantity", "min_quantity")
    list_filter = ("category", "room")
    search_fields = ("item_name",)


@admin.register(PendingItem)
class PendingItemAdmin(admin.ModelAdmin):
    list_display = ("pending_item_id", "item_name", "category", "quantity", "requested_by", "status", "requested_at")
    list_filter = ("status", "requested_at")
    search_fields = ("item_name",)
    readonly_fields = ("requested_at",)
