from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import exports, selectors


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


class ExportCSVView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return exports.build_csv(exports.parse_days(request.query_params.get("days")))


class ExportExcelView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return exports.build_excel(exports.parse_days(request.query_params.get("days")))
