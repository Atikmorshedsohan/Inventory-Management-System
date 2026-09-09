from django.db import transaction
from django.http import HttpResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.models import Room
from common.permissions import RolePermission

from . import services
from .models import (
    PendingStockTransaction,
    RoomItemHistory,
    StockImportBatch,
    StockTransaction,
)
from .serializers import (
    ItemTransferSerializer,
    PendingStockTransactionSerializer,
    RoomItemHistorySerializer,
    StockImportBatchSerializer,
    StockTransactionSerializer,
)

_STOCK_APPROVERS = ("admin", "manager", "staff")
_PENDING_SELECT = ("item", "room", "requested_by", "approved_by")


class StockTransactionViewSet(viewsets.ModelViewSet):
    queryset = StockTransaction.objects.select_related("item", "user").all()
    serializer_class = StockTransactionSerializer
    filterset_fields = ["type", "item"]
    permission_classes = [RolePermission]

    def perform_create(self, serializer):
        user = self.request.user if self.request.user.is_authenticated else None
        with transaction.atomic():
            txn = serializer.save(user=user)
            services.apply_stock_transaction(
                transaction_obj=txn,
                user=self.request.user,
                room_id=self.request.data.get("room"),
            )


class RoomItemHistoryViewSet(viewsets.ModelViewSet):
    queryset = RoomItemHistory.objects.select_related(
        "item", "from_room", "to_room", "user", "dest_item"
    ).all()
    serializer_class = RoomItemHistorySerializer
    filterset_fields = ["item", "from_room", "to_room", "transfer_type"]
    permission_classes = [RolePermission]

    def perform_create(self, serializer):
        with transaction.atomic():
            history = serializer.save()
            services.record_item_move(history=history)


class ItemTransferView(APIView):
    """Dedicated Move Item workflow (logs source + destination with snapshots)."""

    permission_classes = [RolePermission]

    def post(self, request):
        serializer = ItemTransferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        history = services.transfer_item(
            item=data["item"],
            to_room=data["to_room"],
            quantity=data.get("quantity"),
            user=request.user,
            remarks=data.get("remarks", ""),
        )
        return Response(
            RoomItemHistorySerializer(history).data, status=status.HTTP_201_CREATED
        )


class BulkStockImportView(APIView):
    """Upload a CSV to stock-in many items at once. GET returns a blank template."""

    permission_classes = [RolePermission]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        response = HttpResponse(services.IMPORT_TEMPLATE_CSV, content_type="text/csv")
        response["Content-Disposition"] = (
            'attachment; filename="stock_import_template.csv"'
        )
        return response

    def post(self, request):
        upload = request.FILES.get("file")
        if upload is None:
            return Response(
                {"detail": "Attach a CSV file in the 'file' field."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        batch = services.bulk_import_stock(
            file=upload, user=request.user, filename=getattr(upload, "name", "")
        )
        code = (
            status.HTTP_201_CREATED
            if batch.success_count
            else status.HTTP_400_BAD_REQUEST
        )
        return Response(StockImportBatchSerializer(batch).data, status=code)


class StockImportBatchViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = StockImportBatch.objects.select_related("uploaded_by").all()
    serializer_class = StockImportBatchSerializer
    permission_classes = [RolePermission]


class PendingStockTransactionViewSet(viewsets.ModelViewSet):
    """Stock transactions awaiting admin approval."""

    queryset = PendingStockTransaction.objects.select_related(*_PENDING_SELECT).all()
    serializer_class = PendingStockTransactionSerializer
    filterset_fields = ["status", "type", "item"]
    search_fields = ["item__item_name", "requested_by__name"]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = PendingStockTransaction.objects.select_related(*_PENDING_SELECT)
        if self.request.user.role in _STOCK_APPROVERS:
            return qs.all()
        return qs.filter(requested_by=self.request.user)

    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        data["requested_by"] = request.user.pk
        data["status"] = "pending"
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def perform_create(self, serializer):
        pending = serializer.save(requested_by=self.request.user)
        services.note_pending_stock_created(pending)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def approve(self, request, pk=None):
        if request.user.role not in _STOCK_APPROVERS:
            return Response(
                {"detail": "Only admins can approve stock transactions"},
                status=status.HTTP_403_FORBIDDEN,
            )
        pending = services.approve_pending_stock(
            pending=self.get_object(), approver=request.user
        )
        return Response(self.get_serializer(pending).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def reject(self, request, pk=None):
        if request.user.role not in _STOCK_APPROVERS:
            return Response(
                {"detail": "Only admins can reject transactions"},
                status=status.HTTP_403_FORBIDDEN,
            )
        pending = services.reject_pending_stock(
            pending=self.get_object(),
            approver=request.user,
            reason=request.data.get("rejection_reason", "No reason provided"),
        )
        return Response(self.get_serializer(pending).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def pending_approvals(self, request):
        if request.user.role != "admin":
            return Response(
                {"detail": "Only admins can view pending approvals"},
                status=status.HTTP_403_FORBIDDEN,
            )
        pending = (
            PendingStockTransaction.objects.filter(status="pending")
            .select_related("item", "room", "requested_by")
            .order_by("requested_at")
        )
        return Response(self.get_serializer(pending, many=True).data)
