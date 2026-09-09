"""Read-only aggregations for the dashboard / room-overview / activity pages."""

from datetime import datetime, time, timedelta

from django.db.models import Count, F, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from catalog.models import Item, Room
from keys.models import KeyBorrow
from requisitions.models import Requisition
from stock.models import RoomItemHistory, StockTransaction


def dashboard_stats():
    now = timezone.now()
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    stock_in_month = (
        StockTransaction.objects.filter(type="IN", timestamp__gte=start_of_month)
        .aggregate(total=Sum("quantity"))["total"]
        or 0
    )
    return {
        "total_items": Item.objects.count(),
        "low_stock_items": Item.objects.filter(quantity__lte=F("min_quantity")).count(),
        "available_items": Item.objects.filter(quantity__gt=0).count(),
        "stock_in_month": stock_in_month,
        "pending_requisitions": Requisition.objects.filter(status="pending").count(),
    }


def low_stock_items():
    """Every item at or below its minimum, with the room it sits in."""
    items = (
        Item.objects.select_related("category", "room")
        .filter(quantity__lte=F("min_quantity"))
        .order_by(F("quantity") - F("min_quantity"), "item_name")
    )
    return [
        {
            "item_id": item.item_id,
            "item_name": item.item_name,
            "category": item.category.category_name if item.category else "Uncategorized",
            "room_id": item.room.room_id if item.room else None,
            "room_name": item.room.room_name if item.room else "Unassigned",
            "unit": item.unit,
            "quantity": item.quantity,
            "min_quantity": item.min_quantity,
            "shortage": item.min_quantity - item.quantity,
            "out_of_stock": item.quantity <= 0,
        }
        for item in items
    ]


def room_snapshot():
    """Point-in-time picture of what is in every room, for printing/export."""
    from catalog.services import roomwise_inventory

    rooms = roomwise_inventory()
    for room in rooms:
        room["low_stock_count"] = sum(1 for i in room["items"] if i["is_low_stock"])

    return {
        "generated_at": timezone.now(),
        "room_count": len(rooms),
        "item_count": sum(r["item_count"] for r in rooms),
        "total_quantity": sum(r["total_quantity"] for r in rooms),
        "low_stock_count": sum(r["low_stock_count"] for r in rooms),
        "rooms": rooms,
    }


def stock_movement_series(days=30):
    """Daily stock IN vs stock OUT totals for the last ``days`` days.

    Every day in the window is present (zero-filled) so the chart has no gaps.
    """
    # ``or`` would swallow an explicit 0, so treat only None as "unset".
    days = 30 if days is None else max(1, min(int(days), 365))
    today = timezone.localdate()
    start_day = today - timedelta(days=days - 1)
    since = timezone.make_aware(
        datetime.combine(start_day, time.min), timezone.get_current_timezone()
    )

    buckets = {start_day + timedelta(days=i): {"in": 0, "out": 0} for i in range(days)}

    rows = (
        StockTransaction.objects.filter(timestamp__gte=since, type__in=("IN", "OUT"))
        .annotate(day=TruncDate("timestamp"))
        .values("day", "type")
        .annotate(total=Sum("quantity"))
    )
    for row in rows:
        bucket = buckets.get(row["day"])
        if bucket is not None:
            bucket["in" if row["type"] == "IN" else "out"] += row["total"] or 0

    labels, stock_in, stock_out = [], [], []
    for day in sorted(buckets):
        labels.append(day.isoformat())
        stock_in.append(buckets[day]["in"])
        stock_out.append(buckets[day]["out"])

    return {
        "days": days,
        "start": start_day.isoformat(),
        "end": today.isoformat(),
        "labels": labels,
        "stock_in": stock_in,
        "stock_out": stock_out,
        "total_in": sum(stock_in),
        "total_out": sum(stock_out),
        "net": sum(stock_in) - sum(stock_out),
    }


def room_overview():
    since = timezone.now() - timedelta(days=7)
    moves = (
        RoomItemHistory.objects.select_related("item", "from_room", "to_room", "user")
        .filter(moved_at__gte=since)
        .order_by("-moved_at")
    )
    return {
        "total_rooms": Room.objects.count(),
        "unassigned_items": Item.objects.filter(room__isnull=True).count(),
        "recent_moves_7d": moves.count(),
        "recent_moves": [
            {
                "item_name": m.item.item_name,
                "from_room_name": m.from_room.room_name if m.from_room else None,
                "to_room_name": m.to_room.room_name if m.to_room else None,
                "user_name": m.user.name if m.user else "System",
                "moved_at": m.moved_at,
            }
            for m in moves[:10]
        ],
    }


def reconciliation_report():
    """Compare every item's balance against the sum of its stock transactions.

    Expected balance = ``opening_quantity + IN - OUT + ADJUST``. Any non-zero
    ``discrepancy`` means the item's quantity changed without a matching ledger
    entry (a hand-edited quantity, a data import, a bug) and needs a look.
    """
    ledger = {
        row["item"]: row
        for row in StockTransaction.objects.values("item").annotate(
            total_in=Sum("quantity", filter=Q(type="IN")),
            total_out=Sum("quantity", filter=Q(type="OUT")),
            total_adjust=Sum("quantity", filter=Q(type="ADJUST")),
            txn_count=Count("transaction_id"),
        )
    }

    rows = []
    balanced = 0
    for item in Item.objects.select_related("category", "room").order_by("item_name"):
        agg = ledger.get(item.item_id, {})
        total_in = agg.get("total_in") or 0
        total_out = agg.get("total_out") or 0
        total_adjust = agg.get("total_adjust") or 0
        opening = item.opening_quantity or 0
        expected = opening + total_in - total_out + total_adjust
        discrepancy = item.quantity - expected
        is_balanced = discrepancy == 0
        balanced += is_balanced
        rows.append(
            {
                "item_id": item.item_id,
                "item_name": item.item_name,
                "category": item.category.category_name if item.category else "N/A",
                "room_name": item.room.room_name if item.room else "Unassigned",
                "unit": item.unit,
                "system_quantity": item.quantity,
                "opening_quantity": opening,
                "total_in": total_in,
                "total_out": total_out,
                "total_adjust": total_adjust,
                "transaction_count": agg.get("txn_count") or 0,
                "expected_quantity": expected,
                "discrepancy": discrepancy,
                "status": "balanced" if is_balanced else ("over" if discrepancy > 0 else "short"),
            }
        )

    return {
        "generated_at": timezone.now(),
        "total_items": len(rows),
        "balanced": balanced,
        "mismatched": len(rows) - balanced,
        "rows": rows,
    }


def roomwise_activity():
    since = timezone.now() - timedelta(days=7)

    transactions = (
        StockTransaction.objects.select_related("item", "user")
        .filter(timestamp__gte=since)
        .order_by("-timestamp")
    )
    moves = (
        RoomItemHistory.objects.select_related("item", "from_room", "to_room", "user")
        .filter(moved_at__gte=since)
        .order_by("-moved_at")
    )
    key_borrows = (
        KeyBorrow.objects.select_related("key", "borrower", "approver")
        .filter(requested_at__gte=since)
        .order_by("-requested_at")
    )

    return {
        "recent_transactions": [
            {
                "type": t.type,
                "item_name": t.item.item_name,
                "quantity": t.quantity,
                "user_name": t.user.name if t.user else "System",
                "timestamp": t.timestamp,
                "notes": t.notes or "",
            }
            for t in transactions[:10]
        ],
        "recent_moves": [
            {
                "item_name": m.item.item_name,
                "from_room_name": m.from_room.room_name if m.from_room else "Unassigned",
                "to_room_name": m.to_room.room_name if m.to_room else "Unassigned",
                "user_name": m.user.name if m.user else "System",
                "moved_at": m.moved_at,
                "remarks": m.remarks or "",
            }
            for m in moves[:10]
        ],
        "recent_key_borrows": [
            {
                "key_number": b.key.key_number,
                "room_name": b.key.room_name,
                "borrower_name": b.borrower.name if b.borrower else "Unknown",
                "borrower_email": b.borrower.email if b.borrower else None,
                "borrower_phone": b.borrower.phone_number if b.borrower else None,
                "borrower_department": b.borrower.department if b.borrower else None,
                "approver_name": b.approver.name if b.approver else None,
                "status": b.status,
                "requested_at": b.requested_at,
                "approved_at": b.approved_at,
                "borrowed_at": b.borrowed_at,
                "returned_at": b.returned_at,
                "purpose": b.purpose or "",
                "expected_return_at": b.expected_return_at,
            }
            for b in key_borrows[:10]
        ],
    }
