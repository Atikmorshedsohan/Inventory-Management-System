"""Requisition lifecycle: approve -> reject / issue (full or partial) -> return.

Every transition and every comment is recorded on ``RequisitionEvent`` so the
UI can show a full history timeline.
"""

from datetime import timedelta

from django.db import models, transaction
from django.utils import timezone

from audit.services import record as audit_record
from common.exceptions import DomainError
from stock.models import StockTransaction

from .models import RequisitionEvent


def _actor(user):
    return user if (user and user.is_authenticated) else None


def _sync_reorder_alert(item):
    """Best-effort reorder-alert refresh after an item's quantity drops."""
    try:
        from catalog.services import sync_reorder_alert

        sync_reorder_alert(item)
    except Exception as exc:  # noqa: BLE001 - alerts must not block issuing
        print(f"Reorder alert sync failed for item {getattr(item, 'pk', '?')}: {exc}")


def _notify_requester(requisition, *, title, message, level="info"):
    """Best-effort in-app notification to the person who raised the requisition."""
    try:
        from notifications.services import safe_notify

        safe_notify(
            recipient=requisition.user,
            title=title,
            message=message,
            level=level,
            category="general",
            link="/requisitions/",
        )
    except Exception as exc:  # noqa: BLE001 - notifications are best-effort
        print(f"Notification dispatch failed: {exc}")


def notify_new_requisition(requisition):
    """Tell admins / managers a fresh requisition is waiting for a decision."""
    try:
        from notifications.services import role_recipients, safe_broadcast

        item_count = requisition.items.count()
        safe_broadcast(
            recipients=role_recipients("admin", "manager", exclude=requisition.user),
            title=f"New requisition #{requisition.req_id} from {getattr(requisition.user, 'name', 'a user')}",
            message=f"{item_count} item line(s) - purpose: {requisition.purpose or 'n/a'}. "
                    "Pending approval.",
            level="warning",
            category="general",
            link="/requisitions/",
        )
    except Exception as exc:  # noqa: BLE001 - notifications are best-effort
        print(f"Notification dispatch failed: {exc}")


def log_event(requisition, *, event_type, actor, from_status="", to_status="", note="", metadata=None):
    """Append one row to the requisition's history timeline."""
    return RequisitionEvent.objects.create(
        requisition=requisition,
        event_type=event_type,
        actor=_actor(actor),
        from_status=from_status or "",
        to_status=to_status or "",
        note=note or "",
        metadata=metadata or {},
    )


def approve(*, requisition, user):
    if requisition.status != "pending":
        raise DomainError("Only pending requisitions can be approved.")
    prev = requisition.status
    requisition.status = "approved"
    requisition.save(update_fields=["status"])
    log_event(requisition, event_type="approved", actor=user, from_status=prev, to_status="approved")
    audit_record(_actor(user), f"Approved requisition #{requisition.req_id}")
    _notify_requester(
        requisition,
        title=f"Requisition #{requisition.req_id} approved",
        message="Your requisition was approved and is ready to be issued.",
        level="success",
    )
    return requisition


def reject(*, requisition, user, reason=""):
    if requisition.status not in ("pending", "approved"):
        raise DomainError("Only pending/approved requisitions can be rejected.")
    prev = requisition.status
    requisition.status = "rejected"
    requisition.save(update_fields=["status"])
    log_event(
        requisition,
        event_type="rejected",
        actor=user,
        from_status=prev,
        to_status="rejected",
        note=reason or "",
    )
    suffix = f". Reason: {reason}" if reason else ""
    audit_record(_actor(user), f"Rejected requisition #{requisition.req_id}{suffix}")
    _notify_requester(
        requisition,
        title=f"Requisition #{requisition.req_id} rejected",
        message="Your requisition was rejected" + (f". Reason: {reason}" if reason else "."),
        level="danger",
    )
    return requisition


def add_comment(*, requisition, user, note):
    note = (note or "").strip()
    if not note:
        raise DomainError("A comment cannot be empty.")
    event = log_event(requisition, event_type="comment", actor=user, note=note)
    audit_record(_actor(user), f"Commented on requisition #{requisition.req_id}")
    return event


@transaction.atomic
def issue(*, requisition, user, allow_partial=True, req_item_ids=None):
    """Hand out stock for a requisition.

    * ``allow_partial=True`` (default): give whatever is in stock right now.
      Lines that are only part-filled leave the rest outstanding and the
      requisition moves to ``partially_issued``; a later ``issue`` call picks up
      where this one left off. When every line is fully satisfied the status
      becomes ``issued``.
    * ``allow_partial=False``: only issue lines that can be filled completely.
    * ``req_item_ids``: restrict this round to specific requisition-item rows.
    """
    if requisition.status not in ("approved", "partially_issued"):
        raise DomainError("Only approved or partially-issued requisitions can be issued.")

    actor = _actor(user)
    selected = set(req_item_ids) if req_item_ids else None

    issued_now = []
    shortfalls = []

    for ri in requisition.items.select_related("item"):
        if selected is not None and ri.req_item_id not in selected:
            continue

        outstanding = ri.quantity - ri.issued_quantity
        if outstanding <= 0:
            continue

        available = ri.item.quantity
        give = min(outstanding, available)

        if give <= 0:
            shortfalls.append({"item": ri.item.item_name, "requested": outstanding, "issued": 0})
            continue
        if give < outstanding and not allow_partial:
            shortfalls.append(
                {"item": ri.item.item_name, "requested": outstanding, "issued": 0, "reason": "partial not allowed"}
            )
            continue

        ri.item.quantity -= give
        ri.item.save(update_fields=["quantity"])
        ri.issued_quantity += give
        ri.save(update_fields=["issued_quantity"])

        partial = give < outstanding
        StockTransaction.objects.create(
            item=ri.item,
            type="OUT",
            quantity=give,
            user=actor,
            notes=f"Issued for requisition #{requisition.req_id}" + (" (partial)" if partial else ""),
        )
        _sync_reorder_alert(ri.item)

        issued_now.append({"item": ri.item.item_name, "issued": give, "requested": outstanding})
        if partial:
            shortfalls.append(
                {"item": ri.item.item_name, "requested": outstanding, "issued": give,
                 "remaining": outstanding - give}
            )

    if not issued_now:
        raise DomainError(
            "Nothing could be issued - none of the outstanding items are in stock."
        )

    # Fresh query (``.filter`` bypasses any prefetch cache on ``requisition``).
    still_outstanding = requisition.items.filter(
        issued_quantity__lt=models.F("quantity")
    ).exists()
    fully_done = not still_outstanding
    prev = requisition.status

    update_fields = ["status"]
    if fully_done:
        requisition.status = "issued"
    else:
        requisition.status = "partially_issued"
    if not requisition.expected_return_at:
        requisition.expected_return_at = timezone.now() + timedelta(
            days=requisition.return_duration_days or 0
        )
        update_fields.append("expected_return_at")
    requisition.save(update_fields=update_fields)

    event_type = "issued" if fully_done else "partially_issued"
    log_event(
        requisition,
        event_type=event_type,
        actor=user,
        from_status=prev,
        to_status=requisition.status,
        note=_issue_summary(issued_now, shortfalls),
        metadata={"issued": issued_now, "shortfalls": shortfalls},
    )
    audit_record(
        actor,
        f"{'Issued' if fully_done else 'Partially issued'} requisition #{requisition.req_id}",
    )
    _notify_requester(
        requisition,
        title=f"Requisition #{requisition.req_id} "
              f"{'issued' if fully_done else 'partially issued'}",
        message=_issue_summary(issued_now, shortfalls) or "Items issued.",
        level="success" if fully_done else "warning",
    )
    return {
        "status": requisition.status,
        "fully_issued": fully_done,
        "issued": issued_now,
        "shortfalls": shortfalls,
    }


def _issue_summary(issued_now, shortfalls):
    parts = [f"Issued {r['issued']}× {r['item']}" for r in issued_now]
    for s in shortfalls:
        if s.get("remaining"):
            parts.append(f"{s['item']}: {s['remaining']} still outstanding")
        elif s.get("issued", 0) == 0:
            parts.append(f"{s['item']}: out of stock, nothing issued")
    return "; ".join(parts)


def mark_returned(*, requisition, user):
    if requisition.status not in ("issued", "partially_issued"):
        raise DomainError("Only issued or partially-issued requisitions can be returned.")
    prev = requisition.status
    requisition.status = "returned"
    requisition.returned_at = timezone.now()
    requisition.save(update_fields=["status", "returned_at"])
    log_event(requisition, event_type="returned", actor=user, from_status=prev, to_status="returned")
    audit_record(_actor(user), f"Returned requisition #{requisition.req_id}")
    return requisition
