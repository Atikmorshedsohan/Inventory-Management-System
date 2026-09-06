#!/usr/bin/env python
"""Create sample room keys for testing"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'inventory_backend.settings')
django.setup()

from inventory.models import RoomKey, Room

# Check existing keys
existing_keys = RoomKey.objects.count()
print(f"Existing keys: {existing_keys}")

if existing_keys == 0:
    # Get all rooms
    rooms = Room.objects.all()
    print(f"Found {rooms.count()} rooms")
    
    if rooms.count() == 0:
        print("No rooms found! Please create rooms first.")
    else:
        # Create keys for each room
        for room in rooms:
            key, created = RoomKey.objects.get_or_create(
                room_name=room.room_name,
                defaults={
                    'key_number': f'KEY-{room.room_id:03d}',
                    'description': f'Key for {room.room_name}',
                    'status': 'available'
                }
            )
            if created:
                print(f"✓ Created key {key.key_number} for {room.room_name}")
            else:
                print(f"- Key already exists for {room.room_name}")
        
        print(f"\nTotal keys now: {RoomKey.objects.count()}")
else:
    print("Keys already exist:")
    for key in RoomKey.objects.all()[:10]:
        print(f"  - {key.key_number}: {key.room_name} ({key.status})")
