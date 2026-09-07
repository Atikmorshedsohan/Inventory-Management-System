from django.urls import path

from . import views

urlpatterns = [
    path("reports/dashboard/", views.DashboardStatsView.as_view(), name="dashboard-stats"),
    path("reports/rooms-overview/", views.RoomOverviewView.as_view(), name="rooms-overview"),
    path("reports/roomwise-activity/", views.RoomwiseActivityView.as_view(), name="roomwise-activity"),
    path("reports/export/csv/", views.ExportCSVView.as_view(), name="reports-export-csv"),
    path("reports/export/excel/", views.ExportExcelView.as_view(), name="reports-export-excel"),
]
