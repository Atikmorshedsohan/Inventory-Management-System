from rest_framework import viewsets

from common.permissions import NotViewerPermission, RolePermission

from .models import AuditLog
from .serializers import AuditLogSerializer


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only access to the audit trail."""

    queryset = AuditLog.objects.select_related("user").all()
    serializer_class = AuditLogSerializer
    permission_classes = [NotViewerPermission, RolePermission]
    filterset_fields = ["user"]
    search_fields = ["action"]
