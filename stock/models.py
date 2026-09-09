from django.conf import settings
from django.db import models

TRANSACTION_TYPES = (
    ("IN", "Stock In"),
    ("OUT", "Stock Out"),
    ("ADJUST", "Adjustment"),
)

PENDING_STATUS_CHOICES = (
    ("pending", "Pending"),
    ("approved", "Approved"),
    ("rejected", "Rejected"),
)


class StockTransaction(models.Model):
    transaction_id = models.AutoField(primary_key=True)
    item = models.ForeignKey(
        "catalog.Item", on_delete=models.CASCADE, related_name="transactions", db_column="item_id"
    )
    type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    quantity = models.IntegerField()
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, db_column="user_id"
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "stock_transactions"
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.item.item_name} - {self.type} - {self.quantity}"


TRANSFER_TYPES = (
    ("full", "Full move"),
    ("partial", "Partial move"),
)


class RoomItemHistory(models.Model):
    history_id = models.AutoField(primary_key=True)
    item = models.ForeignKey(
        "catalog.Item", on_delete=models.CASCADE, related_name="room_history", db_column="item_id"
    )
    from_room = models.ForeignKey(
        "catalog.Room",
        on_delete=models.SET_NULL,
        null=True,
        related_name="history_from",
        db_column="from_room_id",
    )
    to_room = models.ForeignKey(
        "catalog.Room",
        on_delete=models.SET_NULL,
        null=True,
        related_name="history_to",
        db_column="to_room_id",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="room_moves",
        db_column="user_id",
    )
    moved_at = models.DateTimeField(auto_now_add=True)
    remarks = models.TextField(blank=True, null=True)

    # --- Move Item workflow: quantity + before/after snapshots ---------------
    transfer_type = models.CharField(max_length=10, choices=TRANSFER_TYPES, default="full")
    quantity = models.IntegerField(null=True, blank=True)
    # For a partial move the destination stock lands on a sibling item row.
    dest_item = models.ForeignKey(
        "catalog.Item",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="incoming_transfers",
        db_column="dest_item_id",
    )
    source_qty_before = models.IntegerField(null=True, blank=True)
    source_qty_after = models.IntegerField(null=True, blank=True)
    dest_qty_before = models.IntegerField(null=True, blank=True)
    dest_qty_after = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = "room_item_history"
        ordering = ["-moved_at"]

    def __str__(self):
        return f"{self.item.item_name}: {self.from_room} → {self.to_room}"


class StockImportBatch(models.Model):
    """One bulk stock-in upload: a CSV of items to stock in at once."""

    batch_id = models.AutoField(primary_key=True)
    filename = models.CharField(max_length=255, blank=True, default="")
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="stock_import_batches",
        db_column="uploaded_by_id",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    total_rows = models.IntegerField(default=0)
    success_count = models.IntegerField(default=0)
    error_count = models.IntegerField(default=0)
    # Per-row outcome: [{"row": 2, "status": "ok"|"error", "message": str, ...}]
    report = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = "stock_import_batches"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Import #{self.batch_id} ({self.success_count}/{self.total_rows} ok)"


class PendingStockTransaction(models.Model):
    """Stock transaction awaiting admin approval."""

    pending_id = models.AutoField(primary_key=True)
    item = models.ForeignKey(
        "catalog.Item", on_delete=models.CASCADE, related_name="pending_transactions"
    )
    room = models.ForeignKey("catalog.Room", on_delete=models.SET_NULL, null=True, blank=True)
    type = models.CharField(max_length=10, choices=(("IN", "Stock In"), ("OUT", "Stock Out")))
    quantity = models.IntegerField()
    notes = models.TextField(blank=True, null=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="pending_stock_requests",
    )
    status = models.CharField(max_length=20, choices=PENDING_STATUS_CHOICES, default="pending")
    requested_at = models.DateTimeField(auto_now_add=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_stock_requests",
    )
    approved_at = models.DateTimeField(blank=True, null=True)
    rejection_reason = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "pending_stock_transactions"
        ordering = ["-requested_at"]

    def __str__(self):
        return f"Pending Stock {self.type}: {self.item.item_name} x{self.quantity}"
