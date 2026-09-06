from django.contrib import admin
from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['log_id', 'user', 'action', 'timestamp']
    list_filter = ['timestamp']
    search_fields = ['user__name', 'action']
    readonly_fields = ['user', 'action', 'timestamp']
