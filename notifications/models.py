from django.conf import settings
from django.db import models

LEVEL_CHOICES = (
    ("info", "Info"),
    ("success", "Success"),
    ("warning", "Warning"),
    ("danger", "Danger"),
)

CATEGORY_CHOICES = (
    ("reorder", "Reorder alert"),
    ("transfer", "Item transfer"),
    ("import", "Bulk import"),
    ("general", "General"),
)


class Notification(models.Model):
    """A single in-app message for one recipient.

    Reorder alerts are de-duplicated on ``(recipient, item, category="reorder",
    is_read=False)`` so an item never stacks up more than one open alert per
    person; when the item climbs back above its minimum the open alerts are
    marked read automatically (see :func:`notifications.services.resolve_reorder`).
    """

    notification_id = models.AutoField(primary_key=True)
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        db_column="recipient_id",
    )
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="general")
    level = models.CharField(max_length=10, choices=LEVEL_CHOICES, default="info")
    title = models.CharField(max_length=150)
    message = models.TextField(blank=True, default="")
    link = models.CharField(max_length=200, blank=True, default="")
    item = models.ForeignKey(
        "catalog.Item",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
        db_column="item_id",
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "notifications"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "is_read"]),
            models.Index(fields=["item", "category", "is_read"]),
        ]

    def __str__(self):
        state = "read" if self.is_read else "unread"
        return f"[{state}] {self.recipient_id}: {self.title}"
