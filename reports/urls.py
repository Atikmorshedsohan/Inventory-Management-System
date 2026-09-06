from django.urls import path
from .views import (
    DashboardStatsView,
    InventoryReportView,
    PurchaseReportView,
    RequisitionReportView
)

urlpatterns = [
    path('dashboard/', DashboardStatsView.as_view(), name='dashboard-stats'),
    path('inventory/', InventoryReportView.as_view(), name='inventory-report'),
    path('purchases/', PurchaseReportView.as_view(), name='purchase-report'),
    path('requisitions/', RequisitionReportView.as_view(), name='requisition-report'),
]
