from django.contrib import admin

from .models import Requisition, RequisitionItem


@admin.register(Requisition)
class RequisitionAdmin(admin.ModelAdmin):
    list_display = ("req_id", "user", "status", "created_at")
    list_filter = ("status", "created_at")


@admin.register(RequisitionItem)
class RequisitionItemAdmin(admin.ModelAdmin):
    list_display = ("req_item_id", "requisition", "item", "quantity")
