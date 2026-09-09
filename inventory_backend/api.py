"""Single composition point for the REST API.

Every domain app contributes its view sets here so the public URL layout
(``/api/items/``, ``/api/room-keys/`` ...) stays in one obvious place.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from accounts.views import LoginEventViewSet, UserViewSet
from audit.views import AuditLogViewSet
from catalog.views import CategoryViewSet, ItemViewSet, PendingItemViewSet, RoomViewSet
from keys.views import KeyAuditLogViewSet, KeyBorrowViewSet, RoomKeyViewSet
from notifications.views import NotificationViewSet
from requisitions.views import RequisitionItemViewSet, RequisitionViewSet
from stock.views import (
    PendingStockTransactionViewSet,
    StockTransactionViewSet,
)

router = DefaultRouter()
router.register(r"users", UserViewSet)
router.register(r"login-events", LoginEventViewSet)
router.register(r"categories", CategoryViewSet)
router.register(r"items", ItemViewSet)
router.register(r"rooms", RoomViewSet)
router.register(r"requisitions", RequisitionViewSet)
router.register(r"requisition-items", RequisitionItemViewSet)
router.register(r"stock-transactions", StockTransactionViewSet)
router.register(r"pending-stock-transactions", PendingStockTransactionViewSet)
router.register(r"pending-items", PendingItemViewSet)
router.register(r"audit-logs", AuditLogViewSet)
router.register(r"notifications", NotificationViewSet, basename="notification")
router.register(r"room-keys", RoomKeyViewSet)
router.register(r"key-audit-logs", KeyAuditLogViewSet)
router.register(r"key-borrows", KeyBorrowViewSet)

urlpatterns = [
    path("", include("accounts.urls")),
    path("", include("reports.urls")),
    path("", include(router.urls)),
]
