"""Single definition of the inventory report.

:func:`build_report` returns the report as an ordered list of :class:`Section`
objects. Both the CSV and the Excel exporter render that same structure, so the
two downloads always contain exactly the same data - they cannot drift apart
the way two hand-written builders did.
"""

from dataclasses import dataclass, field
from datetime import timedelta

from django.db.models import Count, F
from django.utils import timezone

from audit.models import AuditLog
from catalog.models import Item
from requisitions.models import Requisition, RequisitionItem
from stock.models import StockTransaction

DEFAULT_DAYS = 90
ROW_LIMIT = 500


@dataclass
class Section:
    """One block of the report: a CSV block and an Excel worksheet."""

    key: str  # worksheet name (<= 31 chars, no []:*?/\\)
    title: str  # human heading
    headers: list
    rows: list = field(default_factory=list)


def parse_days(raw, default=DEFAULT_DAYS):
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def _dt(value):
    return value.strftime("%Y-%m-%d %H:%M:%S") if value else ""


def _room_name(obj):
    return obj.room.room_name if obj.room else "Unassigned"


def _category_name(item):
    return item.category.category_name if item.category else "Uncategorized"


def _status_label(item):
    return "Low Stock" if item.quantity <= item.min_quantity else "Available"


def _low_stock_items():
    return (
        Item.objects.select_related("category", "room")
        .filter(quantity__lte=F("min_quantity"))
        .order_by("item_name")
    )


def _all_items():
    return Item.objects.select_related("category", "room").order_by("item_name")


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------

def _summary_section(days, since):
    total_items = Item.objects.count()
    low = _low_stock_items().count()
    rows = [
        ["Report", "CSE Inventory Management System"],
        ["Generated", _dt(timezone.now())],
        ["Period", f"Last {days} days (since {since.strftime('%Y-%m-%d')})"],
        ["Total items", total_items],
        ["Low stock items", low],
        ["Items in stock", Item.objects.filter(quantity__gt=0).count()],
        ["Total units on hand", sum(i.quantity for i in Item.objects.all())],
        ["Stock transactions in period", StockTransaction.objects.filter(timestamp__gte=since).count()],
        ["Requisitions in period", Requisition.objects.filter(created_at__gte=since).count()],
    ]
    return Section("Summary", "SUMMARY", ["Metric", "Value"], rows)


def _low_stock_section():
    rows = [
        [
            item.item_name,
            _category_name(item),
            _room_name(item),
            item.quantity,
            item.min_quantity,
            item.min_quantity - item.quantity,
            item.unit,
        ]
        for item in _low_stock_items()
    ]
    return Section(
        "Low Stock",
        "LOW STOCK ALERTS",
        ["Item Name", "Category", "Room", "Current Stock", "Minimum Stock", "Shortage", "Unit"],
        rows,
    )


def _category_section():
    total_items = Item.objects.count()
    rows = []
    for row in (
        Item.objects.values("category__category_name")
        .annotate(count=Count("item_id"))
        .order_by("-count")
    ):
        count = row["count"]
        percent = round((count / total_items) * 100, 1) if total_items else 0
        rows.append([row["category__category_name"] or "Uncategorized", count, f"{percent}%"])
    return Section("By Category", "ITEMS BY CATEGORY", ["Category", "Count", "Percentage"], rows)


def _all_items_section():
    rows = [
        [
            item.item_name,
            _category_name(item),
            _room_name(item),
            item.quantity,
            item.unit,
            item.min_quantity,
            _status_label(item),
            _dt(getattr(item, "updated_at", None)),
        ]
        for item in _all_items()
    ]
    return Section(
        "All Items",
        "ALL ITEMS",
        ["Item Name", "Category", "Room", "Quantity", "Unit", "Min Quantity", "Status", "Updated At"],
        rows,
    )


def _room_snapshot_section():
    """Flat per-room listing - the tabular form of the room snapshot report."""
    rows = []
    for item in Item.objects.select_related("category", "room").order_by(
        "room__room_name", "item_name"
    ):
        room = item.room
        rows.append(
            [
                room.room_name if room else "Unassigned",
                room.room_type if room else "",
                room.location if room else "",
                item.item_name,
                _category_name(item),
                item.quantity,
                item.unit,
                item.min_quantity,
                _status_label(item),
            ]
        )
    return Section(
        "Room Snapshot",
        "ROOM INVENTORY SNAPSHOT",
        ["Room", "Room Type", "Location", "Item Name", "Category", "Quantity", "Unit", "Min Quantity", "Status"],
        rows,
    )


def _transactions_section(since):
    txns = (
        StockTransaction.objects.select_related("item", "item__room", "user")
        .filter(timestamp__gte=since)
        .order_by("-timestamp")[:ROW_LIMIT]
    )
    rows = [
        [
            tr.transaction_id,
            tr.item.item_name,
            _room_name(tr.item),
            tr.type,
            tr.quantity,
            tr.user.name if tr.user else "System",
            _dt(tr.timestamp),
            (tr.notes or "").replace("\n", " "),
        ]
        for tr in txns
    ]
    return Section(
        "Transactions",
        "STOCK TRANSACTIONS",
        ["Transaction ID", "Item", "Room", "Type", "Quantity", "User", "Timestamp", "Notes"],
        rows,
    )


def _requisitions_section(since):
    reqs = (
        Requisition.objects.select_related("user")
        .filter(created_at__gte=since)
        .order_by("-created_at")[:ROW_LIMIT]
    )
    rows = [
        [
            r.req_id,
            r.user.name if r.user else "",
            r.status,
            r.department or "",
            _dt(r.created_at),
            _dt(r.expected_return_at),
            _dt(r.returned_at),
            (r.purpose or "").replace("\n", " "),
        ]
        for r in reqs
    ]
    return Section(
        "Requisitions",
        "REQUISITIONS",
        ["Req ID", "User", "Status", "Department", "Created At", "Expected Return", "Returned At", "Purpose"],
        rows,
    )


def _requisition_items_section(since):
    req_items = (
        RequisitionItem.objects.select_related("requisition", "item")
        .filter(requisition__created_at__gte=since)
        .order_by("-req_item_id")[: ROW_LIMIT * 2]
    )
    rows = [
        [
            ri.requisition.req_id,
            ri.requisition.status,
            ri.item.item_name,
            ri.quantity,
            ri.issued_quantity,
            ri.outstanding_quantity,
        ]
        for ri in req_items
    ]
    return Section(
        "Requisition Items",
        "REQUISITION ITEMS",
        ["Req ID", "Req Status", "Item", "Requested", "Issued", "Outstanding"],
        rows,
    )


def _audit_section(since):
    logs = (
        AuditLog.objects.select_related("user")
        .filter(timestamp__gte=since)
        .order_by("-timestamp")[:ROW_LIMIT]
    )
    rows = [
        [log.log_id, log.user.name if log.user else "System", log.action, _dt(log.timestamp)]
        for log in logs
    ]
    return Section("Audit Log", "AUDIT LOG", ["Log ID", "User", "Action", "Timestamp"], rows)


def build_report(days=DEFAULT_DAYS):
    """The whole report, as ordered sections. Used by both exporters."""
    since = timezone.now() - timedelta(days=days)
    return [
        _summary_section(days, since),
        _low_stock_section(),
        _category_section(),
        _all_items_section(),
        _room_snapshot_section(),
        _transactions_section(since),
        _requisitions_section(since),
        _requisition_items_section(since),
        _audit_section(since),
    ]
