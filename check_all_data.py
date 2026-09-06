"""
Check what data exists in the database
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'inventory_backend.settings')
django.setup()

from django.utils import timezone
from datetime import timedelta
from inventory.models import (
    StockTransaction, RoomItemHistory, KeyBorrow, Item
)

now = timezone.now()
since_7d = now - timedelta(days=7)

print("=" * 60)
print("DATABASE DATA SUMMARY")
print("=" * 60)

# Stock Transactions
print("\n📦 STOCK TRANSACTIONS (Last 7 days):")
transactions = StockTransaction.objects.filter(timestamp__gte=since_7d).order_by('-timestamp')[:10]
print(f"Total: {transactions.count()}")
for txn in transactions:
    print(f"  • {txn.type}: {txn.item.item_name} - {txn.quantity} units by {txn.user.name if txn.user else 'System'} ({txn.timestamp.strftime('%Y-%m-%d %H:%M')})")

# Room Moves
print("\n🚚 ROOM MOVES (Last 7 days):")
moves = RoomItemHistory.objects.filter(moved_at__gte=since_7d).order_by('-moved_at')[:10]
print(f"Total: {moves.count()}")
for move in moves:
    from_room = move.from_room.room_name if move.from_room else 'Unassigned'
    to_room = move.to_room.room_name if move.to_room else 'Unassigned'
    print(f"  • {move.item.item_name}: {from_room} → {to_room} by {move.user.name if move.user else 'System'} ({move.moved_at.strftime('%Y-%m-%d %H:%M')})")

# Key Borrows
print("\n🔑 KEY BORROWS (Last 7 days):")
key_borrows = KeyBorrow.objects.filter(requested_at__gte=since_7d).order_by('-requested_at')[:10]
print(f"Total: {key_borrows.count()}")
for borrow in key_borrows:
    print(f"  • {borrow.key.key_number} ({borrow.key.room_name}): {borrow.status} by {borrow.borrower.name} ({borrow.requested_at.strftime('%Y-%m-%d %H:%M')})")

# All Items
print("\n📋 ALL ITEMS IN SYSTEM:")
items = Item.objects.all()
print(f"Total: {items.count()}")
for item in items[:10]:
    room = item.room.room_name if item.room else 'Unassigned'
    print(f"  • {item.item_name}: {item.quantity} {item.unit} in {room}")

print("\n" + "=" * 60)
print("WHICH DATA DO YOU WANT TO DISPLAY?")
print("=" * 60)
print("\nIf you want to:")
print("1. Keep the test data → It's already showing correctly")
print("2. Remove test data → I can help delete the sample data")
print("3. Add more real data → I can help create real inventory data")
