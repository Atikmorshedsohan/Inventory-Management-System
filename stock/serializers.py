from rest_framework import serializers

from catalog.models import Room

from .models import PendingStockTransaction, RoomItemHistory, StockTransaction


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
    from_room_name = serializers.CharField(source="from_room.room_name", read_only=True)
    to_room_name = serializers.CharField(source="to_room.room_name", read_only=True)
    user_name = serializers.CharField(source="user.name", read_only=True, allow_null=True)

    class Meta:
        model = RoomItemHistory
        fields = [
            "history_id", "item", "item_name", "from_room", "from_room_name",
            "to_room", "to_room_name", "user", "user_name", "moved_at", "remarks",
        ]
        read_only_fields = ["history_id", "moved_at"]


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
        read_only_fields = [
            "pending_id", "requested_at", "approved_by", "approved_by_name", "approved_at",
        ]
