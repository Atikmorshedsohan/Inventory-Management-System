from rest_framework import serializers
from .models import Category, Item, StockTransaction


class CategorySerializer(serializers.ModelSerializer):
    items_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['category_id', 'category_name', 'description', 'items_count']
        read_only_fields = ['category_id']

    def get_items_count(self, obj):
        return obj.items.count()


class ItemSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.category_name', read_only=True)
    is_low_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = Item
        fields = ['item_id', 'item_name', 'category', 'category_name', 
                  'unit', 'quantity', 'min_quantity', 'description', 'is_low_stock']
        read_only_fields = ['item_id', 'quantity']  # quantity updated via transactions


class StockTransactionSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source='item.item_name', read_only=True)
    user_name = serializers.CharField(source='user.name', read_only=True)

    class Meta:
        model = StockTransaction
        fields = ['transaction_id', 'item', 'item_name', 'type', 'quantity',
                  'user', 'user_name', 'timestamp', 'notes']
        read_only_fields = ['transaction_id', 'timestamp']

    def create(self, validated_data):
        transaction = super().create(validated_data)
        # Update item quantity based on transaction type
        item = transaction.item
        if transaction.type == 'IN':
            item.quantity += transaction.quantity
        elif transaction.type == 'OUT':
            if item.quantity >= transaction.quantity:
                item.quantity -= transaction.quantity
            else:
                raise serializers.ValidationError("Insufficient stock for OUT transaction")
        elif transaction.type == 'ADJUST':
            item.quantity = transaction.quantity
        item.save()
        
        # Log the action
        from audit.models import AuditLog
        AuditLog.objects.create(
            user=transaction.user,
            action=f"{transaction.type} transaction: {transaction.quantity} {item.unit} of {item.item_name}"
        )
        
        return transaction
