"""Read-only aggregations for the dashboard / room-overview / activity pages."""

from datetime import timedelta

from django.db.models import F, Sum
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
