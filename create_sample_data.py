#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'inventory_backend.settings')
django.setup()

from inventory.models import Room, Category, Item

# Create rooms
rooms_data = [
    {'room_name': 'Room 200', 'room_type': 'Class Room', 'location': '1st Floor', 'room_key': True},
    {'room_name': 'Room 201', 'room_type': 'Computer Lab', 'location': '1st Floor', 'room_key': True},
    {'room_name': 'Room 202', 'room_type': 'Staff Room', 'location': '1st Floor', 'room_key': True},
    {'room_name': 'Room 301', 'room_type': 'Class Room', 'location': '2nd Floor', 'room_key': False},
]

rooms = []
for room_data in rooms_data:
    room = Room.objects.create(**room_data)
    rooms.append(room)
    print(f"✅ Created room: {room.room_name}")

# Create categories
categories_data = [
    {'category_name': 'Electronics', 'description': 'Electronic devices and equipment'},
    {'category_name': 'Stationery', 'description': 'Paper, pens, and office supplies'},
    {'category_name': 'Furniture', 'description': 'Tables, chairs, and desks'},
]

categories = []
for cat_data in categories_data:
    cat = Category.objects.create(**cat_data)
    categories.append(cat)
    print(f"✅ Created category: {cat.category_name}")

# Create items and assign to rooms
items_data = [
    {'item_name': 'Projector', 'category': categories[0], 'room': rooms[0], 'unit': 'pcs', 'quantity': 2, 'min_quantity': 1},
    {'item_name': 'Laptop', 'category': categories[0], 'room': rooms[1], 'unit': 'pcs', 'quantity': 15, 'min_quantity': 5},
    {'item_name': 'Whiteboard Marker', 'category': categories[1], 'room': rooms[0], 'unit': 'box', 'quantity': 10, 'min_quantity': 3},
    {'item_name': 'Desk Chair', 'category': categories[2], 'room': rooms[0], 'unit': 'pcs', 'quantity': 30, 'min_quantity': 10},
    {'item_name': 'A4 Paper', 'category': categories[1], 'room': rooms[2], 'unit': 'ream', 'quantity': 5, 'min_quantity': 2},
    {'item_name': 'Printer', 'category': categories[0], 'room': rooms[2], 'unit': 'pcs', 'quantity': 1, 'min_quantity': 1},
]

for item_data in items_data:
    item = Item.objects.create(**item_data)
    print(f"✅ Created item: {item.item_name} → {item.room.room_name if item.room else 'General Storage'}")

print("\n✅ Database reset complete with sample data!")
