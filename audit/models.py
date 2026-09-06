from django.db import models


class AuditLog(models.Model):
    """Audit Log Model - tracks all user actions"""
    log_id = models.AutoField(primary_key=True)
    user = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, related_name='audit_logs', db_column='user_id')
    action = models.CharField(max_length=200)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.name if self.user else 'Unknown'} - {self.action} at {self.timestamp}"

    class Meta:
        db_table = 'audit_log'
        ordering = ['-timestamp']
