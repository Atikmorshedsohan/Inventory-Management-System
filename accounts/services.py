"""Business logic for account/auth flows.

Views stay thin: they validate input with a serializer, call one of these
functions, and shape the HTTP response.
"""

import secrets
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from audit.services import record as audit_record

from .models import PasswordResetToken, User

RESET_TOKEN_TTL = timedelta(hours=1)

_RESET_EMAIL_BODY = """Hello {name},

You have requested to reset your password for the CSE Inventory Management System.

Click the link below to reset your password:
{url}

This link will expire in 1 hour.

If you did not request this password reset, please ignore this email and your password will remain unchanged.

For security reasons, never share this link with anyone.

Best regards,
CSE Inventory System
"""


class PasswordResetError(Exception):
    """Raised when a reset token cannot be used."""


def issue_password_reset(*, email, reset_url_builder):
    """Create a fresh reset token for ``email`` and email the link.

    ``reset_url_builder`` is ``callable(token) -> str`` so this function does
    not need to know about HTTP requests. Email failures are swallowed (the
    caller always reports success to avoid leaking which emails exist).
    """
    user = User.objects.get(email=email)

    PasswordResetToken.objects.filter(user=user, used=False).update(used=True)
    token = PasswordResetToken.objects.create(
        user=user,
        token=secrets.token_urlsafe(32),
        expires_at=timezone.now() + RESET_TOKEN_TTL,
    )

    try:
        send_mail(
            "Password Reset Request - CSE Inventory System",
            _RESET_EMAIL_BODY.format(name=user.name, url=reset_url_builder(token.token)),
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False,
        )
    except Exception as exc:  # noqa: BLE001 - logged, not surfaced
        print(f"Email sending failed: {exc}")

    return token


def confirm_password_reset(*, token, new_password):
    """Validate ``token`` and set the user's new password."""
    try:
        reset_token = PasswordResetToken.objects.get(token=token)
    except PasswordResetToken.DoesNotExist:
        raise PasswordResetError("Invalid token.")

    if not reset_token.is_valid():
        raise PasswordResetError("Token is invalid or has expired.")

    user = reset_token.user
    user.set_password(new_password)
    user.save()

    reset_token.used = True
    reset_token.save()

    audit_record(user, f"Password reset completed for {user.email}")
    return user
