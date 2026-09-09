"""Business logic for stock movements and the pending-transaction workflow."""

from django.db import transaction
from django.utils import timezone

from audit.services import record as audit_record
from catalog.models import Room
from common.exceptions import DomainError

from .models import RoomItemHistory, StockTransaction


def _adjust_quantity(item, txn_type, quantity):
    """Apply an IN/OUT delta to ``item.quantity`` (in memory)."""
    if txn_type == "IN":
        item.quantity += quantity
    elif txn_type == "OUT":
        if item.quantity < quantity:
            raise Exception("Insufficient stock")
        item.quantity -= quantity


def _sync_reorder_alert(item):
    """Raise or clear the item's reorder alert; never break the caller."""
    try:
        from notifications.services import sync_item_alert

        sync_item_alert(item)
    except Exception as exc:  # noqa: BLE001 - alerts are best-effort
        print(f"Reorder alert sync failed for item {getattr(item, 'pk', '?')}: {exc}")


def _notify(**kwargs):
    """Best-effort in-app notification (never blocks the stock operation)."""
    try:
        from notifications.services import safe_notify

        safe_notify(**kwargs)
    except Exception as exc:  # noqa: BLE001 - notifications are best-effort
        print(f"Notification dispatch failed: {exc}")


def note_pending_stock_created(pending):
    """Tell stock approvers a stock request is waiting for a decision."""
    try:
        from notifications.services import role_recipients, safe_broadcast

        safe_broadcast(
            recipients=role_recipients("admin", "manager", "staff", exclude=pending.requested_by),
            title=f"Stock {pending.type} request: {pending.item.item_name}",
            message=f"{getattr(pending.requested_by, 'name', 'Someone')} requested to stock "
                    f"{pending.type.lower()} {pending.quantity} {pending.item.item_name}. "
                    "Pending approval.",
            level="warning",
            category="general",
            link="/stock/",
            item=pending.item,
        )
    except Exception as exc:  # noqa: BLE001 - notifications are best-effort
        print(f"Notification dispatch failed: {exc}")


@transaction.atomic
def apply_stock_transaction(*, transaction_obj, user, room_id):
    """Post a stock transaction: adjust the item, optionally relocate it, log history + audit."""
    txn = transaction_obj
    item = txn.item
    actor = user if (user and user.is_authenticated) else None

    _adjust_quantity(item, txn.type, txn.quantity)

    room = Room.objects.filter(room_id=room_id).first() if room_id else None
    if room:
        item.room = room
    item.save(update_fields=["quantity", "room"])

    if room and txn.type in ("IN", "OUT"):
        RoomItemHistory.objects.create(
            item=item,
            from_room=item.room if txn.type == "OUT" else None,
            to_room=room if txn.type == "IN" else None,
            user=actor,
            remarks=f"Stock {txn.type}: {txn.quantity} units. {txn.notes or ''}",
        )

    audit_record(actor, f"Stock {txn.type}: {item.item_name} x{txn.quantity}")
    _sync_reorder_alert(item)
    return txn


# ---------------------------------------------------------------------------
# Pending stock approval workflow
# ---------------------------------------------------------------------------

@transaction.atomic
def approve_pending_stock(*, pending, approver):
    if pending.status != "pending":
        raise DomainError(
            f"Cannot approve non-pending transaction (current: {pending.status})"
        )

    item = pending.item
    if pending.type == "IN":
        item.quantity += pending.quantity
    elif pending.type == "OUT":
        if item.quantity < pending.quantity:
            raise DomainError("Insufficient stock to approve OUT transaction")
        item.quantity -= pending.quantity

    if pending.room:
        item.room = pending.room
    item.save(update_fields=["quantity", "room"])

    StockTransaction.objects.create(
        item=item,
        type=pending.type,
        quantity=pending.quantity,
        user=approver,
        notes=f"Approved from pending: {pending.notes or ''}",
    )

    if pending.room and pending.type in ("IN", "OUT"):
        RoomItemHistory.objects.create(
            item=item,
            from_room=item.room if pending.type == "OUT" else None,
            to_room=pending.room if pending.type == "IN" else None,
            user=approver,
            remarks=f"Stock {pending.type}: {pending.quantity} units",
        )

    pending.status = "approved"
    pending.approved_by = approver
    pending.approved_at = timezone.now()
    pending.save()

    audit_record(
        approver,
        f"Approved pending stock {pending.type}: {item.item_name} x{pending.quantity}",
    )
    _sync_reorder_alert(item)
    _notify(
        recipient=pending.requested_by,
        title=f"Stock {pending.type} approved: {item.item_name}",
        message=f"Your request to stock {pending.type.lower()} {pending.quantity} "
                f"{item.item_name} was approved.",
        level="success",
        category="general",
        link="/stock/",
        item=item,
    )
    return pending


@transaction.atomic
def reject_pending_stock(*, pending, approver, reason):
    if pending.status != "pending":
        raise DomainError(
            f"Cannot reject non-pending transaction (current: {pending.status})"
        )

    pending.status = "rejected"
    pending.rejection_reason = reason
    pending.approved_by = approver
    pending.approved_at = timezone.now()
    pending.save()

    audit_record(
        approver,
        f"Rejected pending stock {pending.type}: {pending.item.item_name}. Reason: {reason}",
    )
    _notify(
        recipient=pending.requested_by,
        title=f"Stock {pending.type} rejected: {pending.item.item_name}",
        message=f"Your request to stock {pending.type.lower()} {pending.quantity} "
                f"{pending.item.item_name} was rejected. Reason: {reason}",
        level="danger",
        category="general",
        link="/stock/",
        item=pending.item,
    )
    return pending
