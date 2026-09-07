"""Single entry point for writing to the audit trail.

Every app records activity through :func:`record` instead of importing the
``AuditLog`` model directly, so the write policy lives in one place.
"""

from .models import AuditLog


def _normalize(user):
    if user and getattr(user, "is_authenticated", False):
        return user
    return None


def record(user, action):
    """Append one line to the audit trail and return the created row."""
    return AuditLog.objects.create(user=_normalize(user), action=action)
