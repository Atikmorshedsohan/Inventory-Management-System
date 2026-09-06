from rest_framework import serializers
from .models import Order, OrderItem
from products.models import Product


class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'product_name', 'quantity', 'unit_price', 'subtotal']
        read_only_fields = ['id', 'subtotal']

    def validate(self, attrs):
        product = attrs.get('product')
        quantity = attrs.get('quantity')
        
        if product and quantity:
            if product.quantity_in_stock < quantity:
                raise serializers.ValidationError(
                    f"Insufficient stock for {product.name}. Available: {product.quantity_in_stock}"
                )
        return attrs


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)

    class Meta:
        model = Order
        fields = ['id', 'order_number', 'customer', 'customer_name', 'status',
                  'total_amount', 'notes', 'items', 'created_by', 'created_by_name',
                  'created_at', 'updated_at']
        read_only_fields = ['id', 'total_amount', 'created_at', 'updated_at']

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        order = Order.objects.create(**validated_data)
        
        for item_data in items_data:
            product = item_data['product']
            quantity = item_data['quantity']
            
            # Create order item
            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=quantity,
                unit_price=product.unit_price
            )
            
            # Update product stock
            product.quantity_in_stock -= quantity
            product.save()
        
        order.calculate_total()
        return order

    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
        
        # Update order fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Update items if provided
        if items_data is not None:
            # Clear existing items and restore stock
            for item in instance.items.all():
                item.product.quantity_in_stock += item.quantity
                item.product.save()
            instance.items.all().delete()
            
            # Create new items
            for item_data in items_data:
                product = item_data['product']
                quantity = item_data['quantity']
                
                OrderItem.objects.create(
                    order=instance,
                    product=product,
                    quantity=quantity,
                    unit_price=product.unit_price
                )
                
                product.quantity_in_stock -= quantity
                product.save()
            
            instance.calculate_total()
        
        return instance
