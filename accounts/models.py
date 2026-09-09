from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone

from .managers import UserManager

ELEVATED_ROLES = ("admin", "manager", "staff")


class User(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = (
        ("admin", "Admin"),
        ("manager", "Manager"),
        ("viewer", "Viewer"),
        ("staff", "Staff"),  # legacy compatibility
    )

    user_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    email = models.EmailField(max_length=100, unique=True)
    phone_number = models.CharField(max_length=20, blank=True, default="")
    department = models.CharField(max_length=100, blank=True, default="")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="staff")
    created_at = models.DateTimeField(auto_now_add=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name"]

    class Meta:
        db_table = "users"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.email}) - {self.role}"

    def save(self, *args, **kwargs):
        # Staff-level roles get Django admin access; superuser stays independent.
        self.is_staff = self.role in ELEVATED_ROLES
        super().save(*args, **kwargs)


class LoginEvent(models.Model):
    """When and from where someone signed in - including failed attempts.

    ``user`` is null for a failed attempt against an address that does not
    exist, which is exactly the case worth spotting; ``email`` always records
    what was actually typed.
    """

    EVENT_CHOICES = (
        ("login", "Signed in"),
        ("failed", "Failed sign-in"),
        ("logout", "Signed out"),
    )

    event_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="login_events",
        db_column="user_id",
    )
    email = models.CharField(max_length=254, blank=True, default="")
    event = models.CharField(max_length=20, choices=EVENT_CHOICES, default="login")
    successful = models.BooleanField(default=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    client = models.CharField(max_length=120, blank=True, default="")
    user_agent = models.TextField(blank=True, default="")
    reason = models.CharField(max_length=200, blank=True, default="")
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "login_events"
        # event_id breaks ties between rows written in the same tick.
        ordering = ["-timestamp", "-event_id"]
        indexes = [
            models.Index(fields=["user", "-timestamp"]),
            models.Index(fields=["successful", "-timestamp"]),
        ]

    def __str__(self):
        who = self.user.email if self.user else (self.email or "unknown")
        return f"{self.get_event_display()}: {who} from {self.ip_address or 'unknown IP'}"


class PasswordResetToken(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reset_tokens"
    )
    token = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)

    class Meta:
        db_table = "password_reset_tokens"
        ordering = ["-created_at"]

    def is_valid(self):
        return not self.used and timezone.now() < self.expires_at
