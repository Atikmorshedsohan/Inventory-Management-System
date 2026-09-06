from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db import transaction
from datetime import timedelta

from . import models, serializers


def user_display(user):
    """Return a safe display name for a user model."""
    if not user:
        return 'Unknown'
    for attr in ('name', 'full_name'):
        val = getattr(user, attr, None)
        if val:
            return val
    if hasattr(user, 'get_full_name'):
        val = user.get_full_name()
        if val:
            return val
    return getattr(user, 'username', str(user))
from .permissions import RolePermission


class RoomKeyViewSet(viewsets.ModelViewSet):
    """ViewSet for managing room keys"""
    queryset = models.RoomKey.objects.all()
    serializer_class = serializers.RoomKeySerializer
    permission_classes = [RolePermission]
    filterset_fields = ['status', 'room_name']
    search_fields = ['room_name', 'key_number', 'description']

    @action(detail=False, methods=['get'])
    def available_keys(self, request):
        """Get list of available keys that can be borrowed"""
        keys = models.RoomKey.objects.filter(status='available')
        serializer = self.get_serializer(keys, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def borrow_history(self, request, pk=None):
        """Get borrowing history for a specific key"""
        key = self.get_object()
        borrows = models.KeyBorrow.objects.filter(key=key).order_by('-requested_at')
        serializer = serializers.KeyBorrowSerializer(borrows, many=True)
        return Response(serializer.data)


class KeyAuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing key audit logs"""
    queryset = models.KeyAuditLog.objects.all()
    serializer_class = serializers.KeyAuditLogSerializer
    permission_classes = [RolePermission]
    filterset_fields = ['action', 'key']
    search_fields = ['key__key_number', 'action']
    ordering = ['-timestamp']


class KeyBorrowViewSet(viewsets.ModelViewSet):
    """ViewSet for managing key borrowing requests"""
    queryset = models.KeyBorrow.objects.all()
    serializer_class = serializers.KeyBorrowSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['status', 'borrower', 'key']
    search_fields = ['key__key_number', 'borrower__name', 'purpose']
    ordering = ['-requested_at']

    def get_queryset(self):
        """
        Filter queryset based on user role:
        - Viewers see only their own requests
        - Staff/Admin see all requests
        """
        user = self.request.user
        if user.role == 'viewer':
            return models.KeyBorrow.objects.filter(borrower=user)
        return models.KeyBorrow.objects.all()

    def create(self, request, *args, **kwargs):
        """Create a new key borrow request (viewers only)"""
        try:
            if request.user.role != 'viewer':
                return Response(
                    {'detail': 'Only viewers can request to borrow keys'},
                    status=status.HTTP_403_FORBIDDEN
                )

            data = request.data.copy()
            data['borrower'] = request.user.pk  # Use pk instead of id
            serializer = self.get_serializer(data=data)
            serializer.is_valid(raise_exception=True)

            key = serializer.validated_data['key']
            expected_return_at = serializer.validated_data.get('expected_return_at')

            # Basic sanity checks before creating the pending request
            if expected_return_at and expected_return_at <= timezone.now():
                return Response(
                    {'detail': 'Expected return time must be in the future'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            with transaction.atomic():
                # Clear this borrower's stale pending requests for the same key so they can re-request
                now = timezone.now()
                stale_self_pending = models.KeyBorrow.objects.select_for_update().filter(
                    key=key,
                    borrower=request.user,
                    status='pending'
                )
                if stale_self_pending.exists():
                    stale_self_pending.update(
                        status='rejected',
                        rejection_reason='Auto-cancelled: replaced by a new request',
                        approver=request.user,
                        approved_at=now
                    )

                # Block duplicate pending/active requests for the same key
                has_active_request = models.KeyBorrow.objects.select_for_update().filter(
                    key=key,
                    status__in=['pending', 'approved', 'borrowed']
                ).exists()
                if has_active_request:
                    return Response(
                        {'detail': 'This key already has a pending or active borrow request'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # Also check the key status to avoid queuing requests for lost/maintenance keys
                if key.status != 'available':
                    return Response(
                        {'detail': f'Key is not available (current status: {key.status})'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                self.perform_create(serializer)
                
                # Create audit log
                models.KeyAuditLog.objects.create(
                    key=serializer.instance.key,
                    action='borrowed',
                    performed_by=request.user,
                    notes=f"Requested to borrow key #{serializer.instance.borrow_id}"
                )
            
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response(
                {'detail': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    def perform_create(self, serializer):
        """Set borrower and create the borrow request"""
        serializer.save(borrower=self.request.user)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def approve(self, request, pk=None):
        """Approve a key borrow request (staff/admin only)"""
        if request.user.role not in ['staff', 'admin', 'manager']:
            return Response(
                {'detail': 'Only staff can approve key borrow requests'},
                status=status.HTTP_403_FORBIDDEN
            )

        borrow_request = self.get_object()
        
        # Allow re-issuing a returned request if the key is free
        if borrow_request.status == 'returned':
            if borrow_request.key.status != 'available':
                return Response(
                    {'detail': 'Key is not available to re-issue this returned request'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            # Treat as a fresh approval/hand-over
        elif borrow_request.status not in ['pending', 'approved']:
            return Response(
                {'detail': f'Cannot approve request with status: {borrow_request.status}. Only pending or approved requests can be approved.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            # Approve and hand over immediately
            now = timezone.now()
            borrow_request.status = 'borrowed'
            borrow_request.approver = request.user
            borrow_request.approved_at = now
            borrow_request.borrowed_at = now
            borrow_request.save()

            # Update key status and assign borrower
            borrow_request.key.status = 'in_use'
            borrow_request.key.assigned_to = borrow_request.borrower
            borrow_request.key.assigned_date = now
            borrow_request.key.save()

            # Auto-cancel any other outstanding requests for the same key
            other_requests = models.KeyBorrow.objects.select_for_update().filter(
                key=borrow_request.key,
                status__in=['pending', 'approved']
            ).exclude(pk=borrow_request.pk)
            if other_requests.exists():
                other_requests.update(
                    status='rejected',
                    rejection_reason='Auto-cancelled: key handed to another borrower',
                    approver=request.user,
                    approved_at=now
                )

            # Create audit log
            models.KeyAuditLog.objects.create(
                key=borrow_request.key,
                action='borrowed',
                performed_by=request.user,
                notes=f"Approved and handed over request #{borrow_request.borrow_id} to {user_display(borrow_request.borrower)}"
            )

        serializer = self.get_serializer(borrow_request)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def pickup(self, request, pk=None):
        """Mark key as picked up (viewer picks up approved key)"""
        borrow_request = self.get_object()
        
        if borrow_request.borrower != request.user and request.user.role not in ['staff', 'admin', 'manager']:
            return Response(
                {'detail': 'You can only pick up your own keys'},
                status=status.HTTP_403_FORBIDDEN
            )

        if borrow_request.status != 'approved':
            return Response(
                {'detail': f'Key can only be picked up from approved requests, current status: {borrow_request.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            borrow_request.status = 'borrowed'
            borrow_request.borrowed_at = timezone.now()
            borrow_request.save()

            # Update key status
            borrow_request.key.status = 'in_use'
            borrow_request.key.assigned_to = borrow_request.borrower
            borrow_request.key.assigned_date = timezone.now()
            borrow_request.key.save()

            # Auto-cancel any other outstanding requests for the same key
            now = timezone.now()
            other_requests = models.KeyBorrow.objects.select_for_update().filter(
                key=borrow_request.key,
                status__in=['pending', 'approved']
            ).exclude(pk=borrow_request.pk)
            if other_requests.exists():
                other_requests.update(
                    status='rejected',
                    rejection_reason='Auto-cancelled: key handed to another borrower',
                    approver=request.user,
                    approved_at=now
                )

            # Create audit log
            models.KeyAuditLog.objects.create(
                key=borrow_request.key,
                action='borrowed',
                performed_by=request.user,
                notes=f"Key picked up by {user_display(borrow_request.borrower)}"
            )

        serializer = self.get_serializer(borrow_request)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def return_key(self, request, pk=None):
        """Return a borrowed key"""
        borrow_request = self.get_object()
        
        if borrow_request.borrower != request.user and request.user.role not in ['staff', 'admin', 'manager']:
            return Response(
                {'detail': 'You can only return your own keys'},
                status=status.HTTP_403_FORBIDDEN
            )

        if borrow_request.status != 'borrowed':
            return Response(
                {'detail': f'Only borrowed keys can be returned, current status: {borrow_request.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            borrow_request.status = 'returned'
            borrow_request.returned_at = timezone.now()
            borrow_request.save()

            # Update key status back to available
            borrow_request.key.status = 'available'
            borrow_request.key.assigned_to = None
            borrow_request.key.assigned_date = None
            borrow_request.key.last_location = request.data.get('location', 'Unknown')
            borrow_request.key.save()

            # Create audit log
            models.KeyAuditLog.objects.create(
                key=borrow_request.key,
                action='returned_borrow',
                performed_by=request.user,
                notes=f"Key returned by {user_display(borrow_request.borrower)}. Location: {request.data.get('location', 'Unknown')}"
            )

        serializer = self.get_serializer(borrow_request)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def reject(self, request, pk=None):
        """Reject a key borrow request (staff/admin only)"""
        if request.user.role not in ['staff', 'admin', 'manager']:
            return Response(
                {'detail': 'Only staff can reject key borrow requests'},
                status=status.HTTP_403_FORBIDDEN
            )

        borrow_request = self.get_object()
        
        if borrow_request.status != 'pending':
            return Response(
                {'detail': f'Cannot reject request with status: {borrow_request.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        rejection_reason = request.data.get('rejection_reason', 'No reason provided')
        
        with transaction.atomic():
            borrow_request.status = 'rejected'
            borrow_request.rejection_reason = rejection_reason
            borrow_request.approver = request.user
            borrow_request.approved_at = timezone.now()
            borrow_request.save()

            # Create audit log
            models.KeyAuditLog.objects.create(
                key=borrow_request.key,
                action='returned_borrow',
                performed_by=request.user,
                notes=f"Borrow request #{borrow_request.borrow_id} rejected. Reason: {rejection_reason}"
            )

        serializer = self.get_serializer(borrow_request)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def my_requests(self, request):
        """Get current user's key borrow requests"""
        if request.user.role == 'viewer':
            borrows = models.KeyBorrow.objects.filter(borrower=request.user).order_by('-requested_at')
            serializer = self.get_serializer(borrows, many=True)
            return Response(serializer.data)
        return Response(
            {'detail': 'Only viewers can view their key requests'},
            status=status.HTTP_403_FORBIDDEN
        )

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def pending_approvals(self, request):
        """Get pending key borrow requests (staff/admin only)"""
        if request.user.role not in ['staff', 'admin', 'manager']:
            return Response(
                {'detail': 'Only staff can view pending key borrow requests'},
                status=status.HTTP_403_FORBIDDEN
            )
        pending = models.KeyBorrow.objects.filter(status='pending').select_related('key', 'borrower', 'approver')

        # Optional filters to slice the pending queue
        room_query = request.query_params.get('room_name')
        key_number_query = request.query_params.get('key_number')
        borrower_id_query = request.query_params.get('borrower_id')
        older_than_minutes = request.query_params.get('older_than_minutes')

        if room_query:
            pending = pending.filter(key__room_name__icontains=room_query)
        if key_number_query:
            pending = pending.filter(key__key_number__icontains=key_number_query)
        if borrower_id_query:
            try:
                pending = pending.filter(borrower_id=int(borrower_id_query))
            except ValueError:
                return Response({'detail': 'borrower_id must be an integer'}, status=status.HTTP_400_BAD_REQUEST)

        if older_than_minutes:
            try:
                minutes = int(older_than_minutes)
                cutoff = timezone.now() - timedelta(minutes=minutes)
                pending = pending.filter(requested_at__lte=cutoff)
            except ValueError:
                return Response({'detail': 'older_than_minutes must be an integer'}, status=status.HTTP_400_BAD_REQUEST)

        pending = pending.order_by('requested_at')

        stale_minutes = request.query_params.get('stale_minutes', 120)
        serializer = self.get_serializer(
            pending,
            many=True,
            context={**self.get_serializer_context(), 'pending_stale_minutes': stale_minutes}
        )
        return Response(serializer.data)

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def overdue_keys(self, request):
        """Get overdue borrowed keys"""
        if request.user.role not in ['staff', 'admin', 'manager']:
            return Response(
                {'detail': 'Only staff can view overdue keys'},
                status=status.HTTP_403_FORBIDDEN
            )

        overdue = models.KeyBorrow.objects.filter(
            status='borrowed',
            expected_return_at__lt=timezone.now()
        ).order_by('expected_return_at')
        serializer = self.get_serializer(overdue, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def active_borrow(self, request):
        """Get active (borrowed) key requests - keys currently in use"""
        active = models.KeyBorrow.objects.filter(status='borrowed').order_by('-borrowed_at')
        serializer = self.get_serializer(active, many=True)
        return Response(serializer.data)
