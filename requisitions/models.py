from django.conf import settings
from django.db import models


class Requisition(models.Model):
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("partially_issued", "Partially Issued"),
        ("issued", "Issued"),
        ("returned", "Returned"),
    )

    req_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="requisitions",
        db_column="user_id",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    purpose = models.TextField()
    department = models.CharField(max_length=100, blank=True, default="")
    phone_number = models.CharField(max_length=30, blank=True, default="")
    return_duration_days = models.IntegerField(default=7)
    expected_return_at = models.DateTimeField(blank=True, null=True)
    returned_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "requisitions"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Requisition #{self.req_id} - {self.user} - {self.status}"


class RequisitionItem(models.Model):
    req_item_id = models.AutoField(primary_key=True)
    requisition = models.ForeignKey(
        Requisition, on_delete=models.CASCADE, related_name="items", db_column="req_id"
    )
    item = models.ForeignKey(
        "catalog.Item",
        on_delete=models.CASCADE,
        related_name="requisition_items",
        db_column="item_id",
    )
    quantity = models.IntegerField()
    # Running total actually handed out - supports issuing in several partial rounds.
    issued_quantity = models.IntegerField(default=0)

    class Meta:
        db_table = "requisition_items"

    def __str__(self):
        return f"{self.requisition.req_id} - {self.item.item_name} x {self.quantity}"

    @property
    def outstanding_quantity(self):
        return max(self.quantity - self.issued_quantity, 0)


class RequisitionEvent(models.Model):
    """One entry in a requisition's history timeline.

    Covers both automatic state transitions (created -> approved -> issued ...)
    and free-text comments/notes left by the approver or the requester.
    """

    EVENT_TYPES = (
        ("created", "Created"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("partially_issued", "Partially issued"),
        ("issued", "Issued"),
        ("returned", "Returned"),
        ("comment", "Comment"),
    )

    event_id = models.AutoField(primary_key=True)
    requisition = models.ForeignKey(
        Requisition, on_delete=models.CASCADE, related_name="events", db_column="req_id"
    )
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    from_status = models.CharField(max_length=20, blank=True, default="")
    to_status = models.CharField(max_length=20, blank=True, default="")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="requisition_events",
        db_column="actor_id",
    )
    note = models.TextField(blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "requisition_events"
        ordering = ["created_at", "event_id"]

    def __str__(self):
        return f"Req #{self.requisition_id}: {self.event_type} @ {self.created_at:%Y-%m-%d %H:%M}"
