#!/usr/bin/env python
import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'inventory_backend.settings')
django.setup()

from inventory.models import PendingStockTransaction
from inventory.serializers import PendingStockTransactionSerializer

# Get all pending transactions
pending = PendingStockTransaction.objects.filter(status='pending').select_related('item', 'room', 'requested_by').order_by('requested_at')

print(f"Total pending transactions with status='pending': {pending.count()}")
print("\n" + "=" * 80)

# Serialize them
serializer = PendingStockTransactionSerializer(pending, many=True)
data = serializer.data

print("Serialized data that the API returns:")
print(json.dumps(data, indent=2, default=str))

print("\n" + "=" * 80)
print("\nField checks:")
for trans in data[:3]:  # Check first 3
    print(f"\nTransaction ID: {trans.get('pending_id')}")
    print(f"  - item_name: {trans.get('item_name')}")
    print(f"  - room_name: {trans.get('room_name')}")
    print(f"  - requested_by_name: {trans.get('requested_by_name')}")
    print(f"  - type: {trans.get('type')}")
    print(f"  - quantity: {trans.get('quantity')}")
    print(f"  - status: {trans.get('status')}")
