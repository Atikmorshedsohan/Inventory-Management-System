"""Write actions for the reports domain (currently: reconciliation fixes)."""

from django.db import transaction
from django.db.models import Q, Sum

from audit.services import record as audit_record
from catalog.models import Item
from common.exceptions import DomainError
from stock.models import StockTransaction


@transaction.atomic
def reconcile_item(*, item_id, user):
    """Post an ``ADJUST`` transaction so the ledger matches the item's balance.

    Used when the reconciliation report shows a discrepancy that the admin has
    verified against a physical count: the counted quantity is trusted and the
    ledger is corrected to agree with it. The item's ``quantity`` is unchanged.
    """
    try:
        item = Item.objects.select_for_update().get(pk=item_id)
    except Item.DoesNotExist:
        raise DomainError("Item not found.", status_code=404)

    agg = StockTransaction.objects.filter(item=item).aggregate(
        total_in=Sum("quantity", filter=Q(type="IN")),
        total_out=Sum("quantity", filter=Q(type="OUT")),
        total_adjust=Sum("quantity", filter=Q(type="ADJUST")),
    )
    expected = (
        (item.opening_quantity or 0)
        + (agg["total_in"] or 0)
        - (agg["total_out"] or 0)
        + (agg["total_adjust"] or 0)
    )
    discrepancy = item.quantity - expected
    if discrepancy == 0:
        raise DomainError(f"'{item.item_name}' is already balanced.")

    actor = user if (user and getattr(user, "is_authenticated", False)) else None
    StockTransaction.objects.create(
        item=item,
        type="ADJUST",
        quantity=discrepancy,
        user=actor,
        notes="Reconciliation adjustment: ledger aligned to the counted balance.",
    )
    audit_record(
        actor,
        f"Reconciled '{item.item_name}': ledger adjusted by {discrepancy:+d} "
        f"to match balance of {item.quantity}",
    )
    return {
        "item_id": item.item_id,
        "item_name": item.item_name,
        "adjustment": discrepancy,
        "system_quantity": item.quantity,
        "expected_quantity": item.quantity,
        "status": "balanced",
    }
