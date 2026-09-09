"""Filtering for the audit trail.

``AuditLog.action`` is free text, so "action type" is derived by matching
keywords rather than stored as a column. The mapping lives here so the API and
the UI agree on the categories.
"""

from functools import reduce
from operator import or_

import django_filters
from django.db.models import Q

from .models import AuditLog

# Ordered: the first pattern that matches wins when classifying a single row.
ACTION_TYPES = (
    ("stock", "Stock movement", ["stock in", "stock out", "stock adjust", "bulk stock"]),
    ("transfer", "Transfer", ["transferred", "moved '"]),
    ("reconcile", "Reconciliation", ["reconciled"]),
    ("role", "Role change", ["changed role"]),
    ("approve", "Approval", ["approved"]),
    ("reject", "Rejection", ["rejected"]),
    ("issue", "Issued", ["issued", "partially issued"]),
    ("return", "Returned", ["returned"]),
    ("create", "Created", ["created", "submitted"]),
    ("comment", "Comment", ["commented"]),
    ("auth", "Account", ["password reset", "registered", "logged"]),
    ("update", "Updated", ["updated"]),
    ("delete", "Deleted", ["deleted"]),
)

# "other" is a real, selectable bucket: everything no pattern claimed.
ACTION_TYPE_CHOICES = [(key, label) for key, label, _ in ACTION_TYPES] + [("other", "Other")]
_PATTERNS = {key: patterns for key, _, patterns in ACTION_TYPES}


def classify(action):
    """Return the action-type key for one free-text action string."""
    lowered = (action or "").lower()
    for key, _label, patterns in ACTION_TYPES:
        if any(p in lowered for p in patterns):
            return key
    return "other"


def _patterns_q(patterns):
    return reduce(or_, (Q(action__icontains=p) for p in patterns))


def _any_pattern_q():
    return reduce(or_, (_patterns_q(p) for _k, _l, p in ACTION_TYPES))


def action_type_q(key):
    """A ``Q`` selecting exactly the rows that :func:`classify` puts in ``key``.

    ``classify`` takes the *first* matching category, so an action like
    "Approved and created item" is an approval, not a creation. The filter has
    to exclude the higher-priority categories the same way, otherwise picking
    "create" would return rows the UI badges as "approve" - and the per-category
    counts would add up to more than the number of rows.
    """
    if key == "other":
        return ~_any_pattern_q()

    higher = Q()
    for candidate, _label, patterns in ACTION_TYPES:
        own = _patterns_q(patterns)
        if candidate == key:
            return own & ~higher if higher else own
        higher |= own
    return Q()


class AuditLogFilter(django_filters.FilterSet):
    """?user=3&action_type=stock&date_from=2026-09-01&date_to=2026-09-08"""

    user = django_filters.NumberFilter(field_name="user__user_id")
    action_type = django_filters.ChoiceFilter(
        choices=ACTION_TYPE_CHOICES, method="filter_action_type"
    )
    date_from = django_filters.DateFilter(field_name="timestamp", lookup_expr="date__gte")
    date_to = django_filters.DateFilter(field_name="timestamp", lookup_expr="date__lte")

    class Meta:
        model = AuditLog
        fields = ["user", "action_type", "date_from", "date_to"]

    def filter_action_type(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(action_type_q(value))
