from rest_framework import serializers

from .models import KeyAuditLog, KeyBorrow, RoomKey
from .utils import user_display


class RoomKeySerializer(serializers.ModelSerializer):
    assigned_to_name = serializers.CharField(source="assigned_to.name", read_only=True, allow_null=True)

    class Meta:
        model = RoomKey
        fields = [
            "key_id", "room_name", "key_number", "description", "status",
            "assigned_to", "assigned_to_name", "assigned_date", "last_location",
            "created_at", "updated_at",
        ]
        read_only_fields = ["key_id", "created_at", "updated_at"]


class KeyAuditLogSerializer(serializers.ModelSerializer):
    key_number = serializers.CharField(source="key.key_number", read_only=True)
    performed_by_name = serializers.CharField(source="performed_by.name", read_only=True, allow_null=True)

    class Meta:
        model = KeyAuditLog
        fields = [
            "log_id", "key", "key_number", "action",
            "performed_by", "performed_by_name", "notes", "timestamp",
        ]
        read_only_fields = ["log_id", "timestamp"]


class KeyBorrowSerializer(serializers.ModelSerializer):
    key_number = serializers.CharField(source="key.key_number", read_only=True)
    room_name = serializers.CharField(source="key.room_name", read_only=True)
    borrower_name = serializers.SerializerMethodField()
    approver_name = serializers.SerializerMethodField()
    handed_over_by_name = serializers.SerializerMethodField()
    is_overdue = serializers.SerializerMethodField()
    awaiting_pickup = serializers.BooleanField(read_only=True)

    class Meta:
        model = KeyBorrow
        fields = [
            "borrow_id", "key", "key_number", "room_name", "borrower", "borrower_name",
            "approver", "approver_name", "purpose", "status", "requested_at",
            "approved_at", "borrowed_at", "handed_over_by", "handed_over_by_name",
            "handover_notes", "awaiting_pickup", "expected_return_at", "returned_at",
            "rejection_reason", "notes", "is_overdue", "created_at",
        ]
        read_only_fields = [
            "borrow_id", "requested_at", "approved_at", "borrowed_at", "returned_at",
            "created_at", "handed_over_by", "handover_notes", "awaiting_pickup",
        ]

    def get_borrower_name(self, obj):
        return user_display(obj.borrower)

    def get_approver_name(self, obj):
        return user_display(obj.approver) if obj.approver else None

    def get_handed_over_by_name(self, obj):
        return user_display(obj.handed_over_by) if obj.handed_over_by else None

    def get_is_overdue(self, obj):
        return obj.is_overdue
