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
    return txn


@transaction.atomic
def record_item_move(*, history):
    """Move an item to ``history.to_room`` and log it."""
    item = history.item
    item.room = history.to_room
    item.save(update_fields=["room"])
    audit_record(
        history.user,
        f"Moved '{item.item_name}' from {history.from_room} to {history.to_room}",
    )
    return history


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
    return pending
