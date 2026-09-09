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
from common.exceptions import DomainError

from .models import LoginEvent, PasswordResetToken, User
from .utils import client_ip, describe_client, user_agent

RESET_TOKEN_TTL = timedelta(hours=1)

VALID_ROLES = [key for key, _label in User.ROLE_CHOICES]


def record_login_event(request, *, email="", event="login", successful=True, user=None, reason=""):
    """Write one sign-in / sign-out / failed-attempt record.

    Never raises: an auth flow must not break because we could not log it.
    """
    try:
        raw_agent = user_agent(request)
        return LoginEvent.objects.create(
            user=user,
            email=(email or "")[:254],
            event=event,
            successful=successful,
            ip_address=client_ip(request),
            client=describe_client(raw_agent)[:120],
            user_agent=raw_agent[:1000],
            reason=(reason or "")[:200],
        )
    except Exception as exc:  # noqa: BLE001 - logged, never surfaced
        print(f"Could not record login event: {exc}")
        return None

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


def active_admin_count():
    return User.objects.filter(role="admin", is_active=True).count()


def change_user_role(*, target, actor, new_role):
    """Move ``target`` to ``new_role`` on behalf of ``actor`` (an admin).

    Guards against the two ways this locks people out: changing your own role
    (you would lose the screen you are standing on) and demoting the last
    remaining admin.
    """
    new_role = (new_role or "").strip().lower()
    if new_role not in VALID_ROLES:
        raise DomainError(
            f"'{new_role}' is not a valid role. Choose one of: {', '.join(VALID_ROLES)}."
        )
    if target.pk == getattr(actor, "pk", None):
        raise DomainError("You cannot change your own role - ask another admin to do it.")

    previous = target.role
    if previous == new_role:
        raise DomainError(f"{target.name} already has the '{new_role}' role.")
    if previous == "admin" and active_admin_count() <= 1:
        raise DomainError(
            "This is the last active admin. Promote someone else to admin first."
        )

    target.role = new_role
    # User.save() recomputes is_staff from the role.
    target.save(update_fields=["role", "is_staff"])

    audit_record(
        actor,
        f"Changed role for {target.name} ({target.email}): {previous} -> {new_role}",
    )
    return target


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
