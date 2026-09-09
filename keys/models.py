from django.conf import settings
from django.db import models
from django.utils import timezone

from .utils import user_display


class RoomKey(models.Model):
    STATUS_CHOICES = (
        ("available", "Available"),
        ("reserved", "Reserved"),
        ("in_use", "In Use"),
        ("lost", "Lost"),
        ("maintenance", "Maintenance"),
    )

    key_id = models.AutoField(primary_key=True)
    room_name = models.CharField(max_length=100)
    key_number = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="available")
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_keys",
        db_column="assigned_to_id",
    )
    assigned_date = models.DateTimeField(blank=True, null=True)
    last_location = models.CharField(max_length=200, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "room_keys"
        ordering = ["room_name", "key_number"]

    def __str__(self):
        return f"{self.key_number} - {self.room_name}"


class KeyAuditLog(models.Model):
    ACTION_CHOICES = (
        ("assigned", "Assigned"),
        ("returned", "Returned"),
        ("lost", "Lost"),
        ("found", "Found"),
        ("maintenance", "Sent to Maintenance"),
        ("restored", "Restored"),
        ("created", "Created"),
        ("borrowed", "Borrowed"),
        ("approved", "Borrow Approved"),
        ("picked_up", "Handover Confirmed"),
        ("rejected", "Borrow Rejected"),
        ("returned_borrow", "Returned from Borrow"),
    )

    log_id = models.AutoField(primary_key=True)
    key = models.ForeignKey(
        RoomKey, on_delete=models.CASCADE, related_name="audit_logs", db_column="key_id"
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="key_audit_logs",
        db_column="performed_by_id",
    )
    notes = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "key_audit_log"
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.key.key_number} - {self.action} by {self.performed_by if self.performed_by else 'Unknown'}"


class KeyBorrow(models.Model):
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("borrowed", "Borrowed"),
        ("returned", "Returned"),
        ("overdue", "Overdue"),
    )

    borrow_id = models.AutoField(primary_key=True)
    key = models.ForeignKey(
        RoomKey, on_delete=models.CASCADE, related_name="borrow_history", db_column="key_id"
    )
    borrower = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="borrowed_keys",
        db_column="borrower_id",
    )
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_key_borrows",
        db_column="approver_id",
    )
    purpose = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    requested_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(blank=True, null=True)
    # Set only when the physical handover is confirmed (see services.confirm_pickup).
    borrowed_at = models.DateTimeField(blank=True, null=True)
    handed_over_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="key_handovers",
        db_column="handed_over_by_id",
    )
    handover_notes = models.TextField(blank=True, null=True)
    expected_return_at = models.DateTimeField()
    returned_at = models.DateTimeField(blank=True, null=True)
    rejection_reason = models.TextField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "key_borrows"
        ordering = ["-requested_at"]

    def __str__(self):
        return f"{self.key.key_number} borrowed by {user_display(self.borrower)} - {self.status}"

    @property
    def is_overdue(self):
        if self.status == "borrowed" and self.expected_return_at:
            return timezone.now() > self.expected_return_at
        return False

    @property
    def awaiting_pickup(self):
        """Approved but the borrower has not physically collected the key yet."""
        return self.status == "approved"
