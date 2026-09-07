"""Key-borrow lifecycle: request -> approve / reject -> pickup -> return."""

from django.db import transaction
from django.utils import timezone

from common.exceptions import DomainError

from .models import KeyAuditLog, KeyBorrow
from .utils import user_display

_ACTIVE_STATUSES = ("pending", "approved", "borrowed")
_CANCELLABLE_STATUSES = ("pending", "approved")


def _assign_key(key, borrower, when):
    key.status = "in_use"
    key.assigned_to = borrower
    key.assigned_date = when
    key.save()


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

    if (
        KeyBorrow.objects.select_for_update()
        .filter(key=key, status__in=_ACTIVE_STATUSES)
        .exists()
    ):
        raise DomainError("This key already has a pending or active borrow request")
    if key.status != "available":
        raise DomainError(f"Key is not available (current status: {key.status})")

    borrow = serializer.save(borrower=actor)
    KeyAuditLog.objects.create(
        key=borrow.key,
        action="borrowed",
        performed_by=actor,
        notes=f"Requested to borrow key #{borrow.borrow_id}",
    )
    return borrow


@transaction.atomic
def approve_borrow(*, borrow, approver):
    """Approve and hand the key over immediately."""
    if borrow.status == "returned":
        if borrow.key.status != "available":
            raise DomainError("Key is not available to re-issue this returned request")
    elif borrow.status not in _CANCELLABLE_STATUSES:
        raise DomainError(
            f"Cannot approve request with status: {borrow.status}. "
            "Only pending or approved requests can be approved."
        )

    now = timezone.now()
    borrow.status = "borrowed"
    borrow.approver = approver
    borrow.approved_at = now
    borrow.borrowed_at = now
    borrow.save()

    _assign_key(borrow.key, borrow.borrower, now)
    _cancel_other_requests(borrow.key, borrow.pk, approver, now)

    KeyAuditLog.objects.create(
        key=borrow.key,
        action="borrowed",
        performed_by=approver,
        notes=(
            f"Approved and handed over request #{borrow.borrow_id} "
            f"to {user_display(borrow.borrower)}"
        ),
    )
    return borrow


@transaction.atomic
def pickup_borrow(*, borrow, actor):
    """A viewer collects a key from an already-approved request."""
    if borrow.status != "approved":
        raise DomainError(
            f"Key can only be picked up from approved requests, current status: {borrow.status}"
        )

    now = timezone.now()
    borrow.status = "borrowed"
    borrow.borrowed_at = now
    borrow.save()

    _assign_key(borrow.key, borrow.borrower, now)
    _cancel_other_requests(borrow.key, borrow.pk, actor, now)

    KeyAuditLog.objects.create(
        key=borrow.key,
        action="borrowed",
        performed_by=actor,
        notes=f"Key picked up by {user_display(borrow.borrower)}",
    )
    return borrow


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
    return borrow


@transaction.atomic
def reject_borrow(*, borrow, approver, reason):
    if borrow.status != "pending":
        raise DomainError(f"Cannot reject request with status: {borrow.status}")

    borrow.status = "rejected"
    borrow.rejection_reason = reason
    borrow.approver = approver
    borrow.approved_at = timezone.now()
    borrow.save()

    KeyAuditLog.objects.create(
        key=borrow.key,
        action="returned_borrow",
        performed_by=approver,
        notes=f"Borrow request #{borrow.borrow_id} rejected. Reason: {reason}",
    )
    return borrow
