"""Business logic for stock movements, bulk import, transfers and the
pending-transaction workflow."""

import csv
import io

from django.db import transaction
from django.utils import timezone

from audit.services import record as audit_record
from catalog.models import Item, Room
from common.exceptions import DomainError

from .models import RoomItemHistory, StockImportBatch, StockTransaction


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
            transfer_type="full",
            quantity=txn.quantity,
            remarks=f"Stock {txn.type}: {txn.quantity} units. {txn.notes or ''}",
        )

    audit_record(actor, f"Stock {txn.type}: {item.item_name} x{txn.quantity}")
    _sync_reorder_alert(item)
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


# ---------------------------------------------------------------------------
# Move Item workflow
# ---------------------------------------------------------------------------

def _find_or_create_sibling(item, room):
    """Return the matching item row in ``room`` (same name/category/unit) or make one."""
    sibling = (
        Item.objects.filter(
            item_name__iexact=item.item_name,
            room=room,
            category=item.category,
            unit=item.unit,
        )
        .exclude(pk=item.pk)
        .first()
    )
    if sibling:
        return sibling, False
    sibling = Item.objects.create(
        item_name=item.item_name,
        category=item.category,
        room=room,
        unit=item.unit,
        quantity=0,
        opening_quantity=0,
        min_quantity=item.min_quantity,
        description=item.description,
    )
    return sibling, True


@transaction.atomic
def transfer_item(*, item, to_room, quantity=None, user=None, remarks=""):
    """Move stock of ``item`` into ``to_room``.

    * Full move (quantity omitted or equal to the whole balance) simply
      reassigns the item's room - the ledger is untouched.
    * Partial move splits the balance: the source item is drawn down with an
      ``OUT`` transaction and a sibling row in ``to_room`` is topped up with an
      ``IN`` transaction, so the reconciliation report stays balanced.

    Returns the :class:`RoomItemHistory` row, which carries before/after
    snapshots for both rooms.
    """
    actor = user if (user and getattr(user, "is_authenticated", False)) else None
    remarks = (remarks or "").strip()

    if to_room is None:
        raise DomainError("A destination room is required.")
    if item.room_id and item.room_id == to_room.room_id:
        raise DomainError(f"'{item.item_name}' is already in {to_room.room_name}.")

    whole = item.quantity
    qty = whole if quantity in (None, "", 0) else int(quantity)
    if qty < 1:
        raise DomainError("Transfer quantity must be at least 1.")
    if qty > whole:
        raise DomainError(
            f"Cannot transfer {qty}; only {whole} {item.unit or 'units'} in stock."
        )

    from_room = item.room
    from_room_name = from_room.room_name if from_room else "Unassigned"
    source_before = whole

    if qty == whole:
        # Whole-item relocation - no quantity change, no ledger entry.
        # Per-room snapshot: the source room empties, the destination fills.
        item.room = to_room
        item.save(update_fields=["room"])
        history = RoomItemHistory.objects.create(
            item=item,
            from_room=from_room,
            to_room=to_room,
            user=actor,
            transfer_type="full",
            quantity=qty,
            dest_item=None,
            source_qty_before=source_before,
            source_qty_after=0,
            dest_qty_before=0,
            dest_qty_after=whole,
            remarks=remarks or f"Full move of {qty} {item.unit or 'unit(s)'}",
        )
        audit_record(
            actor,
            f"Transferred {item.item_name} (all {qty}) from {from_room_name} "
            f"to {to_room.room_name}",
        )
        _sync_reorder_alert(item)
        _notify(
            recipient=actor,
            title=f"Item moved: {item.item_name}",
            message=f"All {qty} {item.unit or 'unit(s)'} moved from {from_room_name} "
                    f"to {to_room.room_name}.",
            level="success",
            category="transfer",
            link="/stock/",
            item=item,
        )
        return history

    # Partial move -> split the balance across two item rows.
    dest_item, created = _find_or_create_sibling(item, to_room)
    dest_before = dest_item.quantity

    item.quantity -= qty
    item.save(update_fields=["quantity"])
    StockTransaction.objects.create(
        item=item,
        type="OUT",
        quantity=qty,
        user=actor,
        notes=f"Transfer to {to_room.room_name}. {remarks}".strip(),
    )

    dest_item.quantity += qty
    dest_item.save(update_fields=["quantity"])
    StockTransaction.objects.create(
        item=dest_item,
        type="IN",
        quantity=qty,
        user=actor,
        notes=f"Transfer from {from_room_name}. {remarks}".strip(),
    )

    history = RoomItemHistory.objects.create(
        item=item,
        from_room=from_room,
        to_room=to_room,
        user=actor,
        transfer_type="partial",
        quantity=qty,
        dest_item=dest_item,
        source_qty_before=source_before,
        source_qty_after=item.quantity,
        dest_qty_before=dest_before,
        dest_qty_after=dest_item.quantity,
        remarks=remarks or f"Partial move of {qty} {item.unit or 'unit(s)'}",
    )
    audit_record(
        actor,
        f"Transferred {qty} x {item.item_name} from {from_room_name} to "
        f"{to_room.room_name}"
        + (" (new room row created)" if created else ""),
    )
    _sync_reorder_alert(item)
    _sync_reorder_alert(dest_item)
    _notify(
        recipient=actor,
        title=f"Item moved: {item.item_name}",
        message=f"{qty} {item.unit or 'unit(s)'} moved from {from_room_name} to "
                f"{to_room.room_name}. {item.item_name} left with {item.quantity}.",
        level="success",
        category="transfer",
        link="/stock/",
        item=item,
    )
    return history


# ---------------------------------------------------------------------------
# Bulk stock import (CSV)
# ---------------------------------------------------------------------------

IMPORT_TEMPLATE_HEADERS = ["item_name", "item_id", "quantity", "room", "notes"]

IMPORT_TEMPLATE_CSV = (
    "item_name,item_id,quantity,room,notes\r\n"
    "HDMI Cable,,25,Lab 1,Restock from supplier invoice #123\r\n"
    ",42,10,,Quantities counted 2026-09-01\r\n"
)


def _clean_header(name):
    return (name or "").strip().lower().replace(" ", "_")


def _resolve_import_item(row):
    raw_id = (row.get("item_id") or "").strip()
    name = (row.get("item_name") or "").strip()
    room_ref = (row.get("room") or "").strip()

    room = _resolve_room(room_ref) if room_ref else None
    if room_ref and room is None:
        raise DomainError(f"Room '{room_ref}' not found")

    if raw_id:
        if not raw_id.isdigit():
            raise DomainError(f"item_id '{raw_id}' is not a number")
        item = Item.objects.filter(pk=int(raw_id)).first()
        if item is None:
            raise DomainError(f"No item with id {raw_id}")
        return item, room

    if not name:
        raise DomainError("Row needs an item_name or item_id")

    matches = Item.objects.filter(item_name__iexact=name)
    if room is not None:
        matches = matches.filter(room=room)
    matches = list(matches[:2])
    if not matches:
        raise DomainError(f"No item named '{name}'" + (f" in {room.room_name}" if room else ""))
    if len(matches) > 1:
        raise DomainError(
            f"'{name}' matches several items - add an item_id or a room to disambiguate"
        )
    return matches[0], room


def _resolve_room(ref):
    ref = ref.strip()
    if not ref:
        return None
    if ref.isdigit():
        room = Room.objects.filter(pk=int(ref)).first()
        if room:
            return room
    return Room.objects.filter(room_name__iexact=ref).first()


def bulk_import_stock(*, file, user, filename=""):
    """Stock-in every row of an uploaded CSV.

    Each row is applied in its own savepoint, so one bad row does not lose the
    others. Returns the :class:`StockImportBatch` with a per-row report.
    """
    actor = user if (user and getattr(user, "is_authenticated", False)) else None

    raw = file.read()
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8-sig", errors="replace")
    raw = raw.lstrip("﻿")

    reader = csv.reader(io.StringIO(raw))
    try:
        header = next(reader)
    except StopIteration:
        raise DomainError("The CSV file is empty.")

    cols = [_clean_header(h) for h in header]
    if "quantity" not in cols:
        raise DomainError("The CSV needs at least an 'item_name' (or 'item_id') and 'quantity' column.")
    if "item_name" not in cols and "item_id" not in cols:
        raise DomainError("The CSV needs an 'item_name' or 'item_id' column.")

    report = []
    success = 0
    touched = {}

    for line_no, values in enumerate(reader, start=2):
        if not any((v or "").strip() for v in values):
            continue  # skip blank lines
        row = {cols[i]: values[i] for i in range(min(len(cols), len(values)))}
        entry = {"row": line_no, "item": row.get("item_name") or row.get("item_id") or "", }
        try:
            qty_raw = (row.get("quantity") or "").strip()
            if not qty_raw or not qty_raw.lstrip("+").isdigit():
                raise DomainError(f"quantity '{qty_raw}' is not a positive whole number")
            qty = int(qty_raw)
            if qty < 1:
                raise DomainError("quantity must be at least 1")

            with transaction.atomic():
                item, room = _resolve_import_item(row)
                txn = StockTransaction.objects.create(
                    item=item,
                    type="IN",
                    quantity=qty,
                    user=actor,
                    notes=(row.get("notes") or "").strip() or f"Bulk import: {filename or 'CSV'}",
                )
                apply_stock_transaction(
                    transaction_obj=txn,
                    user=user,
                    room_id=room.room_id if room else None,
                )
            touched[item.pk] = item
            entry.update(status="ok", item=item.item_name, quantity=qty,
                         message=f"Stocked in {qty} (now {item.quantity})")
            success += 1
        except DomainError as exc:
            entry.update(status="error", message=str(exc.detail))
        except Exception as exc:  # noqa: BLE001 - surfaced in the row report
            entry.update(status="error", message=str(exc))
        report.append(entry)

    batch = StockImportBatch.objects.create(
        filename=filename or getattr(file, "name", "") or "upload.csv",
        uploaded_by=actor,
        total_rows=len(report),
        success_count=success,
        error_count=len(report) - success,
        report=report,
    )
    audit_record(
        actor,
        f"Bulk stock import '{batch.filename}': {success} ok, "
        f"{batch.error_count} failed ({batch.total_rows} rows)",
    )
    for item in touched.values():
        _sync_reorder_alert(item)
    _notify(
        recipient=actor,
        title=f"Bulk import finished: {batch.filename}",
        message=(
            f"{success} of {batch.total_rows} row(s) stocked in"
            + (f", {batch.error_count} failed - open the import to see why."
               if batch.error_count else " with no errors.")
        ),
        level="warning" if batch.error_count else "success",
        category="import",
        link="/stock/",
    )
    return batch


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
            transfer_type="full",
            quantity=pending.quantity,
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
