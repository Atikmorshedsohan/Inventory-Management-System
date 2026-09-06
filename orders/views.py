from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from .models import Order, OrderItem
from .serializers import OrderSerializer
import uuid


class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['customer', 'status']
    search_fields = ['order_number', 'customer__name']
    ordering_fields = ['created_at', 'total_amount']

    def perform_create(self, serializer):
        # Generate unique order number
        order_number = f"ORD-{uuid.uuid4().hex[:8].upper()}"
        serializer.save(created_by=self.request.user, order_number=order_number)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Mark order as completed"""
        order = self.get_object()
        order.status = 'completed'
        order.save()
        return Response({'status': 'Order completed'})

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel order and restore stock"""
        order = self.get_object()
        
        # Restore product stock
        for item in order.items.all():
            item.product.quantity_in_stock += item.quantity
            item.product.save()
        
        order.status = 'cancelled'
        order.save()
        return Response({'status': 'Order cancelled'})
