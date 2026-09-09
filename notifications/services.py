"""Single entry point for creating in-app notifications and reorder alerts.

Other apps call :func:`sync_item_alert` after any change to an item's quantity
and this module decides whether to raise a new reorder alert, leave the existing
one in place, or resolve it.
"""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.utils import timezone

from .models import Notification

User = get_user_model()

# Roles that own the reorder / restock responsibility.
ALERT_ROLES = ("admin", "manager")

_REORDER_EMAIL_BODY = """{item_name} has reached its reorder level.

Current quantity : {quantity}
Minimum quantity : {min_quantity}
Room             : {room}

Please arrange a restock.

— CSE Inventory System
"""


def alert_recipients():
    """Active admins / managers who should receive stock alerts."""
    return list(User.objects.filter(role__in=ALERT_ROLES, is_active=True))


def role_recipients(*roles, exclude=None):
    """Active users in any of ``roles`` (default: admin/manager/staff).

    ``exclude`` (a user or user id) drops the actor so, e.g., a staff member who
    files a request is not notified about their own request.
    """
    roles = roles or ("admin", "manager", "staff")
    qs = User.objects.filter(role__in=roles, is_active=True)
    exclude_id = getattr(exclude, "pk", exclude)
    if exclude_id:
        qs = qs.exclude(pk=exclude_id)
    return list(qs)


def push(*, recipient, title, message="", level="info", category="general", link="", item=None):
    """Create one notification row and return it."""
    return Notification.objects.create(
        recipient=recipient,
        title=title,
        message=message,
        level=level,
        category=category,
        link=link,
        item=item,
    )


def broadcast(*, recipients, **kwargs):
    """``push`` the same notification to several recipients."""
    return [push(recipient=r, **kwargs) for r in recipients]


def notify(*, recipient, title, message="", level="info", category="general", link="", item=None):
    """Public entry point for other apps to raise one in-app notification.

    Returns the row, or ``None`` when there is no recipient (e.g. an
    unauthenticated actor). Never raises for a missing recipient.
    """
    if recipient is None or not getattr(recipient, "pk", None):
        return None
    return push(
        recipient=recipient, title=title, message=message, level=level,
        category=category, link=link, item=item,
    )


def safe_notify(**kwargs):
    """``notify`` that swallows every error.

    Call sites in the stock / requisition / key / catalog services use this so a
    notification failure can never roll back or block the real operation.
    """
    try:
        return notify(**kwargs)
    except Exception as exc:  # noqa: BLE001 - notifications are best-effort
        print(f"Notification failed: {exc}")
        return None


def safe_broadcast(*, recipients, **kwargs):
    """``push`` the same notification to several recipients, swallowing errors."""
    made = []
    for r in recipients or []:
        try:
            made.append(push(recipient=r, **kwargs))
        except Exception as exc:  # noqa: BLE001 - notifications are best-effort
            print(f"Notification failed for recipient {getattr(r, 'pk', '?')}: {exc}")
    return made


def _send_reorder_email(item, recipients):
    emails = [r.email for r in recipients if r.email]
    if not emails:
        return
    try:
        send_mail(
            subject=f"[CSE Inventory] Reorder alert: {item.item_name}",
            message=_REORDER_EMAIL_BODY.format(
                item_name=item.item_name,
                quantity=item.quantity,
                min_quantity=item.min_quantity,
                room=item.room.room_name if item.room else "Unassigned",
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=emails,
            fail_silently=True,
        )
    except Exception as exc:  # noqa: BLE001 - logged, never surfaced to the caller
        print(f"Reorder email failed: {exc}")


def notify_reorder(item, *, recipients=None):
    """Raise a reorder alert for ``item`` unless one is already open.

    Returns the list of notifications created (empty when the item is fine or
    every recipient already has an open alert for it).
    """
    if item.quantity > item.min_quantity:
        return []

    recipients = alert_recipients() if recipients is None else list(recipients)
    if not recipients:
        return []

    already = set(
        Notification.objects.filter(
            item=item, category="reorder", is_read=False
        ).values_list("recipient_id", flat=True)
    )

    room = item.room.room_name if item.room else "Unassigned"
    message = (
        f"{item.item_name} is at {item.quantity} {item.unit or 'units'} "
        f"(minimum {item.min_quantity}) in {room}."
    )
    created = [
        push(
            recipient=r,
            title=f"Reorder alert: {item.item_name}",
            message=message,
            level="warning",
            category="reorder",
            link="/reconciliation/",
            item=item,
        )
        for r in recipients
        if r.pk not in already
    ]

    if created and getattr(settings, "REORDER_ALERT_EMAILS", False):
        _send_reorder_email(item, recipients)

    return created


def resolve_reorder(item):
    """Mark every open reorder alert for ``item`` as read. Returns the count."""
    return Notification.objects.filter(
        item=item, category="reorder", is_read=False
    ).update(is_read=True, read_at=timezone.now())


def sync_item_alert(item):
    """Fire or clear a reorder alert to match the item's current quantity."""
    if item.quantity <= item.min_quantity:
        return notify_reorder(item)
    resolve_reorder(item)
    return []


def check_all_reorder_levels():
    """Scan every item and reconcile its reorder alerts. Returns alerts raised."""
    from catalog.models import Item

    raised = 0
    for item in Item.objects.select_related("room").all():
        raised += len(sync_item_alert(item))
    return raised
