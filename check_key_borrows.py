import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'inventory_backend.settings')
django.setup()

from django.utils import timezone
from datetime import timedelta
from inventory import models

now = timezone.now()
since_7d = now - timedelta(days=7)

# Check key borrows
key_borrows_qs = models.KeyBorrow.objects.select_related(
    'key', 'borrower', 'approver'
).filter(requested_at__gte=since_7d).order_by('-requested_at')

print(f"Key borrows in last 7 days: {key_borrows_qs.count()}")

for borrow in key_borrows_qs[:5]:
    print(f"\nBorrow ID: {borrow.borrow_id}")
    print(f"  Key: {borrow.key.key_number} ({borrow.key.room_name})")
    print(f"  Borrower: {borrow.borrower.name}")
    print(f"  Status: {borrow.status}")
    print(f"  Requested: {borrow.requested_at}")
    print(f"  Days ago: {(now - borrow.requested_at).days}")
