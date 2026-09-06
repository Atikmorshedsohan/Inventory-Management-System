from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, Count, Avg
from django.utils import timezone
from datetime import timedelta
from products.models import Item, StockTransaction
from suppliers.models import Purchase
from requisitions.models import Requisition


class DashboardStatsView(APIView):
    """Dashboard statistics"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Total counts
        total_items = Item.objects.count()
        total_categories = Item.objects.values('category').distinct().count()
        
        # Low stock items
        low_stock_count = len([item for item in Item.objects.all() if item.is_low_stock])
        
        # Out of stock
        out_of_stock_count = Item.objects.filter(quantity=0).count()

        # Total inventory value (based on recent purchases)
        total_inventory_value = 0
        for item in Item.objects.all():
            latest_purchase = item.purchases.order_by('-purchase_date').first()
            if latest_purchase:
                total_inventory_value += item.quantity * latest_purchase.unit_price

        # Recent transactions (last 7 days)
        last_week = timezone.now() - timedelta(days=7)
        recent_transactions = StockTransaction.objects.filter(timestamp__gte=last_week).count()
        
        # Pending requisitions
        pending_requisitions = Requisition.objects.filter(status='pending').count()

        return Response({
            'total_items': total_items,
            'total_categories': total_categories,
            'low_stock_count': low_stock_count,
            'out_of_stock_count': out_of_stock_count,
            'total_inventory_value': float(total_inventory_value),
            'recent_transactions': recent_transactions,
            'pending_requisitions': pending_requisitions,
        })


class InventoryReportView(APIView):
    """Inventory report"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Stock status
        items = Item.objects.all()
        total_items = items.count()
        in_stock = items.filter(quantity__gt=0).count()
        out_of_stock = items.filter(quantity=0).count()
        low_stock = len([item for item in items if item.is_low_stock and item.quantity > 0])

        # Items by category
        items_by_category = items.values(
            'category__category_name'
        ).annotate(
            count=Count('item_id'),
            total_stock=Sum('quantity')
        ).order_by('-count')

        # Recent stock transactions
        recent_transactions = StockTransaction.objects.all()[:20].values(
            'item__item_name', 'type', 'quantity', 'timestamp', 'user__name'
        )

        return Response({
            'total_items': total_items,
            'in_stock': in_stock,
            'out_of_stock': out_of_stock,
            'low_stock': low_stock,
            'items_by_category': list(items_by_category),
            'recent_transactions': list(recent_transactions),
        })


class PurchaseReportView(APIView):
    """Purchase analytics report"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Get date range from query params
        days = int(request.query_params.get('days', 30))
        start_date = timezone.now() - timedelta(days=days)

        purchases = Purchase.objects.filter(purchase_date__gte=start_date)

        # Total purchases
        total_purchases = purchases.count()
        
        # Total spending
        total_spent = sum(p.total_cost for p in purchases)

        # Purchases by supplier
        purchases_by_supplier = purchases.values(
            'supplier__supplier_name'
        ).annotate(
            count=Count('purchase_id'),
            total_amount=Sum('quantity')
        ).order_by('-count')[:10]

        # Top purchased items
        top_items = purchases.values(
            'item__item_name'
        ).annotate(
            total_quantity=Sum('quantity'),
            purchase_count=Count('purchase_id')
        ).order_by('-total_quantity')[:10]

        return Response({
            'period_days': days,
            'total_purchases': total_purchases,
            'total_spent': float(total_spent),
            'purchases_by_supplier': list(purchases_by_supplier),
            'top_items': list(top_items),
        })


class RequisitionReportView(APIView):
    """Requisition analytics report"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Requisitions by status
        requisitions_by_status = Requisition.objects.values('status').annotate(
            count=Count('req_id')
        )

        # Recent requisitions
        recent_requisitions = Requisition.objects.all()[:10].values(
            'req_id', 'user__name', 'status', 'created_at', 'purpose'
        )

        # Most requested items
        from requisitions.models import RequisitionItem
        most_requested = RequisitionItem.objects.values(
            'item__item_name'
        ).annotate(
            total_quantity=Sum('quantity'),
            request_count=Count('req_item_id')
        ).order_by('-total_quantity')[:10]

        return Response({
            'requisitions_by_status': list(requisitions_by_status),
            'recent_requisitions': list(recent_requisitions),
            'most_requested_items': list(most_requested),
        })
