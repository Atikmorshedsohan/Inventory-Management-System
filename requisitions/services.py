"""Requisition lifecycle: approve -> reject / issue -> return."""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from audit.services import record as audit_record
from common.exceptions import DomainError
from stock.models import StockTransaction


def _actor(user):
    return user if (user and user.is_authenticated) else None


def approve(*, requisition, user):
    if requisition.status != "pending":
        raise DomainError("Only pending requisitions can be approved.")
    requisition.status = "approved"
    requisition.save(update_fields=["status"])
    audit_record(_actor(user), f"Approved requisition #{requisition.req_id}")
    return requisition


def reject(*, requisition, user):
    if requisition.status not in ("pending", "approved"):
        raise DomainError("Only pending/approved requisitions can be rejected.")
    requisition.status = "rejected"
    requisition.save(update_fields=["status"])
    audit_record(_actor(user), f"Rejected requisition #{requisition.req_id}")
    return requisition


def issue(*, requisition, user):
    if requisition.status != "approved":
        raise DomainError("Only approved requisitions can be issued.")

    actor = _actor(user)
    shortage = None
    with transaction.atomic():
        for req_item in requisition.items.select_related("item").all():
            item = req_item.item
            if item.quantity < req_item.quantity:
                shortage = f"Insufficient stock for {item.item_name}"
                break
            item.quantity -= req_item.quantity
            item.save(update_fields=["quantity"])
            StockTransaction.objects.create(
                item=item,
                type="OUT",
                quantity=req_item.quantity,
                user=actor,
                notes=f"Issued for requisition #{requisition.req_id}",
            )
        if shortage is None:
            requisition.status = "issued"
            requisition.expected_return_at = timezone.now() + timedelta(
                days=requisition.return_duration_days or 0
            )
            requisition.save(update_fields=["status", "expected_return_at"])
            audit_record(actor, f"Issued requisition #{requisition.req_id}")

    if shortage:
        # Matches the original: partially-issued rows stay committed, 400 is returned.
        raise DomainError(shortage)
    return requisition


def mark_returned(*, requisition, user):
    if requisition.status != "issued":
        raise DomainError("Only issued requisitions can be returned.")
    requisition.status = "returned"
    requisition.returned_at = timezone.now()
    requisition.save(update_fields=["status", "returned_at"])
    audit_record(_actor(user), f"Returned requisition #{requisition.req_id}")
    return requisition
