from rest_framework import serializers

from .models import Category, Item, PendingItem, Room


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["category_id", "category_name", "description"]
        read_only_fields = ["category_id"]


class RoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = Room
        fields = ["room_id", "room_name", "room_type", "room_key", "location"]
        read_only_fields = ["room_id"]


class ItemSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source="item_id", read_only=True)
    category = CategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        source="category",
        queryset=Category.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
    )
    room = serializers.SerializerMethodField(read_only=True)
    room_id = serializers.PrimaryKeyRelatedField(
        source="room",
        queryset=Room.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Item
        fields = [
            "id", "item_id", "item_name", "category", "category_id", "room", "room_id",
            "unit", "quantity", "opening_quantity", "min_quantity", "description",
            "updated_at",
        ]
        read_only_fields = ["id", "item_id", "updated_at"]
        extra_kwargs = {"opening_quantity": {"required": False}}

    def get_room(self, obj):
        if obj.room:
            return {
                "room_id": obj.room.room_id,
                "room_name": obj.room.room_name,
                "room_type": obj.room.room_type,
                "location": obj.room.location,
            }
        return None


class PendingItemSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.category_name", read_only=True, allow_null=True)
    room_name = serializers.CharField(source="room.room_name", read_only=True, allow_null=True)
    requested_by_name = serializers.CharField(source="requested_by.name", read_only=True, allow_null=True)
    approved_by_name = serializers.CharField(source="approved_by.name", read_only=True, allow_null=True)

    class Meta:
        model = PendingItem
        fields = [
            "pending_item_id", "item_name", "category", "category_name", "room", "room_name",
            "unit", "quantity", "min_quantity", "description", "status",
            "requested_by", "requested_by_name", "requested_at",
            "approved_by", "approved_by_name", "approved_at", "rejection_reason",
        ]
        # ``status`` is read-only: it only moves through the audited
        # approve/reject services. Left writable, the requester could PATCH
        # their own row to "approved" and drop it out of the approval queue.
        read_only_fields = [
            "pending_item_id", "requested_at", "status",
            "approved_by", "approved_by_name", "approved_at",
        ]
