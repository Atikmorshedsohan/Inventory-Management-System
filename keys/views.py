from datetime import timedelta

from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from common.permissions import RolePermission

from . import services
from .models import KeyAuditLog, KeyBorrow, RoomKey
from .serializers import KeyAuditLogSerializer, KeyBorrowSerializer, RoomKeySerializer

_KEY_STAFF = ("staff", "admin", "manager")


class RoomKeyViewSet(viewsets.ModelViewSet):
    queryset = RoomKey.objects.all()
    serializer_class = RoomKeySerializer
    permission_classes = [RolePermission]
    filterset_fields = ["status", "room_name"]
    search_fields = ["room_name", "key_number", "description"]

    @action(detail=False, methods=["get"])
    def available_keys(self, request):
        keys = RoomKey.objects.filter(status="available")
        return Response(self.get_serializer(keys, many=True).data)

    @action(detail=True, methods=["get"])
    def borrow_history(self, request, pk=None):
        borrows = KeyBorrow.objects.filter(key=self.get_object()).order_by("-requested_at")
        return Response(KeyBorrowSerializer(borrows, many=True).data)


class KeyAuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = KeyAuditLog.objects.all()
    serializer_class = KeyAuditLogSerializer
    permission_classes = [RolePermission]
    filterset_fields = ["action", "key"]
    search_fields = ["key__key_number", "action"]
    ordering = ["-timestamp"]


class KeyBorrowViewSet(viewsets.ModelViewSet):
    queryset = KeyBorrow.objects.all()
    serializer_class = KeyBorrowSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["status", "borrower", "key"]
    search_fields = ["key__key_number", "borrower__name", "purpose"]
    ordering = ["-requested_at"]

    def get_queryset(self):
        if self.request.user.role == "viewer":
            return KeyBorrow.objects.filter(borrower=self.request.user)
        return KeyBorrow.objects.all()

    def create(self, request, *args, **kwargs):
        """Create a borrow request (viewers only)."""
        try:
            if request.user.role != "viewer":
                return Response(
                    {"detail": "Only viewers can request to borrow keys"},
                    status=status.HTTP_403_FORBIDDEN,
                )
            data = request.data.copy()
            data["borrower"] = request.user.pk
            serializer = self.get_serializer(data=data)
            serializer.is_valid(raise_exception=True)
            services.request_borrow(serializer=serializer, actor=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as exc:  # noqa: BLE001 - preserved: all errors -> 400 {"detail": ...}
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    def perform_create(self, serializer):
        serializer.save(borrower=self.request.user)

    # -- staff/admin actions -------------------------------------------------

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def approve(self, request, pk=None):
        if request.user.role not in _KEY_STAFF:
            return Response(
                {"detail": "Only staff can approve key borrow requests"},
                status=status.HTTP_403_FORBIDDEN,
            )
        borrow = services.approve_borrow(borrow=self.get_object(), approver=request.user)
        return Response(self.get_serializer(borrow).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def reject(self, request, pk=None):
        if request.user.role not in _KEY_STAFF:
            return Response(
                {"detail": "Only staff can reject key borrow requests"},
                status=status.HTTP_403_FORBIDDEN,
            )
        borrow = services.reject_borrow(
            borrow=self.get_object(),
            approver=request.user,
            reason=request.data.get("rejection_reason", "No reason provided"),
        )
        return Response(self.get_serializer(borrow).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def pickup(self, request, pk=None):
        borrow = self.get_object()
        if borrow.borrower != request.user and request.user.role not in _KEY_STAFF:
            return Response(
                {"detail": "You can only pick up your own keys"},
                status=status.HTTP_403_FORBIDDEN,
            )
        borrow = services.pickup_borrow(borrow=borrow, actor=request.user)
        return Response(self.get_serializer(borrow).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def return_key(self, request, pk=None):
        borrow = self.get_object()
        if borrow.borrower != request.user and request.user.role not in _KEY_STAFF:
            return Response(
                {"detail": "You can only return your own keys"},
                status=status.HTTP_403_FORBIDDEN,
            )
        borrow = services.return_borrow(
            borrow=borrow,
            actor=request.user,
            location=request.data.get("location", "Unknown"),
        )
        return Response(self.get_serializer(borrow).data, status=status.HTTP_200_OK)

    # -- read-only list actions -------------------------------------------------

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def my_requests(self, request):
        if request.user.role != "viewer":
            return Response(
                {"detail": "Only viewers can view their key requests"},
                status=status.HTTP_403_FORBIDDEN,
            )
        borrows = KeyBorrow.objects.filter(borrower=request.user).order_by("-requested_at")
        return Response(self.get_serializer(borrows, many=True).data)

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def pending_approvals(self, request):
        if request.user.role not in _KEY_STAFF:
            return Response(
                {"detail": "Only staff can view pending key borrow requests"},
                status=status.HTTP_403_FORBIDDEN,
            )
        pending = KeyBorrow.objects.filter(status="pending").select_related(
            "key", "borrower", "approver"
        )

        room = request.query_params.get("room_name")
        key_number = request.query_params.get("key_number")
        borrower_id = request.query_params.get("borrower_id")
        older_than_minutes = request.query_params.get("older_than_minutes")

        if room:
            pending = pending.filter(key__room_name__icontains=room)
        if key_number:
            pending = pending.filter(key__key_number__icontains=key_number)
        if borrower_id:
            try:
                pending = pending.filter(borrower_id=int(borrower_id))
            except ValueError:
                return Response(
                    {"detail": "borrower_id must be an integer"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        if older_than_minutes:
            try:
                cutoff = timezone.now() - timedelta(minutes=int(older_than_minutes))
            except ValueError:
                return Response(
                    {"detail": "older_than_minutes must be an integer"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            pending = pending.filter(requested_at__lte=cutoff)

        pending = pending.order_by("requested_at")
        return Response(self.get_serializer(pending, many=True).data)

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def overdue_keys(self, request):
        if request.user.role not in _KEY_STAFF:
            return Response(
                {"detail": "Only staff can view overdue keys"},
                status=status.HTTP_403_FORBIDDEN,
            )
        overdue = KeyBorrow.objects.filter(
            status="borrowed", expected_return_at__lt=timezone.now()
        ).order_by("expected_return_at")
        return Response(self.get_serializer(overdue, many=True).data)

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def active_borrow(self, request):
        active = KeyBorrow.objects.filter(status="borrowed").order_by("-borrowed_at")
        return Response(self.get_serializer(active, many=True).data)
