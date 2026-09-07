"""CSV / Excel report builders. Kept separate from the views so the
file-format details don't clutter the request handlers.
"""

import csv
from datetime import timedelta
from io import BytesIO

from django.db.models import Count, F
from django.http import HttpResponse
from django.utils import timezone

from catalog.models import Item
from requisitions.models import Requisition, RequisitionItem
from stock.models import StockTransaction

DEFAULT_DAYS = 90


def parse_days(raw, default=DEFAULT_DAYS):
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def _low_stock_items():
    return Item.objects.select_related("category").filter(
        quantity__lte=F("min_quantity")
    ).order_by("item_name")


def _all_items():
    return Item.objects.select_related("category").order_by("item_name")


def _status_label(item):
    return "Low Stock" if item.quantity <= item.min_quantity else "Available"


def build_csv(days=DEFAULT_DAYS):
    since = timezone.now() - timedelta(days=days)
    response = HttpResponse(content_type="text/csv")
    stamp = timezone.now().strftime("%Y-%m-%d")
    response["Content-Disposition"] = f'attachment; filename="CSE_Inventory_Report_{stamp}.csv"'
    writer = csv.writer(response)

    writer.writerow(["CSE Inventory Management System - Report"])
    writer.writerow([f'Generated: {timezone.now().strftime("%Y-%m-%d %H:%M:%S")}'])
    writer.writerow([f"Period: last {days} days"])
    writer.writerow([])

    writer.writerow(["LOW STOCK ALERTS"])
    writer.writerow(["Item Name", "Current Stock", "Minimum Stock", "Shortage", "Category"])
    for item in _low_stock_items():
        writer.writerow([
            item.item_name, item.quantity, item.min_quantity,
            item.min_quantity - item.quantity,
            item.category.category_name if item.category else "",
        ])
    writer.writerow([])

    writer.writerow(["ITEMS BY CATEGORY"])
    writer.writerow(["Category", "Count", "Percentage"])
    total_items = Item.objects.count()
    cat_rows = (
        Item.objects.values("category__category_name")
        .annotate(count=Count("item_id"))
        .order_by("-count")
    )
    for row in cat_rows:
        count = row["count"]
        percent = f"{round((count / total_items) * 100, 1) if total_items else 0}%"
        writer.writerow([row["category__category_name"] or "Uncategorized", count, percent])
    writer.writerow([])

    writer.writerow(["ALL ITEMS"])
    writer.writerow(["Item Name", "Category", "Quantity", "Unit", "Min Quantity", "Status", "Updated At"])
    for item in _all_items():
        updated = getattr(item, "updated_at", None)
        writer.writerow([
            item.item_name,
            item.category.category_name if item.category else "N/A",
            item.quantity, item.unit, item.min_quantity, _status_label(item),
            updated.strftime("%Y-%m-%d %H:%M:%S") if updated else "",
        ])
    writer.writerow([])

    writer.writerow(["STOCK TRANSACTIONS (Recent)"])
    writer.writerow(["Transaction ID", "Item", "Type", "Quantity", "User", "Timestamp", "Notes"])
    txns = (
        StockTransaction.objects.select_related("item", "user")
        .filter(timestamp__gte=since)
        .order_by("-timestamp")[:500]
    )
    for tr in txns:
        writer.writerow([
            tr.transaction_id, tr.item.item_name, tr.type, tr.quantity,
            tr.user.name if tr.user else "",
            tr.timestamp.strftime("%Y-%m-%d %H:%M:%S"), tr.notes or "",
        ])
    writer.writerow([])

    writer.writerow(["REQUISITIONS (Recent)"])
    writer.writerow(["Req ID", "User", "Status", "Created At", "Purpose"])
    reqs = (
        Requisition.objects.select_related("user")
        .filter(created_at__gte=since)
        .order_by("-created_at")[:500]
    )
    for r in reqs:
        writer.writerow([
            r.req_id, r.user.name, r.status,
            r.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            (r.purpose or "").replace("\n", " "),
        ])
    writer.writerow([])

    writer.writerow(["REQUISITION ITEMS (Recent)"])
    writer.writerow(["Req ID", "Item", "Quantity"])
    req_items = (
        RequisitionItem.objects.select_related("requisition", "item")
        .filter(requisition__created_at__gte=since)
        .order_by("-req_item_id")[:1000]
    )
    for ri in req_items:
        writer.writerow([ri.requisition.req_id, ri.item.item_name, ri.quantity])

    return response


def build_excel(days=DEFAULT_DAYS):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    since = timezone.now() - timedelta(days=days)
    wb = Workbook()
    header_fill = PatternFill(start_color="0066CC", end_color="0066CC", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=12)

    def header_row(ws):
        for cell in ws[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center")

    ws_summary = wb.active
    ws_summary.title = "Summary"
    ws_summary["A1"] = "CSE Inventory Management System - Report"
    ws_summary["A1"].font = Font(bold=True, size=14)
    ws_summary["A2"] = f'Generated: {timezone.now().strftime("%Y-%m-%d %H:%M:%S")}'
    ws_summary["A3"] = f"Period: last {days} days"

    ws_low = wb.create_sheet("Low Stock")
    ws_low.append(["Item Name", "Current Stock", "Minimum Stock", "Shortage", "Category"])
    header_row(ws_low)
    for item in _low_stock_items():
        ws_low.append([
            item.item_name, item.quantity, item.min_quantity,
            item.min_quantity - item.quantity,
            item.category.category_name if item.category else "",
        ])

    ws_items = wb.create_sheet("All Items")
    ws_items.append(["Item Name", "Category", "Quantity", "Unit", "Min Quantity", "Status", "Updated At"])
    header_row(ws_items)
    for item in _all_items():
        updated = getattr(item, "updated_at", None)
        ws_items.append([
            item.item_name,
            item.category.category_name if item.category else "N/A",
            item.quantity, item.unit, item.min_quantity, _status_label(item),
            updated.strftime("%Y-%m-%d %H:%M:%S") if updated else "",
        ])

    ws_trans = wb.create_sheet("Transactions")
    ws_trans.append(["Transaction ID", "Item", "Type", "Quantity", "User", "Timestamp", "Notes"])
    header_row(ws_trans)
    txns = (
        StockTransaction.objects.select_related("item", "user")
        .filter(timestamp__gte=since)
        .order_by("-timestamp")[:500]
    )
    for tr in txns:
        ws_trans.append([
            tr.transaction_id, tr.item.item_name, tr.type, tr.quantity,
            tr.user.name if tr.user else "",
            tr.timestamp.strftime("%Y-%m-%d %H:%M:%S"), tr.notes or "",
        ])

    ws_req = wb.create_sheet("Requisitions")
    ws_req.append(["Req ID", "User", "Status", "Created At", "Purpose"])
    header_row(ws_req)
    reqs = (
        Requisition.objects.select_related("user")
        .filter(created_at__gte=since)
        .order_by("-created_at")[:500]
    )
    for r in reqs:
        ws_req.append([
            r.req_id, r.user.name, r.status,
            r.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            (r.purpose or "").replace("\n", " "),
        ])

    for ws in (ws_summary, ws_low, ws_items, ws_trans, ws_req):
        for column in ws.columns:
            longest = 0
            letter = column[0].column_letter
            for cell in column:
                try:
                    longest = max(longest, len(str(cell.value)))
                except Exception:
                    pass
            ws.column_dimensions[letter].width = min(longest + 2, 50)

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    stamp = timezone.now().strftime("%Y-%m-%d")
    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="CSE_Inventory_Report_{stamp}.xlsx"'
    return response
