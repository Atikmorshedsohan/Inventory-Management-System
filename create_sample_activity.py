"""
Create sample stock transactions and room moves for testing activity display
"""
import os
import django
from datetime import timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'inventory_backend.settings')
django.setup()

from django.utils import timezone
from inventory.models import (
    User, Item, Room, StockTransaction, RoomItemHistory
)

def create_sample_activity():
    """Create sample stock transactions and room moves"""
    
    # Get or create admin user
    admin = User.objects.filter(role='admin').first()
    if not admin:
        admin = User.objects.create_user(
            email='admin@test.com',
            name='System Admin',
            password='admin123',
            role='admin'
        )
    
    # Get some items and rooms
    items = list(Item.objects.all()[:5])
    rooms = list(Room.objects.all()[:3])
    
    if not items:
        print("❌ No items found. Please create items first.")
        return
    
    if not rooms:
        print("❌ No rooms found. Please create rooms first.")
        return
    
    print(f"📦 Found {len(items)} items and {len(rooms)} rooms")
    
    # Create stock transactions
    print("\n📈 Creating sample stock transactions...")
    transaction_types = ['IN', 'OUT', 'IN', 'OUT', 'IN']
    notes_list = [
        'Restock from supplier',
        'Issued for lab use',
        'New inventory received',
        'Allocated to project',
        'Monthly replenishment'
    ]
    
    now = timezone.now()
    for i, item in enumerate(items):
        # Create transaction from a few days ago
        days_ago = i + 1
        timestamp = now - timedelta(days=days_ago, hours=i*2)
        
        trans = StockTransaction.objects.create(
            item=item,
            type=transaction_types[i % len(transaction_types)],
            quantity=10 + (i * 5),
            user=admin,
            timestamp=timestamp,
            notes=notes_list[i % len(notes_list)]
        )
        print(f"  ✅ Created: {trans.item.item_name} - {trans.type} {trans.quantity} units")
    
    # Create room moves
    print("\n🚚 Creating sample room moves...")
    move_remarks = [
        'Relocated for better organization',
        'Lab reorganization',
        'Equipment reallocation',
        'Room reassignment per admin request',
        'Inventory consolidation'
    ]
    
    for i, item in enumerate(items[:3]):  # Only move first 3 items
        days_ago = i + 1
        moved_at = now - timedelta(days=days_ago, hours=i*3)
        
        from_room = rooms[i % len(rooms)]
        to_room = rooms[(i + 1) % len(rooms)]
        
        # Update item's current room
        item.room = to_room
        item.save()
        
        move = RoomItemHistory.objects.create(
            item=item,
            from_room=from_room,
            to_room=to_room,
            user=admin,
            moved_at=moved_at,
            remarks=move_remarks[i % len(move_remarks)]
        )
        print(f"  ✅ Moved: {move.item.item_name} from {from_room.room_name} to {to_room.room_name}")
    
    print("\n✨ Sample activity data created successfully!")
    print(f"   - {StockTransaction.objects.count()} total stock transactions")
    print(f"   - {RoomItemHistory.objects.count()} total room moves")

if __name__ == '__main__':
    create_sample_activity()
