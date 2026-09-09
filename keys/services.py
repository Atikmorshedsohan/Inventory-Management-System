"""Key-borrow lifecycle: request -> approve / reject -> pickup -> return."""

from django.db import transaction
from django.utils import timezone

from common.exceptions import DomainError

from .models import KeyAuditLog, KeyBorrow
from .utils import user_display

_ACTIVE_STATUSES = ("pending", "approved", "borrowed")
_CANCELLABLE_STATUSES = ("pending", "approved")
# Key states that block a new request even when no borrow row is holding it.
# ``reserved`` is deliberately absent: a reservation with no active borrow
# behind it is stale, and the incoming request is free to take it over.
_KEY_BLOCKED = ("in_use", "lost", "maintenance")


def _notify_borrower(borrow, *, title, message, level="info"):
    """Best-effort in-app notification to the borrower (never blocks the flow)."""
    try:
        from notifications.services import safe_notify

        safe_notify(
            recipient=borrow.borrower,
            title=title,
            message=message,
            level=level,
            category="general",
            link="/roomwise-inventory/",
        )
    except Exception as exc:  # noqa: BLE001 - notifications are best-effort
        print(f"Notification dispatch failed: {exc}")


def _notify_key_staff(borrow, *, title, message, level="info", actor=None):
    """Best-effort fan-out to staff/admin/manager for key activity.

    ``actor`` is excluded so a staff member acting on a borrow is not pinged
    about their own action.
    """
    try:
        from notifications.services import role_recipients, safe_broadcast

        safe_broadcast(
            recipients=role_recipients("staff", "admin", "manager", exclude=actor),
            title=title,
            message=message,
            level=level,
            category="general",
            link="/roomwise-inventory/",
        )
    except Exception as exc:  # noqa: BLE001 - notifications are best-effort
        print(f"Notification dispatch failed: {exc}")


def _assign_key(key, borrower, when):
    key.status = "in_use"
    key.assigned_to = borrower
    key.assigned_date = when
    key.save()


def _reserve_key(key):
    """Take the key off the shelf the moment a borrow request is filed."""
    if key.status == "available":
        key.status = "reserved"
        key.save(update_fields=["status", "updated_at"])


def _release_key_if_idle(key, *, ignore_pk=None):
    """Return a *reserved* key to ``available`` once nothing is holding it.

    A key that has actually been handed over (``in_use``) or is lost / in
    maintenance is left alone - only a dangling reservation is cleared.
    """
    if key.status != "reserved":
        return
    holds = KeyBorrow.objects.filter(key=key, status__in=_ACTIVE_STATUSES)
    if ignore_pk is not None:
        holds = holds.exclude(pk=ignore_pk)
    if not holds.exists():
        key.status = "available"
        key.save(update_fields=["status", "updated_at"])


def _cancel_other_requests(key, keep_pk, approver, when):
    others = (
        KeyBorrow.objects.select_for_update()
        .filter(key=key, status__in=_CANCELLABLE_STATUSES)
        .exclude(pk=keep_pk)
    )
    if others.exists():
        others.update(
            status="rejected",
            rejection_reason="Auto-cancelled: key handed to another borrower",
            approver=approver,
            approved_at=when,
        )


@transaction.atomic
def request_borrow(*, serializer, actor):
    """Create a borrow request for ``actor`` after the anti-duplicate checks."""
    key = serializer.validated_data["key"]
    expected_return_at = serializer.validated_data.get("expected_return_at")
    now = timezone.now()

    if expected_return_at and expected_return_at <= now:
        raise DomainError("Expected return time must be in the future")

    stale = KeyBorrow.objects.select_for_update().filter(
        key=key, borrower=actor, status="pending"
    )
    if stale.exists():
        stale.update(
            status="rejected",
            rejection_reason="Auto-cancelled: replaced by a new request",
            approver=actor,
            approved_at=now,
        )

    clash = (
        KeyBorrow.objects.select_for_update()
        .filter(key=key, status__in=_ACTIVE_STATUSES)
        .first()
    )
    if clash is not None:
        raise DomainError(
            f"Key {key.key_number} is unavailable - {user_display(clash.borrower)} "
            f"already has an active request for it ({clash.get_status_display().lower()})."
        )
    if key.status in _KEY_BLOCKED:
        raise DomainError(
            f"Key {key.key_number} is unavailable (current status: "
            f"{key.get_status_display()})."
        )

    borrow = serializer.save(borrower=actor)
    _reserve_key(key)
    KeyAuditLog.objects.create(
        key=borrow.key,
        action="borrowed",
        performed_by=actor,
        notes=f"Requested to borrow key #{borrow.borrow_id}; key reserved.",
    )
    _notify_key_staff(
        borrow,
        title=f"Key request: {key.key_number} ({key.room_name})",
        message=f"{user_display(actor)} requested key {key.key_number} - "
                f"purpose: {borrow.purpose or 'n/a'}. Awaiting approval.",
        level="warning",
        actor=actor,
    )
    return borrow


@transaction.atomic
def approve_borrow(*, borrow, approver):
    """Approve a request. The key is NOT handed over yet.

    The request parks in ``approved`` until someone confirms the physical
    handover via :func:`confirm_pickup`, which is what actually assigns the key
    and stamps ``borrowed_at``.
    """
    if borrow.status == "returned":
        if borrow.key.status not in ("available", "reserved"):
            raise DomainError("Key is not available to re-issue this returned request")
    elif borrow.status not in _CANCELLABLE_STATUSES:
        raise DomainError(
            f"Cannot approve request with status: {borrow.status}. "
            "Only pending or approved requests can be approved."
        )

    clash = (
        KeyBorrow.objects.filter(key=borrow.key, status__in=("approved", "borrowed"))
        .exclude(pk=borrow.pk)
        .first()
    )
    if clash is not None:
        state = "awaiting pickup" if clash.status == "approved" else "already handed over"
        raise DomainError(
            f"Key {borrow.key.key_number} is {state} on request #{clash.borrow_id} "
            f"({user_display(clash.borrower)}). Resolve that request first."
        )

    borrow.status = "approved"
    borrow.approver = approver
    borrow.approved_at = timezone.now()
    borrow.borrowed_at = None
    borrow.save()

    KeyAuditLog.objects.create(
        key=borrow.key,
        action="approved",
        performed_by=approver,
        notes=(
            f"Approved request #{borrow.borrow_id} for {user_display(borrow.borrower)}. "
            "Awaiting pickup confirmation."
        ),
    )
    _notify_borrower(
        borrow,
        title=f"Key request approved: {borrow.key.key_number}",
        message=f"Your request for key {borrow.key.key_number} ({borrow.key.room_name}) "
                "was approved. Collect it to start your borrow.",
        level="success",
    )
    return borrow


@transaction.atomic
def confirm_pickup(*, borrow, actor, notes=""):
    """Record the physical handover of an approved key.

    This is the step that assigns the key to the borrower, stamps
    ``borrowed_at``, and notes who released it.
    """
    if borrow.status != "approved":
        raise DomainError(
            f"Only approved requests can be picked up, current status: {borrow.status}"
        )
    if borrow.key.status not in ("available", "reserved", "in_use"):
        raise DomainError(
            f"Key {borrow.key.key_number} is not collectable (status: {borrow.key.status})"
        )

    now = timezone.now()
    borrow.status = "borrowed"
    borrow.borrowed_at = now
    borrow.handed_over_by = actor if (actor and actor.is_authenticated) else None
    borrow.handover_notes = (notes or "").strip() or None
    borrow.save()

    _assign_key(borrow.key, borrow.borrower, now)
    _cancel_other_requests(borrow.key, borrow.pk, actor, now)

    detail = f" Notes: {borrow.handover_notes}" if borrow.handover_notes else ""
    KeyAuditLog.objects.create(
        key=borrow.key,
        action="picked_up",
        performed_by=actor,
        notes=(
            f"Handover confirmed: key {borrow.key.key_number} given to "
            f"{user_display(borrow.borrower)} by {user_display(actor)}.{detail}"
        ),
    )
    _notify_borrower(
        borrow,
        title=f"Key collected: {borrow.key.key_number}",
        message=f"Key {borrow.key.key_number} ({borrow.key.room_name}) is now assigned "
                "to you. Return it from the Roomwise Inventory page when you are done.",
        level="info",
    )
    _notify_key_staff(
        borrow,
        title=f"Key handed over: {borrow.key.key_number} ({borrow.key.room_name})",
        message=f"{user_display(borrow.borrower)} collected key {borrow.key.key_number}.",
        level="info",
        actor=actor,
    )
    return borrow


# Kept so existing callers/imports keep working.
pickup_borrow = confirm_pickup


@transaction.atomic
def return_borrow(*, borrow, actor, location):
    if borrow.status != "borrowed":
        raise DomainError(
            f"Only borrowed keys can be returned, current status: {borrow.status}"
        )

    borrow.status = "returned"
    borrow.returned_at = timezone.now()
    borrow.save()

    key = borrow.key
    key.status = "available"
    key.assigned_to = None
    key.assigned_date = None
    key.last_location = location
    key.save()

    KeyAuditLog.objects.create(
        key=key,
        action="returned_borrow",
        performed_by=actor,
        notes=f"Key returned by {user_display(borrow.borrower)}. Location: {location}",
    )
    _notify_borrower(
        borrow,
        title=f"Key returned: {key.key_number}",
        message=f"Key {key.key_number} ({key.room_name}) was returned to {location}.",
        level="success",
    )
    _notify_key_staff(
        borrow,
        title=f"Key returned: {key.key_number} ({key.room_name})",
        message=f"{user_display(borrow.borrower)} returned key {key.key_number} "
                f"to {location}. It is available again.",
        level="success",
        actor=actor,
    )
    return borrow


@transaction.atomic
def reject_borrow(*, borrow, approver, reason):
    """Reject a pending request, or cancel an approved one before pickup."""
    if borrow.status not in _CANCELLABLE_STATUSES:
        raise DomainError(
            f"Cannot reject request with status: {borrow.status}. "
            "Only pending requests, or approved ones not yet picked up, can be rejected."
        )

    was_approved = borrow.status == "approved"
    borrow.status = "rejected"
    borrow.rejection_reason = reason
    borrow.approver = approver
    borrow.approved_at = timezone.now()
    borrow.save()

    # This request was holding the key off the shelf; put it back if nothing
    # else is waiting on it.
    _release_key_if_idle(borrow.key, ignore_pk=borrow.pk)

    verb = "Approval cancelled before pickup for" if was_approved else "Rejected"
    KeyAuditLog.objects.create(
        key=borrow.key,
        action="rejected",
        performed_by=approver,
        notes=f"{verb} borrow request #{borrow.borrow_id}. Reason: {reason}",
    )
    _notify_borrower(
        borrow,
        title=f"Key request rejected: {borrow.key.key_number}",
        message=f"Your request for key {borrow.key.key_number} ({borrow.key.room_name}) "
                f"was not approved. Reason: {reason}",
        level="danger",
    )
    return borrow
