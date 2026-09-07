from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from common.permissions import NotViewerPermission, RolePermission

from . import services
from .models import Requisition, RequisitionItem
from .serializers import RequisitionItemSerializer, RequisitionSerializer


class RequisitionViewSet(viewsets.ModelViewSet):
    queryset = Requisition.objects.select_related("user").prefetch_related("items").all()
    serializer_class = RequisitionSerializer
    filterset_fields = ["status"]
    permission_classes = [NotViewerPermission, RolePermission]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        services.approve(requisition=self.get_object(), user=request.user)
        return Response({"status": "approved"})

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        services.reject(requisition=self.get_object(), user=request.user)
        return Response({"status": "rejected"})

    @action(detail=True, methods=["post"])
    def issue(self, request, pk=None):
        services.issue(requisition=self.get_object(), user=request.user)
        return Response({"status": "issued"})

    @action(detail=True, methods=["post"], url_path="return")
    def mark_return(self, request, pk=None):
        services.mark_returned(requisition=self.get_object(), user=request.user)
        return Response({"status": "returned"})


class RequisitionItemViewSet(viewsets.ModelViewSet):
    queryset = RequisitionItem.objects.select_related("requisition", "item").all()
    serializer_class = RequisitionItemSerializer
    permission_classes = [RolePermission]
