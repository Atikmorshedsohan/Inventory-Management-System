from django.urls import path

from . import views

urlpatterns = [
    path("reports/dashboard/", views.DashboardStatsView.as_view(), name="dashboard-stats"),
    path("reports/rooms-overview/", views.RoomOverviewView.as_view(), name="rooms-overview"),
    path("reports/roomwise-activity/", views.RoomwiseActivityView.as_view(), name="roomwise-activity"),
    path("reports/low-stock/", views.LowStockView.as_view(), name="reports-low-stock"),
    path("reports/stock-movement/", views.StockMovementView.as_view(), name="reports-stock-movement"),
    path("reports/room-snapshot/", views.RoomSnapshotView.as_view(), name="reports-room-snapshot"),
    path(
        "reports/room-snapshot/export/csv/",
        views.SnapshotExportCSVView.as_view(),
        name="reports-snapshot-csv",
    ),
    path(
        "reports/room-snapshot/export/excel/",
        views.SnapshotExportExcelView.as_view(),
        name="reports-snapshot-excel",
    ),
    path("reports/reconciliation/", views.ReconciliationView.as_view(), name="reports-reconciliation"),
    path(
        "reports/reconciliation/reconcile/",
        views.ReconcileItemView.as_view(),
        name="reports-reconcile-item",
    ),
    path("reports/export/csv/", views.ExportCSVView.as_view(), name="reports-export-csv"),
    path("reports/export/excel/", views.ExportExcelView.as_view(), name="reports-export-excel"),
]
