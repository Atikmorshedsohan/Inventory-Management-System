from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from common.permissions import NotViewerPermission, RolePermission

from .filters import ACTION_TYPES, AuditLogFilter, action_type_q, classify
from .models import AuditLog
from .serializers import AuditLogSerializer


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only access to the audit trail.

    Filterable by user, action type and date range - see :class:`AuditLogFilter`.
    """

    queryset = AuditLog.objects.select_related("user").all()
    serializer_class = AuditLogSerializer
    permission_classes = [NotViewerPermission, RolePermission]
    filterset_class = AuditLogFilter
    search_fields = ["action"]
    ordering_fields = ["timestamp", "log_id"]

    @action(detail=False, methods=["get"])
    def action_types(self, request):
        """The action-type vocabulary plus how many rows each one matches.

        The categories are disjoint, so the counts add up to ``total``.
        """
        base = self.filter_queryset(self.get_queryset())
        counts = [
            {"key": key, "label": label, "count": base.filter(action_type_q(key)).count()}
            for key, label, _patterns in ACTION_TYPES
        ]
        counts.append(
            {"key": "other", "label": "Other", "count": base.filter(action_type_q("other")).count()}
        )
        return Response({"total": base.count(), "action_types": counts})

    @action(detail=False, methods=["get"])
    def export(self, request):
        """Download the currently filtered audit trail as CSV."""
        from django.utils import timezone

        from reports.exports import render_csv
        from reports.report_data import Section

        logs = self.filter_queryset(self.get_queryset()).order_by("-timestamp")[:5000]
        rows = [
            [
                log.log_id,
                log.user.name if log.user else "System",
                classify(log.action),
                log.action,
                log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            ]
            for log in logs
        ]
        section = Section(
            "Audit Log",
            "AUDIT LOG",
            ["Log ID", "User", "Action Type", "Action", "Timestamp"],
            rows,
        )
        stamp = timezone.now().strftime("%Y-%m-%d")
        return render_csv([section], filename=f"CSE_Audit_Log_{stamp}.csv")
