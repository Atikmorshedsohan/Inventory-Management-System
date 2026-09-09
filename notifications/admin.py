from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        "notification_id", "recipient", "category", "level", "title",
        "is_read", "created_at",
    )
    list_filter = ("category", "level", "is_read", "created_at")
    search_fields = ("title", "message", "recipient__name", "recipient__email")
    readonly_fields = ("created_at", "read_at")
    ordering = ("-created_at",)
