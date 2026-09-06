from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

router = DefaultRouter()
router.register(r'users', views.UserViewSet)
router.register(r'categories', views.CategoryViewSet)
router.register(r'items', views.ItemViewSet)
router.register(r'rooms', views.RoomViewSet)
router.register(r'room-item-history', views.RoomItemHistoryViewSet)
router.register(r'requisitions', views.RequisitionViewSet)
router.register(r'requisition-items', views.RequisitionItemViewSet)
router.register(r'stock-transactions', views.StockTransactionViewSet)
router.register(r'pending-stock-transactions', views.PendingStockTransactionViewSet)
router.register(r'pending-items', views.PendingItemViewSet)
router.register(r'audit-logs', views.AuditLogViewSet)
router.register(r'room-keys', views.RoomKeyViewSet)
router.register(r'key-audit-logs', views.KeyAuditLogViewSet)
router.register(r'key-borrows', views.KeyBorrowViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('reports/dashboard/', views.DashboardStatsView.as_view(), name='dashboard-stats'),
    path('reports/rooms-overview/', views.RoomOverviewView.as_view(), name='rooms-overview'),
    path('reports/roomwise-activity/', views.RoomwiseActivityView.as_view(), name='roomwise-activity'),
    path('reports/export/csv/', views.ExportCSVView.as_view(), name='reports-export-csv'),
    path('reports/export/excel/', views.ExportExcelView.as_view(), name='reports-export-excel'),
    # Auth (JWT)
    path('auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/register/', views.RegisterView.as_view(), name='register'),
    path('auth/me/', views.current_user, name='current_user'),
    path('auth/password-reset/', views.PasswordResetRequestView.as_view(), name='password_reset_request'),
    path('auth/password-reset/confirm/', views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
]
