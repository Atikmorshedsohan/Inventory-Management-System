"""
Remove sample/test data and keep only original data
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'inventory_backend.settings')
django.setup()

from django.utils import timezone
from inventory.models import StockTransaction, RoomItemHistory, KeyBorrow

print("🗑️  Clearing Test/Sample Data\n")

# Delete sample stock transactions
sample_txns = StockTransaction.objects.filter(
    notes__icontains='sample'
).union(
    StockTransaction.objects.filter(notes__in=[
        'Restock from supplier',
        'Issued for lab use',
        'New inventory received',
        'Allocated to project',
        'Monthly replenishment'
    ])
)
deleted_txns = sample_txns.count()
sample_txns.delete()
print(f"✓ Deleted {deleted_txns} sample stock transactions")

# Delete sample room moves
sample_moves = RoomItemHistory.objects.filter(
    remarks__in=[
        'Relocated for better organization',
        'Lab reorganization',
        'Equipment reallocation',
        'Room reassignment per admin request',
        'Inventory consolidation'
    ]
)
deleted_moves = sample_moves.count()
sample_moves.delete()
print(f"✓ Deleted {deleted_moves} sample room moves")

# Delete sample key borrows (created for testing)
sample_borrows = KeyBorrow.objects.filter(
    purpose__in=[
        'Lab maintenance',
        'Project work',
        'Equipment access',
        'Room inspection'
    ]
)
deleted_borrows = sample_borrows.count()
sample_borrows.delete()
print(f"✓ Deleted {deleted_borrows} sample key borrows")

print(f"\n✨ Sample data removed!")
print(f"\n📊 Remaining data:")
print(f"   - Stock Transactions: {StockTransaction.objects.count()}")
print(f"   - Room Moves: {RoomItemHistory.objects.count()}")
print(f"   - Key Borrows: {KeyBorrow.objects.count()}")
