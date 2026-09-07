from rest_framework import serializers

from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.name", read_only=True, default="System")

    class Meta:
        model = AuditLog
        fields = ["log_id", "user", "user_name", "action", "timestamp"]
        read_only_fields = ["log_id", "timestamp"]
