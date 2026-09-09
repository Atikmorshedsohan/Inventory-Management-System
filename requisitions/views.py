from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from common.permissions import NotViewerPermission, RolePermission

from . import services
from .models import Requisition, RequisitionEvent, RequisitionItem
from .serializers import (
    RequisitionEventSerializer,
    RequisitionItemSerializer,
    RequisitionSerializer,
)

_ELEVATED = ("admin", "manager", "staff")


class RequisitionViewSet(viewsets.ModelViewSet):
    queryset = (
        Requisition.objects.select_related("user")
        .prefetch_related("items__item", "events__actor")
        .all()
    )
    serializer_class = RequisitionSerializer
    filterset_fields = ["status"]
    permission_classes = [NotViewerPermission, RolePermission]

    def perform_create(self, serializer):
        requisition = serializer.save(user=self.request.user)
        services.log_event(
            requisition, event_type="created", actor=self.request.user, to_status="pending"
        )
        services.notify_new_requisition(requisition)

    def _can_comment(self, request, requisition):
        return (
            requisition.user_id == request.user.pk
            or getattr(request.user, "role", "viewer") in _ELEVATED
        )

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        services.approve(requisition=self.get_object(), user=request.user)
        return Response({"status": "approved"})

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        reason = request.data.get("note") or request.data.get("reason") or ""
        services.reject(requisition=self.get_object(), user=request.user, reason=reason)
        return Response({"status": "rejected", "reason": reason})

    @action(detail=True, methods=["post"])
    def issue(self, request, pk=None):
        allow_partial = request.data.get("allow_partial", True)
        if isinstance(allow_partial, str):
            allow_partial = allow_partial.lower() not in ("false", "0", "no")
        req_item_ids = request.data.get("req_item_ids") or None
        result = services.issue(
            requisition=self.get_object(),
            user=request.user,
            allow_partial=bool(allow_partial),
            req_item_ids=req_item_ids,
        )
        return Response(result)

    @action(detail=True, methods=["post"], url_path="return")
    def mark_return(self, request, pk=None):
        services.mark_returned(requisition=self.get_object(), user=request.user)
        return Response({"status": "returned"})

    @action(detail=True, methods=["post"])
    def comment(self, request, pk=None):
        requisition = self.get_object()
        if not self._can_comment(request, requisition):
            return Response(
                {"detail": "You can only comment on your own requisitions."},
                status=status.HTTP_403_FORBIDDEN,
            )
        event = services.add_comment(
            requisition=requisition, user=request.user, note=request.data.get("note", "")
        )
        return Response(
            RequisitionEventSerializer(event).data, status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=["get"])
    def timeline(self, request, pk=None):
        events = self.get_object().events.select_related("actor").all()
        return Response(RequisitionEventSerializer(events, many=True).data)


class RequisitionItemViewSet(viewsets.ModelViewSet):
    queryset = RequisitionItem.objects.select_related("requisition", "item").all()
    serializer_class = RequisitionItemSerializer
    permission_classes = [RolePermission]
