#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'inventory_backend.settings')
django.setup()

from inventory.models import PendingStockTransaction, PendingItem
from django.contrib.auth import get_user_model

User = get_user_model()

# Check if models exist and can be imported
print("✅ PendingStockTransaction model loaded successfully")
print("✅ PendingItem model loaded successfully")

# Try to query pending transactions
pending_trans = PendingStockTransaction.objects.all()
print(f"📊 Pending stock transactions in database: {pending_trans.count()}")

# Try to query pending items
pending_items = PendingItem.objects.all()
print(f"📊 Pending items in database: {pending_items.count()}")

# Check admin registration
from django.contrib.admin.sites import site
from inventory.admin import PendingStockTransactionAdmin, PendingItemAdmin

if PendingStockTransaction in site._registry:
    print("✅ PendingStockTransaction is registered in admin")
else:
    print("❌ PendingStockTransaction is NOT registered in admin")

if PendingItem in site._registry:
    print("✅ PendingItem is registered in admin")
else:
    print("❌ PendingItem is NOT registered in admin")

print("\n✅ All systems ready!")
