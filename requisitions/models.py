from django.conf import settings
from django.db import models


class Requisition(models.Model):
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
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

    class Meta:
        db_table = "requisition_items"

    def __str__(self):
        return f"{self.requisition.req_id} - {self.item.item_name} x {self.quantity}"
