from rest_framework import serializers

from catalog.models import Item, Room

from .models import (
    PendingStockTransaction,
    RoomItemHistory,
    StockImportBatch,
    StockTransaction,
)


class StockTransactionSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source="item.item_name", read_only=True)
    user_name = serializers.CharField(source="user.name", read_only=True, default="System")
    room = serializers.PrimaryKeyRelatedField(
        queryset=Room.objects.all(), write_only=True, required=False, allow_null=True
    )

    class Meta:
        model = StockTransaction
        fields = [
            "transaction_id", "item", "item_name", "type", "quantity", "room",
            "user", "user_name", "timestamp", "notes",
        ]
        read_only_fields = ["transaction_id", "timestamp", "item_name", "user_name"]


class RoomItemHistorySerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source="item.item_name", read_only=True)
    dest_item_name = serializers.CharField(source="dest_item.item_name", read_only=True, allow_null=True)
    from_room_name = serializers.CharField(source="from_room.room_name", read_only=True)
    to_room_name = serializers.CharField(source="to_room.room_name", read_only=True)
    user_name = serializers.CharField(source="user.name", read_only=True, allow_null=True)

    class Meta:
        model = RoomItemHistory
        fields = [
            "history_id", "item", "item_name", "from_room", "from_room_name",
            "to_room", "to_room_name", "user", "user_name", "moved_at", "remarks",
            "transfer_type", "quantity", "dest_item", "dest_item_name",
            "source_qty_before", "source_qty_after",
            "dest_qty_before", "dest_qty_after",
        ]
        read_only_fields = ["history_id", "moved_at"]


class ItemTransferSerializer(serializers.Serializer):
    """Input for the Move Item workflow."""

    item = serializers.PrimaryKeyRelatedField(queryset=Item.objects.all())
    to_room = serializers.PrimaryKeyRelatedField(queryset=Room.objects.all())
    quantity = serializers.IntegerField(required=False, min_value=1, allow_null=True)
    remarks = serializers.CharField(required=False, allow_blank=True, default="")


class StockImportBatchSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(
        source="uploaded_by.name", read_only=True, default="System"
    )

    class Meta:
        model = StockImportBatch
        fields = [
            "batch_id", "filename", "uploaded_by", "uploaded_by_name", "created_at",
            "total_rows", "success_count", "error_count", "report",
        ]
        read_only_fields = fields


class PendingStockTransactionSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source="item.item_name", read_only=True)
    room_name = serializers.CharField(source="room.room_name", read_only=True, allow_null=True)
    requested_by_name = serializers.CharField(source="requested_by.name", read_only=True, allow_null=True)
    approved_by_name = serializers.CharField(source="approved_by.name", read_only=True, allow_null=True)

    class Meta:
        model = PendingStockTransaction
        fields = [
            "pending_id", "item", "item_name", "room", "room_name", "type", "quantity", "notes",
            "status", "requested_by", "requested_by_name", "requested_at",
            "approved_by", "approved_by_name", "approved_at", "rejection_reason",
        ]
        # ``status`` is read-only: it only moves through the audited
        # approve/reject services. Left writable, the requester could PATCH
        # their own row to "approved" and drop it out of the approval queue.
        read_only_fields = [
            "pending_id", "requested_at", "status",
            "approved_by", "approved_by_name", "approved_at",
        ]
