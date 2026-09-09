from rest_framework import serializers

from .filters import classify
from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.name", read_only=True, default="System")
    action_type = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = ["log_id", "user", "user_name", "action", "action_type", "timestamp"]
        read_only_fields = ["log_id", "timestamp", "action_type"]

    def get_action_type(self, obj):
        return classify(obj.action)
