#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'inventory_backend.settings')
django.setup()

from inventory.models import PendingStockTransaction, PendingItem

# Get all pending stock transactions
pending_trans = PendingStockTransaction.objects.all().order_by('-requested_at')

print("=" * 60)
print(f"Total Pending Stock Transactions: {pending_trans.count()}")
print("=" * 60)

for trans in pending_trans[:10]:  # Show last 10
    print(f"\nID: {trans.pending_id}")
    print(f"Item: {trans.item.item_name if trans.item else 'N/A'}")
    print(f"Type: {trans.type}")
    print(f"Quantity: {trans.quantity}")
    print(f"Room: {trans.room.room_name if trans.room else 'N/A'}")
    print(f"Requested By: {trans.requested_by.name if trans.requested_by else 'N/A'}")
    print(f"Status: {trans.status}")
    print(f"Requested At: {trans.requested_at}")
    print("-" * 40)

print("\n" + "=" * 60)
print(f"Total Pending Items: {PendingItem.objects.count()}")
print("=" * 60)
