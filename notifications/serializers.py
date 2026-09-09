from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source="item.item_name", read_only=True, allow_null=True)

    class Meta:
        model = Notification
        fields = [
            "notification_id", "category", "level", "title", "message", "link",
            "item", "item_name", "is_read", "created_at", "read_at",
        ]
        read_only_fields = [
            "notification_id", "category", "level", "title", "message", "link",
            "item", "item_name", "created_at", "read_at",
        ]
