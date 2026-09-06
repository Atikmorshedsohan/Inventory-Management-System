"""
Create sample key borrow activity for testing
"""
import os
import django
from datetime import timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'inventory_backend.settings')
django.setup()

from django.utils import timezone
from inventory.models import User, RoomKey, KeyBorrow

def create_sample_key_activity():
    """Create sample key borrow records"""
    
    # Get users
    admin = User.objects.filter(role__in=['admin', 'staff', 'manager']).first()
    viewer = User.objects.filter(role='viewer').first()
    
    if not admin:
        print("❌ No admin/staff user found. Please create one first.")
        return
    
    if not viewer:
        print("❌ No viewer user found. Creating one...")
        viewer = User.objects.create_user(
            email='viewer@test.com',
            name='Test Viewer',
            password='viewer123',
            role='viewer'
        )
    
    # Get some keys
    keys = list(RoomKey.objects.all()[:3])
    
    if not keys:
        print("❌ No room keys found. Please create keys first.")
        return
    
    print(f"🔑 Found {len(keys)} keys")
    
    now = timezone.now()
    
    # Create various key borrow statuses
    activities = [
        {
            'key': keys[0],
            'status': 'returned',
            'days_ago': 1,
            'purpose': 'Lab maintenance',
            'has_approval': True,
            'has_borrow': True,
            'has_return': True
        },
        {
            'key': keys[1],
            'status': 'borrowed',
            'days_ago': 2,
            'purpose': 'Project work',
            'has_approval': True,
            'has_borrow': True,
            'has_return': False
        },
        {
            'key': keys[2],
            'status': 'approved',
            'days_ago': 3,
            'purpose': 'Equipment access',
            'has_approval': True,
            'has_borrow': False,
            'has_return': False
        },
    ]
    
    if len(keys) > 0:
        activities.append({
            'key': keys[0],
            'status': 'pending',
            'days_ago': 0,
            'purpose': 'Room inspection',
            'has_approval': False,
            'has_borrow': False,
            'has_return': False
        })
    
    print("\n📝 Creating sample key borrow records...")
    for activity in activities:
        requested_at = now - timedelta(days=activity['days_ago'], hours=2)
        
        borrow = KeyBorrow.objects.create(
            key=activity['key'],
            borrower=viewer,
            purpose=activity['purpose'],
            status=activity['status'],
            requested_at=requested_at,
            expected_return_at=now + timedelta(days=1),
        )
        
        if activity['has_approval']:
            borrow.approver = admin
            borrow.approved_at = requested_at + timedelta(hours=1)
        
        if activity['has_borrow']:
            borrow.borrowed_at = requested_at + timedelta(hours=2)
            # Update key status
            if activity['status'] == 'borrowed':
                activity['key'].status = 'in_use'
                activity['key'].assigned_to = viewer
                activity['key'].assigned_date = borrow.borrowed_at
                activity['key'].save()
        
        if activity['has_return']:
            borrow.returned_at = requested_at + timedelta(hours=6)
            # Reset key status
            activity['key'].status = 'available'
            activity['key'].assigned_to = None
            activity['key'].assigned_date = None
            activity['key'].save()
        
        borrow.save()
        
        print(f"  ✅ Created: {activity['key'].key_number} - {activity['status'].upper()} - {activity['purpose']}")
    
    print("\n✨ Sample key borrow activity created successfully!")
    print(f"   - {KeyBorrow.objects.count()} total key borrow records")

if __name__ == '__main__':
    create_sample_key_activity()
