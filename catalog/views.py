from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from common.permissions import NoDeletePermission, RolePermission

from . import services
from .models import Category, Item, PendingItem, Room
from .serializers import (
    CategorySerializer,
    ItemSerializer,
    PendingItemSerializer,
    RoomSerializer,
)

_ITEM_APPROVERS = ("admin", "manager")
_PENDING_SELECT = ("category", "room", "requested_by", "approved_by")


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    search_fields = ["category_name"]
    permission_classes = [RolePermission]


class RoomViewSet(viewsets.ModelViewSet):
    queryset = Room.objects.all()
    serializer_class = RoomSerializer
    search_fields = ["room_name", "room_key", "location"]
    filterset_fields = ["room_type"]
    permission_classes = [RolePermission]


class ItemViewSet(viewsets.ModelViewSet):
    queryset = Item.objects.select_related("category", "room").all()
    serializer_class = ItemSerializer
    filterset_fields = ["category", "room"]
    search_fields = ["item_name"]
    permission_classes = [RolePermission, NoDeletePermission]

    def create(self, request, *args, **kwargs):
        """Staff submit items for approval; admin/manager create them directly."""
        if request.user.role == "staff":
            return self._submit_for_approval(request)
        return super().create(request, *args, **kwargs)

    def _submit_for_approval(self, request):
        data = request.data.copy()
        if "category_id" in data and "category" not in data:
            data["category"] = data.get("category_id")
        if "room_id" in data and "room" not in data:
            data["room"] = data.get("room_id")
        data["requested_by"] = request.user.pk
        data["status"] = "pending"

        serializer = PendingItemSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        pending_item = serializer.save(requested_by=request.user)
        services.note_item_submitted(user=request.user, pending_item=pending_item)

        return Response(
            {
                "message": "Item submitted for admin approval",
                "pending_item": serializer.data,
                "status": "pending_approval",
            },
            status=status.HTTP_201_CREATED,
        )

    def perform_create(self, serializer):
        data = serializer.validated_data
        # A fresh item's initial count is opening stock (it never hit the ledger),
        # unless the caller stated an explicit opening balance.
        if "opening_quantity" in data:
            item = serializer.save()
        else:
            item = serializer.save(opening_quantity=data.get("quantity", 0))
        services.note_item_created(user=self.request.user, item=item)
        services.sync_reorder_alert(item)

    def perform_update(self, serializer):
        item = serializer.save()
        # A hand-edited quantity can push the item below (or back above) its
        # minimum without a stock transaction.
        services.sync_reorder_alert(item)

    @action(detail=False, methods=["get"])
    def roomwise(self, request):
        """Inventory grouped by room/location with room properties."""
        return Response(services.roomwise_inventory())


class PendingItemViewSet(viewsets.ModelViewSet):
    """Pending item creation awaiting admin/manager approval."""

    queryset = PendingItem.objects.select_related(*_PENDING_SELECT).all()
    serializer_class = PendingItemSerializer
    filterset_fields = ["status", "category"]
    search_fields = ["item_name", "requested_by__name"]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = PendingItem.objects.select_related(*_PENDING_SELECT)
        if self.request.user.role in _ITEM_APPROVERS:
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
        services.note_item_submitted(user=self.request.user, pending_item=pending)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def approve(self, request, pk=None):
        if request.user.role not in _ITEM_APPROVERS:
            return Response(
                {"detail": "Only admins and managers can approve items"},
                status=status.HTTP_403_FORBIDDEN,
            )
        pending = services.approve_pending_item(
            pending=self.get_object(), approver=request.user
        )
        return Response(self.get_serializer(pending).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def reject(self, request, pk=None):
        if request.user.role not in _ITEM_APPROVERS:
            return Response(
                {"detail": "Only admins and managers can reject items"},
                status=status.HTTP_403_FORBIDDEN,
            )
        pending = services.reject_pending_item(
            pending=self.get_object(),
            approver=request.user,
            reason=request.data.get("rejection_reason", "No reason provided"),
        )
        return Response(self.get_serializer(pending).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def pending_approvals(self, request):
        if request.user.role not in _ITEM_APPROVERS:
            return Response(
                {"detail": "Only admins and managers can view pending approvals"},
                status=status.HTTP_403_FORBIDDEN,
            )
        pending = (
            PendingItem.objects.filter(status="pending")
            .select_related("category", "room", "requested_by")
            .order_by("requested_at")
        )
        return Response(self.get_serializer(pending, many=True).data)
