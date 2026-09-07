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
