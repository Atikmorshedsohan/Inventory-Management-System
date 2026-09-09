from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import exports, selectors, services

_RECONCILE_ROLES = ("admin", "manager")


class DashboardStatsView(APIView):
    def get(self, request):
        return Response(selectors.dashboard_stats())


class RoomOverviewView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(selectors.room_overview())


class RoomwiseActivityView(APIView):
    """Activity feed for the room-wise inventory page."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(selectors.roomwise_activity())


class ReconciliationView(APIView):
    """Item balances vs. the sum of their stock transactions."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(selectors.reconciliation_report())


class ReconcileItemView(APIView):
    """Correct one item's ledger so it matches the counted balance."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        if getattr(request.user, "role", "viewer") not in _RECONCILE_ROLES:
            return Response(
                {"detail": "Only admins and managers can reconcile items."},
                status=403,
            )
        item_id = request.data.get("item_id") or request.data.get("item")
        if not item_id:
            return Response({"detail": "item_id is required."}, status=400)
        return Response(services.reconcile_item(item_id=item_id, user=request.user))


class LowStockView(APIView):
    """Which items are low, and in which room."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        rows = selectors.low_stock_items()
        return Response({"count": len(rows), "items": rows})


class RoomSnapshotView(APIView):
    """Point-in-time picture of what is in every room."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(selectors.room_snapshot())


class StockMovementView(APIView):
    """Daily stock IN vs stock OUT totals, for the dashboard chart."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        days = exports.parse_days(request.query_params.get("days"), default=30)
        return Response(selectors.stock_movement_series(days))


class ExportCSVView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return exports.build_csv(exports.parse_days(request.query_params.get("days")))


class ExportExcelView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return exports.build_excel(exports.parse_days(request.query_params.get("days")))


class SnapshotExportCSVView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return exports.build_snapshot_csv()


class SnapshotExportExcelView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return exports.build_snapshot_excel()
