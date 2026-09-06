from django.contrib import admin
from .models import Requisition, RequisitionItem


class RequisitionItemInline(admin.TabularInline):
    model = RequisitionItem
    extra = 1


@admin.register(Requisition)
class RequisitionAdmin(admin.ModelAdmin):
    list_display = ['req_id', 'user', 'status', 'created_at', 'purpose']
    list_filter = ['status', 'created_at']
    search_fields = ['user__name', 'purpose']
    inlines = [RequisitionItemInline]


@admin.register(RequisitionItem)
class RequisitionItemAdmin(admin.ModelAdmin):
    list_display = ['req_item_id', 'requisition', 'item', 'quantity']
    search_fields = ['item__item_name', 'requisition__req_id']
