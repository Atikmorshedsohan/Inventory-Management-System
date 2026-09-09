from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    log_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="audit_logs",
        db_column="user_id",
    )
    action = models.CharField(max_length=200)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "audit_log"
        # log_id breaks ties: several entries can share a timestamp when they
        # are written in the same tick, and "-timestamp" alone is then unstable.
        ordering = ["-timestamp", "-log_id"]

    def __str__(self):
        return f"{self.user if self.user else 'Unknown'} - {self.action} at {self.timestamp}"
