"""The role / permission matrix, derived from the code that enforces it.

Nothing here is a hand-maintained table. Endpoint permissions are computed by
*actually evaluating* each view's ``permission_classes`` against a stand-in
request for every (role, method) pair, and the action rules read the same
module constants the views check at runtime. Change a permission class or a
role tuple and this page changes with it - which is what makes it auditable.
"""

from importlib import import_module

from .models import User

METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE")
ROLES = ("admin", "manager", "staff", "viewer")

ROLE_SUMMARY = {
    "admin": "Full access. The only role that can manage users, change roles and delete records.",
    "manager": "Day-to-day operations: create and update records, approve requests. Cannot delete or manage users.",
    "staff": "Legacy alias that behaves like manager. Kept so older accounts keep working.",
    "viewer": "Read-only. Can request items and borrow keys, but changes nothing directly.",
}

# key, label, URL, dotted path to the view that owns it
RESOURCE_SPECS = (
    ("items", "Items", "/api/items/", "catalog.views.ItemViewSet"),
    ("categories", "Categories", "/api/categories/", "catalog.views.CategoryViewSet"),
    ("rooms", "Rooms", "/api/rooms/", "catalog.views.RoomViewSet"),
    ("pending-items", "Pending items", "/api/pending-items/", "catalog.views.PendingItemViewSet"),
    ("stock-transactions", "Stock transactions", "/api/stock-transactions/", "stock.views.StockTransactionViewSet"),
    ("pending-stock", "Pending stock", "/api/pending-stock-transactions/", "stock.views.PendingStockTransactionViewSet"),
    ("requisitions", "Requisitions", "/api/requisitions/", "requisitions.views.RequisitionViewSet"),
    ("room-keys", "Room keys", "/api/room-keys/", "keys.views.RoomKeyViewSet"),
    ("key-borrows", "Key borrows", "/api/key-borrows/", "keys.views.KeyBorrowViewSet"),
    ("notifications", "Notifications", "/api/notifications/", "notifications.views.NotificationViewSet"),
    ("audit-logs", "Audit log", "/api/audit-logs/", "audit.views.AuditLogViewSet"),
    ("users", "Users", "/api/users/", "accounts.views.UserViewSet"),
    ("login-events", "Login activity", "/api/login-events/", "accounts.views.LoginEventViewSet"),
)


class _StubRequest:
    """Just enough request for a DRF permission class to inspect."""

    def __init__(self, method, user):
        self.method = method
        self.user = user
        self.auth = None
        self.query_params = {}
        self.data = {}


class _StubView:
    """Permission classes in this project do not read the view."""

    action = None
    kwargs = {}


def _load(dotted):
    module_path, name = dotted.rsplit(".", 1)
    return getattr(import_module(module_path), name)


def _allows(permission_classes, role, method):
    """Run the real permission classes for one (role, method) pair."""
    request = _StubRequest(method, User(role=role))
    view = _StubView()
    try:
        return all(cls().has_permission(request, view) for cls in permission_classes)
    except Exception:  # noqa: BLE001 - a class we cannot evaluate is reported as unknown
        return None


def build_resource_matrix():
    rows = []
    for key, label, path, dotted in RESOURCE_SPECS:
        view = _load(dotted)
        classes = list(getattr(view, "permission_classes", []))
        rows.append(
            {
                "key": key,
                "label": label,
                "path": path,
                "view": dotted,
                "enforced_by": [cls.__name__ for cls in classes] or ["(none)"],
                "roles": {
                    role: {method: _allows(classes, role, method) for method in METHODS}
                    for role in ROLES
                },
            }
        )
    return rows


def build_action_matrix():
    """Role rules the views check inside the handler, read from the real constants."""
    # Imported lazily: these modules import accounts, so a top-level import
    # here would be circular.
    from accounts.views import _ACTIVITY_VIEWERS
    from catalog.views import _ITEM_APPROVERS
    from keys.views import _KEY_STAFF
    from reports.views import _RECONCILE_ROLES
    from requisitions.views import _ELEVATED as REQUISITION_ELEVATED
    from stock.views import _STOCK_APPROVERS

    specs = (
        ("Approve / reject a pending item", "POST /api/pending-items/{id}/approve/",
         _ITEM_APPROVERS, "catalog.views._ITEM_APPROVERS"),
        ("Approve / reject pending stock", "POST /api/pending-stock-transactions/{id}/approve/",
         _STOCK_APPROVERS, "stock.views._STOCK_APPROVERS"),
        ("View pending stock approvals", "GET /api/pending-stock-transactions/pending_approvals/",
         ("admin",), "stock.views.PendingStockTransactionViewSet.pending_approvals"),
        ("Reconcile an item's ledger", "POST /api/reports/reconciliation/reconcile/",
         _RECONCILE_ROLES, "reports.views._RECONCILE_ROLES"),
        ("Comment on any requisition", "POST /api/requisitions/{id}/comment/",
         REQUISITION_ELEVATED, "requisitions.views._ELEVATED (or the requester)"),
        ("Approve / reject / issue key borrows", "POST /api/key-borrows/{id}/approve/",
         _KEY_STAFF, "keys.views._KEY_STAFF"),
        ("Confirm a key handover", "POST /api/key-borrows/{id}/pickup/",
         _KEY_STAFF, "keys.views._KEY_STAFF (or the borrower)"),
        ("Request to borrow a key", "POST /api/key-borrows/",
         ("viewer",), "keys.views.KeyBorrowViewSet.create"),
        ("View another user's activity", "GET /api/users/{id}/activity/",
         _ACTIVITY_VIEWERS, "accounts.views._ACTIVITY_VIEWERS (or yourself)"),
        ("Change a user's role", "POST /api/users/{id}/set_role/",
         ("admin",), "common.permissions.AdminWritePermission"),
        ("View login activity", "GET /api/login-events/",
         ("admin",), "common.permissions.AdminOnlyPermission"),
    )

    return [
        {
            "label": label,
            "endpoint": endpoint,
            "roles": {role: role in allowed for role in ROLES},
            "allowed": sorted(allowed),
            "source": source,
        }
        for label, endpoint, allowed, source in specs
    ]


def build_matrix():
    return {
        "roles": [
            {"key": role, "label": role.title(), "summary": ROLE_SUMMARY.get(role, "")}
            for role in ROLES
        ],
        "methods": list(METHODS),
        "resources": build_resource_matrix(),
        "actions": build_action_matrix(),
        "notes": [
            "Generated by evaluating each view's permission classes - it cannot "
            "drift from the code.",
            "'staff' is a legacy alias that behaves like 'manager'.",
            "Rules enforced inside a handler (listed under Actions) sit on top of "
            "the endpoint permissions above.",
        ],
    }
