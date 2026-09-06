from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.conf import settings


# --------------------
# User
# --------------------
class UserManager(BaseUserManager):
    def create_user(self, email, name, password=None, **extra_fields):
        if not email:
            raise ValueError('Users must have an email address')
        email = self.normalize_email(email)
        user = self.model(email=email, name=name, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, name, password=None, **extra_fields):
        extra_fields.setdefault('role', 'admin')
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, name, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('manager', 'Manager'),
        ('viewer', 'Viewer'),
        ('staff', 'Staff'),  # legacy compatibility
    )

    user_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    email = models.EmailField(max_length=100, unique=True)
    phone_number = models.CharField(max_length=20, blank=True, default='')
    department = models.CharField(max_length=100, blank=True, default='')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='staff')
    created_at = models.DateTimeField(auto_now_add=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['name']

    def __str__(self):
        return f"{self.name} ({self.email}) - {self.role}"

    def save(self, *args, **kwargs):
        # Ensure Django admin access for both admin and staff roles
        # Set is_staff True when role is 'admin' or 'staff'.
        # Superuser status remains controlled separately.
        if self.role in ('admin', 'manager', 'staff'):
            self.is_staff = True
        else:
            self.is_staff = False
        super().save(*args, **kwargs)

    class Meta:
        db_table = 'users'
        ordering = ['-created_at']


# --------------------
# Products (Categories, Items, Stock)
# --------------------
class Category(models.Model):
    category_id = models.AutoField(primary_key=True)
    category_name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.category_name

    class Meta:
        db_table = 'categories'
        verbose_name_plural = 'Categories'
        ordering = ['category_name']


class Room(models.Model):
    room_id = models.AutoField(primary_key=True)
    room_name = models.CharField(max_length=100)
    room_type = models.CharField(max_length=50)  # lab, classroom, office
    room_key = models.BooleanField(default=False)
    location = models.CharField(max_length=100, blank=True, default='')
    def __str__(self):
        return f"{self.room_name} ({self.room_type})"

    class Meta:
        db_table = 'rooms'
        ordering = ['room_name']


class Item(models.Model):
    item_id = models.AutoField(primary_key=True)
    item_name = models.CharField(max_length=150)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='items', db_column='category_id')
    room = models.ForeignKey('Room', on_delete=models.SET_NULL, null=True, related_name='items', db_column='room_id')
    unit = models.CharField(max_length=50)
    quantity = models.IntegerField(default=0)
    min_quantity = models.IntegerField(default=10)
    description = models.TextField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.item_name} ({self.unit})"

    @property
    def is_low_stock(self):
        return self.quantity <= self.min_quantity

    class Meta:
        db_table = 'items'
        ordering = ['item_name']


class StockTransaction(models.Model):
    TRANSACTION_TYPES = (
        ('IN', 'Stock In'),
        ('OUT', 'Stock Out'),
        ('ADJUST', 'Adjustment'),
    )

    transaction_id = models.AutoField(primary_key=True)
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='transactions', db_column='item_id')
    type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    quantity = models.IntegerField()
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, db_column='user_id')
    timestamp = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.item.item_name} - {self.type} - {self.quantity}"

    class Meta:
        db_table = 'stock_transactions'
        ordering = ['-timestamp']


# --------------------
# Room Item Movement History
# --------------------
class RoomItemHistory(models.Model):
    history_id = models.AutoField(primary_key=True)
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='room_history', db_column='item_id')
    from_room = models.ForeignKey(Room, on_delete=models.SET_NULL, null=True, related_name='history_from', db_column='from_room_id')
    to_room = models.ForeignKey(Room, on_delete=models.SET_NULL, null=True, related_name='history_to', db_column='to_room_id')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='room_moves', db_column='user_id')
    moved_at = models.DateTimeField(auto_now_add=True)
    remarks = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.item.item_name}: {self.from_room} → {self.to_room}"

    class Meta:
        db_table = 'room_item_history'
        ordering = ['-moved_at']


# --------------------
# Requisitions
# --------------------
class Requisition(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('issued', 'Issued'),
        ('returned', 'Returned'),
    )

    req_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='requisitions', db_column='user_id')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    purpose = models.TextField()
    department = models.CharField(max_length=100, blank=True, default='')
    phone_number = models.CharField(max_length=30, blank=True, default='')
    return_duration_days = models.IntegerField(default=7)
    expected_return_at = models.DateTimeField(blank=True, null=True)
    returned_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"Requisition #{self.req_id} - {self.user} - {self.status}"

    class Meta:
        db_table = 'requisitions'
        ordering = ['-created_at']


class RequisitionItem(models.Model):
    req_item_id = models.AutoField(primary_key=True)
    requisition = models.ForeignKey(Requisition, on_delete=models.CASCADE, related_name='items', db_column='req_id')
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='requisition_items', db_column='item_id')
    quantity = models.IntegerField()

    def __str__(self):
        return f"{self.requisition.req_id} - {self.item.item_name} x {self.quantity}"

    class Meta:
        db_table = 'requisition_items'


# --------------------
# Audit
# --------------------
class AuditLog(models.Model):
    log_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='audit_logs', db_column='user_id')
    action = models.CharField(max_length=200)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user if self.user else 'Unknown'} - {self.action} at {self.timestamp}"

    class Meta:
        db_table = 'audit_log'
        ordering = ['-timestamp']


class PasswordResetToken(models.Model):
    """Password Reset Token Model"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reset_tokens')
    token = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)

    def is_valid(self):
        from django.utils import timezone
        return not self.used and timezone.now() < self.expires_at

    class Meta:
        db_table = 'password_reset_tokens'
        ordering = ['-created_at']


# --------------------
# Room Key Management
# --------------------
class RoomKey(models.Model):
    STATUS_CHOICES = (
        ('available', 'Available'),
        ('in_use', 'In Use'),
        ('lost', 'Lost'),
        ('maintenance', 'Maintenance'),
    )

    key_id = models.AutoField(primary_key=True)
    room_name = models.CharField(max_length=100)
    key_number = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_keys', db_column='assigned_to_id')
    assigned_date = models.DateTimeField(blank=True, null=True)
    last_location = models.CharField(max_length=200, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.key_number} - {self.room_name}"

    class Meta:
        db_table = 'room_keys'
        ordering = ['room_name', 'key_number']


class KeyAuditLog(models.Model):
    ACTION_CHOICES = (
        ('assigned', 'Assigned'),
        ('returned', 'Returned'),
        ('lost', 'Lost'),
        ('found', 'Found'),
        ('maintenance', 'Sent to Maintenance'),
        ('restored', 'Restored'),
        ('created', 'Created'),
        ('borrowed', 'Borrowed'),
        ('returned_borrow', 'Returned from Borrow'),
    )

    log_id = models.AutoField(primary_key=True)
    key = models.ForeignKey(RoomKey, on_delete=models.CASCADE, related_name='audit_logs', db_column='key_id')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    performed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='key_audit_logs', db_column='performed_by_id')
    notes = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.key.key_number} - {self.action} by {self.performed_by if self.performed_by else 'Unknown'}"

    class Meta:
        db_table = 'key_audit_log'
        ordering = ['-timestamp']


class KeyBorrow(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('borrowed', 'Borrowed'),
        ('returned', 'Returned'),
        ('overdue', 'Overdue'),
    )

    borrow_id = models.AutoField(primary_key=True)
    key = models.ForeignKey(RoomKey, on_delete=models.CASCADE, related_name='borrow_history', db_column='key_id')
    borrower = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='borrowed_keys', db_column='borrower_id')
    approver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_key_borrows', db_column='approver_id')
    purpose = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    requested_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(blank=True, null=True)
    borrowed_at = models.DateTimeField(blank=True, null=True)
    expected_return_at = models.DateTimeField()
    returned_at = models.DateTimeField(blank=True, null=True)
    rejection_reason = models.TextField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        borrower_display = getattr(self.borrower, 'name', None) or getattr(self.borrower, 'full_name', None)
        if not borrower_display and hasattr(self.borrower, 'get_full_name'):
            borrower_display = self.borrower.get_full_name()
        borrower_display = borrower_display or getattr(self.borrower, 'username', str(self.borrower))
        return f"{self.key.key_number} borrowed by {borrower_display} - {self.status}"

    @property
    def is_overdue(self):
        from django.utils import timezone
        if self.status == 'borrowed' and self.expected_return_at:
            return timezone.now() > self.expected_return_at
        return False

    class Meta:
        db_table = 'key_borrows'
        ordering = ['-requested_at']


# --------------------
# Stock Transaction & Item Approval (Pending)
# --------------------
class PendingStockTransaction(models.Model):
    """Pending stock transactions awaiting admin approval"""
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )

    pending_id = models.AutoField(primary_key=True)
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='pending_transactions')
    room = models.ForeignKey(Room, on_delete=models.SET_NULL, null=True, blank=True)
    type = models.CharField(max_length=10, choices=(('IN', 'Stock In'), ('OUT', 'Stock Out')))
    quantity = models.IntegerField()
    notes = models.TextField(blank=True, null=True)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='pending_stock_requests')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    requested_at = models.DateTimeField(auto_now_add=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_stock_requests')
    approved_at = models.DateTimeField(blank=True, null=True)
    rejection_reason = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Pending Stock {self.type}: {self.item.item_name} x{self.quantity}"

    class Meta:
        db_table = 'pending_stock_transactions'
        ordering = ['-requested_at']


class PendingItem(models.Model):
    """Pending item creation awaiting admin approval"""
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )

    pending_item_id = models.AutoField(primary_key=True)
    item_name = models.CharField(max_length=150)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='pending_items')
    room = models.ForeignKey(Room, on_delete=models.SET_NULL, null=True, blank=True)
    unit = models.CharField(max_length=50, blank=True, null=True)
    quantity = models.IntegerField(default=0)
    min_quantity = models.IntegerField(default=0)
    description = models.TextField(blank=True, null=True)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='pending_items_created')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    requested_at = models.DateTimeField(auto_now_add=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_items')
    approved_at = models.DateTimeField(blank=True, null=True)
    rejection_reason = models.TextField(blank=True, null=True)
    created_item = models.ForeignKey(Item, on_delete=models.SET_NULL, null=True, blank=True, related_name='from_pending')

    def __str__(self):
        return f"Pending Item: {self.item_name}"

    class Meta:
        db_table = 'pending_items'
        ordering = ['-requested_at']