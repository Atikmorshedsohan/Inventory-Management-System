"""Business logic for the catalog domain (items and the pending-item workflow)."""

from collections import defaultdict

from django.db import transaction
from django.utils import timezone

from audit.services import record as audit_record
from common.exceptions import DomainError

from .models import Item, PendingItem


def _normalize_unit(value):
    if value is None:
        return None
    value = str(value).strip()
    return value.lower() if value else None


def sync_reorder_alert(item):
    """Raise or clear the item's reorder alert; never break the caller."""
    try:
        from notifications.services import sync_item_alert

        sync_item_alert(item)
    except Exception as exc:  # noqa: BLE001 - alerts are best-effort
        print(f"Reorder alert sync failed for item {getattr(item, 'pk', '?')}: {exc}")


def _notify(**kwargs):
    """Best-effort in-app notification (never blocks item approval)."""
    try:
        from notifications.services import safe_notify

        safe_notify(**kwargs)
    except Exception as exc:  # noqa: BLE001 - notifications are best-effort
        print(f"Notification dispatch failed: {exc}")


def note_item_submitted(*, user, pending_item):
    """Record that ``user`` submitted a new item for approval and ping approvers."""
    audit_record(user, f"Submitted new item for approval: {pending_item.item_name}")
    try:
        from notifications.services import role_recipients, safe_broadcast

        safe_broadcast(
            recipients=role_recipients("admin", "manager", exclude=user),
            title=f"New item awaiting approval: {pending_item.item_name}",
            message=f"{getattr(user, 'name', 'Someone')} submitted '{pending_item.item_name}' "
                    f"(x{pending_item.quantity}). Review it on the Items page.",
            level="warning",
            category="general",
            link="/items/",
        )
    except Exception as exc:  # noqa: BLE001 - notifications are best-effort
        print(f"Notification dispatch failed: {exc}")
    return pending_item


def note_item_created(*, user, item):
    """Record a direct (admin/manager) item creation."""
    audit_record(user, f"Created item directly: {item.item_name}")
    return item


def _find_mergeable_item(pending):
    """Return an existing ``Item`` the pending row should merge into, or ``None``."""
    name = (pending.item_name or "").strip()
    candidates = Item.objects.filter(item_name__iexact=name)
    if pending.room_id:
        candidates = candidates.filter(room=pending.room)
    else:
        candidates = candidates.filter(room__isnull=True)
    candidates = list(candidates)

    pending_unit = _normalize_unit(pending.unit)
    for candidate in candidates:
        category_ok = (
            candidate.category_id == pending.category_id
            if pending.category_id is not None
            else candidate.category_id is None
        )
        unit_ok = (
            _normalize_unit(candidate.unit) == pending_unit
            if pending_unit is not None
            else _normalize_unit(candidate.unit) is None
        )
        if category_ok and unit_ok:
            return candidate
    return candidates[0] if candidates else None


@transaction.atomic
def approve_pending_item(*, pending, approver):
    """Approve a :class:`PendingItem`: merge into an existing item or create one."""
    if pending.status != "pending":
        raise DomainError(f"Cannot approve non-pending item (current: {pending.status})")

    name = (pending.item_name or "").strip()
    item = _find_mergeable_item(pending)

    if item is not None:
        item.quantity += pending.quantity
        # The merged stock never went through the ledger, so it is opening stock.
        item.opening_quantity += pending.quantity
        if pending.min_quantity and pending.min_quantity > item.min_quantity:
            item.min_quantity = pending.min_quantity
        if pending.description and not item.description:
            item.description = pending.description
        item.save(
            update_fields=["quantity", "opening_quantity", "min_quantity", "description"]
        )
        action = f"Approved and merged item: {item.item_name} (+{pending.quantity})"
    else:
        item = Item.objects.create(
            item_name=name,
            category=pending.category,
            room=pending.room,
            unit=pending.unit,
            quantity=pending.quantity,
            opening_quantity=pending.quantity,
            min_quantity=pending.min_quantity,
            description=pending.description,
        )
        action = f"Approved and created item: {item.item_name}"

    sync_reorder_alert(item)

    pending.status = "approved"
    pending.approved_by = approver
    pending.approved_at = timezone.now()
    pending.created_item = item
    pending.save()

    audit_record(approver, action)
    _notify(
        recipient=pending.requested_by,
        title=f"Item approved: {item.item_name}",
        message=f"Your submitted item '{item.item_name}' (x{pending.quantity}) was approved.",
        level="success",
        category="general",
        link="/items/",
        item=item,
    )
    return pending


@transaction.atomic
def reject_pending_item(*, pending, approver, reason):
    if pending.status != "pending":
        raise DomainError(f"Cannot reject non-pending item (current: {pending.status})")

    pending.status = "rejected"
    pending.rejection_reason = reason
    pending.approved_by = approver
    pending.approved_at = timezone.now()
    pending.save()

    audit_record(approver, f"Rejected pending item: {pending.item_name}. Reason: {reason}")
    _notify(
        recipient=pending.requested_by,
        title=f"Item rejected: {pending.item_name}",
        message=f"Your submitted item '{pending.item_name}' was rejected. Reason: {reason}",
        level="danger",
        category="general",
        link="/items/",
    )
    return pending


def roomwise_inventory():
    """Inventory grouped by room, with per-room totals (used by the room-wise page).

    Rooms come back **most-recently-updated first** - the room holding the item
    that changed last (a stock in/out, a move, an edit) sits at the top, so a
    just-stocked item's room (including the "General Storage" pool for
    unassigned items) is right there without scrolling.
    """
    items = Item.objects.select_related("category", "room").order_by("item_name")

    def blank_room():
        return {
            "room_id": None,
            "room_name": "General Storage",
            "room_type": "storage",
            "location": "",
            "room_key": False,
            "items": [],
            "total_quantity": 0,
            "item_count": 0,
            "last_updated": None,
        }

    rooms = defaultdict(blank_room)
    last_dt = {}  # room key -> latest item.updated_at (datetime), for sorting

    for item in items:
        key = item.room.room_id if item.room else "unassigned"
        bucket = rooms[key]
        if item.room:
            bucket.update(
                room_id=item.room.room_id,
                room_name=item.room.room_name,
                room_type=item.room.room_type,
                location=item.room.location,
                room_key=item.room.room_key,
            )
        bucket["items"].append(
            {
                "item_id": item.item_id,
                "item_name": item.item_name,
                "category": item.category.category_name if item.category else "N/A",
                "unit": item.unit,
                "quantity": item.quantity,
                "min_quantity": item.min_quantity,
                "is_low_stock": item.quantity <= item.min_quantity,
                "description": item.description,
                "updated_at": item.updated_at.isoformat() if item.updated_at else None,
            }
        )
        bucket["total_quantity"] += item.quantity
        bucket["item_count"] += 1
        if item.updated_at and (key not in last_dt or item.updated_at > last_dt[key]):
            last_dt[key] = item.updated_at
            bucket["last_updated"] = item.updated_at.isoformat()

    def sort_key(entry):
        room_key, room = entry
        touched = last_dt.get(room_key)
        return (
            touched is None,                     # rooms with no items sink to the bottom
            -touched.timestamp() if touched else 0.0,  # newest activity first
            room["room_id"] is None,             # General Storage after real rooms on ties
            room["room_name"] or "",
        )

    return [room for _, room in sorted(rooms.items(), key=sort_key)]
