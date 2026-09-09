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


class RoomItemHistory(models.Model):
    """Audit trail of a stocked item's room changing (written by Stock IN/OUT)."""

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

    class Meta:
        db_table = "room_item_history"
        ordering = ["-moved_at"]

    def __str__(self):
        return f"{self.item.item_name}: {self.from_room} → {self.to_room}"


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
