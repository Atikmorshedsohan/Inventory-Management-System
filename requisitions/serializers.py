from rest_framework import serializers

from audit.services import record as audit_record

from .models import Requisition, RequisitionItem


class RequisitionItemSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source="item.item_name", read_only=True)

    class Meta:
        model = RequisitionItem
        # 'requisition' is set by the parent serializer's create()
        fields = ["req_item_id", "item", "item_name", "quantity"]
        read_only_fields = ["req_item_id"]


class RequisitionSerializer(serializers.ModelSerializer):
    items = RequisitionItemSerializer(many=True)
    user_name = serializers.CharField(source="user.name", read_only=True)

    class Meta:
        model = Requisition
        fields = [
            "req_id", "user", "user_name", "status", "created_at", "purpose",
            "department", "phone_number", "return_duration_days",
            "expected_return_at", "returned_at", "items",
        ]
        read_only_fields = [
            "req_id", "created_at", "user", "expected_return_at", "returned_at",
        ]

    def create(self, validated_data):
        items_data = validated_data.pop("items", [])
        requisition = Requisition.objects.create(**validated_data)

        for item_data in items_data:
            item, qty = item_data["item"], item_data["quantity"]
            if item.quantity < qty:
                raise serializers.ValidationError(
                    {"items": [f"Insufficient stock for {item.item_name}. Available: {item.quantity}"]}
                )
            RequisitionItem.objects.create(requisition=requisition, item=item, quantity=qty)

        try:
            audit_record(requisition.user, f"Created requisition #{requisition.req_id}")
        except Exception:
            pass  # audit should not block the core flow

        return requisition
