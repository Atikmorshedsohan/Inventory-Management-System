#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'inventory_backend.settings')
django.setup()

from inventory.models import User

# Create superuser
admin_user = User.objects.create_user(
    email='admin@cse.edu',
    name='Admin User',
    password='admin123',
    role='admin'
)
admin_user.is_staff = True
admin_user.is_superuser = True
admin_user.save()

print(f"✅ Created superuser: {admin_user.email} (role: {admin_user.role})")
print(f"   Password: admin123")
