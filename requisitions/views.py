from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from inventory.permissions import RolePermission
from django_filters.rest_framework import DjangoFilterBackend
from .models import Requisition, RequisitionItem
from .serializers import RequisitionSerializer
from products.models import StockTransaction


class RequisitionViewSet(viewsets.ModelViewSet):
    queryset = Requisition.objects.all()
    serializer_class = RequisitionSerializer
    permission_classes = [IsAuthenticated, RolePermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['user', 'status']
    search_fields = ['purpose']
    ordering_fields = ['created_at']

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve a requisition"""
        requisition = self.get_object()
        
        if requisition.status != 'pending':
            return Response(
                {'error': 'Only pending requisitions can be approved'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        requisition.status = 'approved'
        requisition.save()
        
        # Log the action
        from audit.models import AuditLog
        AuditLog.objects.create(
            user=request.user,
            action=f"Approved requisition #{requisition.req_id}"
        )
        
        return Response({'status': 'Requisition approved'})

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject a requisition"""
        requisition = self.get_object()
        
        if requisition.status != 'pending':
            return Response(
                {'error': 'Only pending requisitions can be rejected'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        requisition.status = 'rejected'
        requisition.save()
        
        # Log the action
        from audit.models import AuditLog
        AuditLog.objects.create(
            user=request.user,
            action=f"Rejected requisition #{requisition.req_id}"
        )
        
        return Response({'status': 'Requisition rejected'})

    @action(detail=True, methods=['post'])
    def issue(self, request, pk=None):
        """Issue items for an approved requisition"""
        requisition = self.get_object()
        
        if requisition.status != 'approved':
            return Response(
                {'error': 'Only approved requisitions can be issued'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create OUT transactions for each item
        for req_item in requisition.items.all():
            StockTransaction.objects.create(
                item=req_item.item,
                type='OUT',
                quantity=req_item.quantity,
                user=request.user,
                notes=f"Issued for requisition #{requisition.req_id}"
            )
        
        requisition.status = 'issued'
        requisition.save()
        
        # Log the action
        from audit.models import AuditLog
        AuditLog.objects.create(
            user=request.user,
            action=f"Issued items for requisition #{requisition.req_id}"
        )
        
        return Response({'status': 'Items issued successfully'})
