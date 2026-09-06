# Key Management Serializers

from django.utils import timezone
from rest_framework import serializers
from . import models


class RoomKeySerializer(serializers.ModelSerializer):
    assigned_to_name = serializers.CharField(source='assigned_to.name', read_only=True, allow_null=True)

    class Meta:
        model = models.RoomKey
        fields = ['key_id', 'room_name', 'key_number', 'description', 'status', 'assigned_to', 'assigned_to_name', 'assigned_date', 'last_location', 'created_at', 'updated_at']
        read_only_fields = ['key_id', 'created_at', 'updated_at']


class KeyAuditLogSerializer(serializers.ModelSerializer):
    key_number = serializers.CharField(source='key.key_number', read_only=True)
    performed_by_name = serializers.CharField(source='performed_by.name', read_only=True, allow_null=True)

    class Meta:
        model = models.KeyAuditLog
        fields = ['log_id', 'key', 'key_number', 'action', 'performed_by', 'performed_by_name', 'notes', 'timestamp']
        read_only_fields = ['log_id', 'timestamp']


class KeyBorrowSerializer(serializers.ModelSerializer):
    key_number = serializers.CharField(source='key.key_number', read_only=True)
    room_name = serializers.CharField(source='key.room_name', read_only=True)
    key_status = serializers.CharField(source='key.status', read_only=True)
    borrower_name = serializers.CharField(source='borrower.name', read_only=True)
    approver_name = serializers.CharField(source='approver.name', read_only=True, allow_null=True)
    is_overdue = serializers.SerializerMethodField()
    waiting_minutes = serializers.SerializerMethodField()
    is_stale_pending = serializers.SerializerMethodField()

    class Meta:
        model = models.KeyBorrow
        fields = ['borrow_id', 'key', 'key_number', 'room_name', 'key_status', 'borrower', 'borrower_name', 'approver', 'approver_name', 
                  'purpose', 'status', 'requested_at', 'approved_at', 'borrowed_at', 'expected_return_at', 'returned_at', 
                  'rejection_reason', 'notes', 'is_overdue', 'waiting_minutes', 'is_stale_pending', 'created_at']
        read_only_fields = ['borrow_id', 'requested_at', 'approved_at', 'borrowed_at', 'returned_at', 'created_at']

    def get_is_overdue(self, obj):
        return obj.is_overdue

    def get_waiting_minutes(self, obj):
        if obj.status != 'pending' or not obj.requested_at:
            return None
        delta = timezone.now() - obj.requested_at
        return int(delta.total_seconds() // 60)

    def get_is_stale_pending(self, obj):
        if obj.status != 'pending' or not obj.requested_at:
            return False
        stale_minutes = self.context.get('pending_stale_minutes', 120)
        try:
            stale_minutes = int(stale_minutes)
        except (TypeError, ValueError):
            stale_minutes = 120
        return (timezone.now() - obj.requested_at).total_seconds() >= stale_minutes * 60
