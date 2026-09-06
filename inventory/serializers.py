from rest_framework import serializers
from . import models


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.User
        fields = ['user_id', 'name', 'email', 'phone_number', 'department', 'role', 'created_at']
        read_only_fields = ['user_id', 'created_at', 'role']


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = models.User
        fields = ['name', 'email', 'password', 'password_confirm', 'role']

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({"password": "Passwords do not match"})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        user = models.User.objects.create_user(
            email=validated_data['email'],
            name=validated_data['name'],
            password=validated_data['password'],
            role=validated_data.get('role', 'viewer')
        )
        return user


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Category
        fields = ['category_id', 'category_name', 'description']
        read_only_fields = ['category_id']


class ItemSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source='item_id', read_only=True)
    category = CategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        source='category', queryset=models.Category.objects.all(), write_only=True, required=False, allow_null=True
    )
    room = serializers.SerializerMethodField(read_only=True)
    room_id = serializers.PrimaryKeyRelatedField(
        source='room', queryset=models.Room.objects.all(), write_only=True, required=False, allow_null=True
    )

    def get_room(self, obj):
        if obj.room:
            return {
                'room_id': obj.room.room_id,
                'room_name': obj.room.room_name,
                'room_type': obj.room.room_type,
                'location': obj.room.location,
            }
        return None

    class Meta:
        model = models.Item
        fields = ['id', 'item_id', 'item_name', 'category', 'category_id', 'room', 'room_id', 'unit', 'quantity', 'min_quantity', 'description', 'updated_at']
        read_only_fields = ['id', 'item_id', 'updated_at']


class StockTransactionSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source='item.item_name', read_only=True)
    user_name = serializers.CharField(source='user.name', read_only=True, default='System')
    room = serializers.PrimaryKeyRelatedField(
        queryset=models.Room.objects.all(), write_only=True, required=False, allow_null=True
    )

    class Meta:
        model = models.StockTransaction
        fields = ['transaction_id', 'item', 'item_name', 'type', 'quantity', 'room', 'user', 'user_name', 'timestamp', 'notes']
        read_only_fields = ['transaction_id', 'timestamp', 'item_name', 'user_name']


class RoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Room
        fields = ['room_id', 'room_name', 'room_type', 'room_key', 'location']
        read_only_fields = ['room_id']


class RequisitionItemSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source='item.item_name', read_only=True)

    class Meta:
        model = models.RequisitionItem
        # Exclude 'requisition' from writable fields; it's set by parent create()
        fields = ['req_item_id', 'item', 'item_name', 'quantity']
        read_only_fields = ['req_item_id']


class RequisitionSerializer(serializers.ModelSerializer):
    items = RequisitionItemSerializer(many=True)
    user_name = serializers.CharField(source='user.name', read_only=True)

    class Meta:
        model = models.Requisition
        fields = [
            'req_id',
            'user',
            'user_name',
            'status',
            'created_at',
            'purpose',
            'department',
            'phone_number',
            'return_duration_days',
            'expected_return_at',
            'returned_at',
            'items'
        ]
        read_only_fields = ['req_id', 'created_at', 'user', 'expected_return_at', 'returned_at']

    def create(self, validated_data):
        items_data = validated_data.pop('items', [])

        # Create requisition (user will be provided via serializer.save(user=...))
        requisition = models.Requisition.objects.create(**validated_data)

        # Validate stock and create items
        for item_data in items_data:
            item = item_data['item']
            qty = item_data['quantity']
            if item.quantity < qty:
                raise serializers.ValidationError({
                    'items': [f"Insufficient stock for {item.item_name}. Available: {item.quantity}"]
                })
            models.RequisitionItem.objects.create(
                requisition=requisition,
                item=item,
                quantity=qty
            )

        # Audit log
        try:
            models.AuditLog.objects.create(
                user=requisition.user,
                action=f"Created requisition #{requisition.req_id}"
            )
        except Exception:
            # Audit should not block core flow
            pass

        return requisition


class AuditLogSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.name', read_only=True, default='System')

    class Meta:
        model = models.AuditLog
        fields = ['log_id', 'user', 'user_name', 'action', 'timestamp']
        read_only_fields = ['log_id', 'timestamp']


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        if not models.User.objects.filter(email=value).exists():
            raise serializers.ValidationError("No user found with this email address.")
        return value


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField()
    new_password = serializers.CharField(min_length=8, write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        return attrs

class RoomItemHistorySerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source='item.item_name', read_only=True)
    from_room_name = serializers.CharField(source='from_room.room_name', read_only=True)
    to_room_name = serializers.CharField(source='to_room.room_name', read_only=True)
    user_name = serializers.CharField(source='user.name', read_only=True, allow_null=True)

    class Meta:
        model = models.RoomItemHistory
        fields = ['history_id', 'item', 'item_name', 'from_room', 'from_room_name', 'to_room', 'to_room_name', 'user', 'user_name', 'moved_at', 'remarks']
        read_only_fields = ['history_id', 'moved_at']

# --------------------
# Room Key Management Serializers
# --------------------
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


class PendingStockTransactionSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source='item.item_name', read_only=True)
    room_name = serializers.CharField(source='room.room_name', read_only=True, allow_null=True)
    requested_by_name = serializers.CharField(source='requested_by.name', read_only=True, allow_null=True)
    approved_by_name = serializers.CharField(source='approved_by.name', read_only=True, allow_null=True)

    class Meta:
        model = models.PendingStockTransaction
        fields = ['pending_id', 'item', 'item_name', 'room', 'room_name', 'type', 'quantity', 'notes', 'status', 'requested_by', 'requested_by_name', 'requested_at', 'approved_by', 'approved_by_name', 'approved_at', 'rejection_reason']
        read_only_fields = ['pending_id', 'requested_at', 'approved_by', 'approved_by_name', 'approved_at']


class PendingItemSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.category_name', read_only=True, allow_null=True)
    room_name = serializers.CharField(source='room.room_name', read_only=True, allow_null=True)
    requested_by_name = serializers.CharField(source='requested_by.name', read_only=True, allow_null=True)
    approved_by_name = serializers.CharField(source='approved_by.name', read_only=True, allow_null=True)

    class Meta:
        model = models.PendingItem
        fields = ['pending_item_id', 'item_name', 'category', 'category_name', 'room', 'room_name', 'unit', 'quantity', 'min_quantity', 'description', 'status', 'requested_by', 'requested_by_name', 'requested_at', 'approved_by', 'approved_by_name', 'approved_at', 'rejection_reason']
        read_only_fields = ['pending_item_id', 'requested_at', 'approved_by', 'approved_by_name', 'approved_at']


class KeyBorrowSerializer(serializers.ModelSerializer):
    key_number = serializers.CharField(source='key.key_number', read_only=True)
    room_name = serializers.CharField(source='key.room_name', read_only=True)
    borrower_name = serializers.SerializerMethodField()
    approver_name = serializers.SerializerMethodField()
    is_overdue = serializers.SerializerMethodField()

    class Meta:
        model = models.KeyBorrow
        fields = ['borrow_id', 'key', 'key_number', 'room_name', 'borrower', 'borrower_name', 'approver', 'approver_name', 'purpose', 'status', 'requested_at', 'approved_at', 'borrowed_at', 'expected_return_at', 'returned_at', 'rejection_reason', 'notes', 'is_overdue', 'created_at']
        read_only_fields = ['borrow_id', 'requested_at', 'approved_at', 'borrowed_at', 'returned_at', 'created_at']

    def _user_display(self, user):
        if not user:
            return None
        for attr in ('name', 'full_name'):
            val = getattr(user, attr, None)
            if val:
                return val
        if hasattr(user, 'get_full_name'):
            val = user.get_full_name()
            if val:
                return val
        return getattr(user, 'username', str(user))

    def get_borrower_name(self, obj):
        return self._user_display(obj.borrower)

    def get_approver_name(self, obj):
        return self._user_display(obj.approver)

    def get_is_overdue(self, obj):
        return obj.is_overdue
