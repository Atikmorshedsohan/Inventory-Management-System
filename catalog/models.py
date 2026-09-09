from django.conf import settings
from django.db import models

STATUS_CHOICES = (
    ("pending", "Pending"),
    ("approved", "Approved"),
    ("rejected", "Rejected"),
)


class Category(models.Model):
    category_id = models.AutoField(primary_key=True)
    category_name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "categories"
        verbose_name_plural = "Categories"
        ordering = ["category_name"]

    def __str__(self):
        return self.category_name


class Room(models.Model):
    room_id = models.AutoField(primary_key=True)
    room_name = models.CharField(max_length=100)
    room_type = models.CharField(max_length=50)  # lab, classroom, office
    room_key = models.BooleanField(default=False)
    location = models.CharField(max_length=100, blank=True, default="")

    class Meta:
        db_table = "rooms"
        ordering = ["room_name"]

    def __str__(self):
        return f"{self.room_name} ({self.room_type})"


class Item(models.Model):
    item_id = models.AutoField(primary_key=True)
    item_name = models.CharField(max_length=150)
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, related_name="items", db_column="category_id"
    )
    room = models.ForeignKey(
        "Room", on_delete=models.SET_NULL, null=True, related_name="items", db_column="room_id"
    )
    unit = models.CharField(max_length=50)
    quantity = models.IntegerField(default=0)
    # Stock the item started with that did not arrive through a StockTransaction
    # (initial count on creation, merged-in pending items). The reconciliation
    # report treats the ledger balance as ``opening_quantity + IN - OUT + ADJUST``.
    opening_quantity = models.IntegerField(default=0)
    min_quantity = models.IntegerField(default=10)
    description = models.TextField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "items"
        # Newest additions first: item_id is auto-incrementing, so descending
        # id is insertion order (most recently added item on top), not A-Z.
        ordering = ["-item_id"]

    def save(self, *args, **kwargs):
        # Django < 5.0 does not fold ``auto_now`` fields into ``update_fields``,
        # so a partial save like ``save(update_fields=["quantity"])`` (used all
        # over the stock / transfer / issue services) would leave ``updated_at``
        # stale and the room-wise "sort by last update" would not move. Keep it
        # fresh on every partial save.
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            kwargs["update_fields"] = {*update_fields, "updated_at"}
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.item_name} ({self.unit})"

    @property
    def is_low_stock(self):
        return self.quantity <= self.min_quantity


class PendingItem(models.Model):
    """Item creation awaiting admin/manager approval."""

    pending_item_id = models.AutoField(primary_key=True)
    item_name = models.CharField(max_length=150)
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="pending_items"
    )
    room = models.ForeignKey(Room, on_delete=models.SET_NULL, null=True, blank=True)
    unit = models.CharField(max_length=50, blank=True, null=True)
    quantity = models.IntegerField(default=0)
    min_quantity = models.IntegerField(default=0)
    description = models.TextField(blank=True, null=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="pending_items_created",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    requested_at = models.DateTimeField(auto_now_add=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_items",
    )
    approved_at = models.DateTimeField(blank=True, null=True)
    rejection_reason = models.TextField(blank=True, null=True)
    created_item = models.ForeignKey(
        Item, on_delete=models.SET_NULL, null=True, blank=True, related_name="from_pending"
    )

    class Meta:
        db_table = "pending_items"
        ordering = ["-requested_at"]

    def __str__(self):
        return f"Pending Item: {self.item_name}"
