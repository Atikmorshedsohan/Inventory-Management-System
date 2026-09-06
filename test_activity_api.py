"""
Test the roomwise activity API endpoint
"""
import os
import django
import requests

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'inventory_backend.settings')
django.setup()

from rest_framework_simplejwt.tokens import AccessToken
from inventory.models import User

# Get admin user and generate token
admin = User.objects.filter(role__in=['admin', 'staff', 'manager']).first()
if not admin:
    print("❌ No admin user found")
    exit(1)

token = str(AccessToken.for_user(admin))
print(f"✓ Generated token for: {admin.name}")

# Test the API endpoint
url = 'http://127.0.0.1:8000/api/reports/roomwise-activity/'
headers = {'Authorization': f'Bearer {token}'}

try:
    response = requests.get(url, headers=headers)
    print(f"\n📡 API Response Status: {response.status_code}")
    
    if response.ok:
        data = response.json()
        print(f"\n✅ Data received:")
        print(f"   - recent_transactions: {len(data.get('recent_transactions', []))} items")
        print(f"   - recent_moves: {len(data.get('recent_moves', []))} items")
        print(f"   - recent_key_borrows: {len(data.get('recent_key_borrows', []))} items")
        
        if data.get('recent_key_borrows'):
            print(f"\n🔑 Key Borrows:")
            for kb in data['recent_key_borrows'][:3]:
                print(f"   - {kb.get('key_number')} ({kb.get('room_name')}) - {kb.get('status')} by {kb.get('borrower_name')}")
        else:
            print("\n⚠️ No key borrows in response!")
    else:
        print(f"❌ Error: {response.text}")
except Exception as e:
    print(f"❌ Request failed: {e}")
