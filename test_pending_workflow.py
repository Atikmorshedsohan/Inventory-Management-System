"""
Test the pending item approval workflow
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'inventory_backend.settings')
django.setup()

from inventory.models import User, Category, Room, PendingItem, Item

# Get users
admin = User.objects.filter(role='admin').first()
staff = User.objects.filter(role='staff').first()

if not staff:
    print("Creating test staff user...")
    staff = User.objects.create_user(
        email='staff@test.com',
        name='Test Staff',
        password='staff123',
        role='staff'
    )
    print(f"✅ Created staff user: {staff.name}")

if not admin:
    print("❌ No admin user found. Please create one first.")
    exit(1)

# Get category and room
category = Category.objects.first()
room = Room.objects.first()

print(f"\n📋 Testing Pending Item Approval Workflow")
print(f"   Staff: {staff.name} ({staff.email})")
print(f"   Admin: {admin.name} ({admin.email})")

# Create a pending item as staff
pending_item = PendingItem.objects.create(
    item_name="Test Laptop",
    category=category,
    room=room,
    unit="pcs",
    quantity=5,
    min_quantity=2,
    description="Test item for approval workflow",
    requested_by=staff,
    status='pending'
)

print(f"\n✅ Staff created pending item: {pending_item.item_name}")
print(f"   Status: {pending_item.status}")
print(f"   Requested by: {pending_item.requested_by.name}")

# Check pending items count
pending_count = PendingItem.objects.filter(status='pending').count()
print(f"\n📊 Total pending items: {pending_count}")

# List all pending items
print(f"\n📝 All pending items:")
for item in PendingItem.objects.filter(status='pending'):
    print(f"   - {item.item_name} (ID: {item.pending_item_id}) - Requested by {item.requested_by.name}")

print(f"\n✨ Workflow setup complete!")
print(f"\n💡 Next steps:")
print(f"   1. Admin can view pending items at: GET /api/pending-items/?status=pending")
print(f"   2. Admin can approve with: POST /api/pending-items/{pending_item.pending_item_id}/approve/")
print(f"   3. Admin can reject with: POST /api/pending-items/{pending_item.pending_item_id}/reject/")
