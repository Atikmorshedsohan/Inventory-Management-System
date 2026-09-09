from django.urls import path

from . import views

urlpatterns = [
    path("stock/transfer/", views.ItemTransferView.as_view(), name="stock-transfer"),
    path("stock/bulk-import/", views.BulkStockImportView.as_view(), name="stock-bulk-import"),
]
