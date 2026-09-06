from rest_framework import serializers
from .models import Requisition, RequisitionItem


class RequisitionItemSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source='item.item_name', read_only=True)

    class Meta:
        model = RequisitionItem
        fields = ['req_item_id', 'item', 'item_name', 'quantity']
        read_only_fields = ['req_item_id']

    def validate(self, attrs):
        item = attrs.get('item')
        quantity = attrs.get('quantity')
        
        if item and quantity:
            if item.quantity < quantity:
                raise serializers.ValidationError(
                    f"Insufficient stock for {item.item_name}. Available: {item.quantity}"
                )
        return attrs


class RequisitionSerializer(serializers.ModelSerializer):
    items = RequisitionItemSerializer(many=True)
    user_name = serializers.CharField(source='user.name', read_only=True)

    class Meta:
        model = Requisition
        fields = ['req_id', 'user', 'user_name', 'status', 'created_at', 'purpose', 'items']
        read_only_fields = ['req_id', 'created_at']

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        requisition = Requisition.objects.create(**validated_data)
        
        for item_data in items_data:
            RequisitionItem.objects.create(
                requisition=requisition,
                **item_data
            )
        
        # Log the action
        from audit.models import AuditLog
        AuditLog.objects.create(
            user=requisition.user,
            action=f"Created requisition #{requisition.req_id} for {requisition.purpose}"
        )
        
        return requisition

    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
        
        # Update requisition fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Update items if provided
        if items_data is not None:
            instance.items.all().delete()
            for item_data in items_data:
                RequisitionItem.objects.create(
                    requisition=instance,
                    **item_data
                )
        
        # Log the action
        from audit.models import AuditLog
        AuditLog.objects.create(
            user=self.context['request'].user,
            action=f"Updated requisition #{instance.req_id} - Status: {instance.status}"
        )
        
        return instance
