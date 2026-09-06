#!/usr/bin/env python
"""
Test script to verify that viewers cannot access requisitions and audit logs
"""
import os
import django
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'inventory_backend.settings')
django.setup()

from django.test import TestCase
from inventory.models import User
from inventory.permissions import NotViewerPermission
from rest_framework.test import APIRequestFactory
from rest_framework.request import Request

# Create a mock request factory
factory = APIRequestFactory()

# Create test users
print("Creating test users...")
viewer_user, _ = User.objects.get_or_create(
    email='viewer@test.com',
    defaults={'name': 'Viewer User', 'role': 'viewer'}
)
admin_user, _ = User.objects.get_or_create(
    email='admin@test.com',
    defaults={'name': 'Admin User', 'role': 'admin'}
)
manager_user, _ = User.objects.get_or_create(
    email='manager@test.com',
    defaults={'name': 'Manager User', 'role': 'manager'}
)
staff_user, _ = User.objects.get_or_create(
    email='staff@test.com',
    defaults={'name': 'Staff User', 'role': 'staff'}
)

print(f"✓ Created viewer user: {viewer_user.name} (role: {viewer_user.role})")
print(f"✓ Created admin user: {admin_user.name} (role: {admin_user.role})")
print(f"✓ Created manager user: {manager_user.name} (role: {manager_user.role})")
print(f"✓ Created staff user: {staff_user.name} (role: {staff_user.role})")

# Test NotViewerPermission
permission = NotViewerPermission()
print("\n" + "="*50)
print("Testing NotViewerPermission")
print("="*50)

# Test with viewer (should fail)
request = factory.get('/api/audit-logs/')
request.user = viewer_user
drf_request = Request(request)

# Check that viewer_user is authenticated
print(f"Viewer user is_authenticated: {viewer_user.is_authenticated}")

result = permission.has_permission(drf_request, None)
print(f"Viewer access to audit logs: {result} (expected: False)")
assert result == False, "Viewer should NOT have permission!"
print("✅ PASS: Viewer correctly denied access")

# Test with admin (should pass)
request = factory.get('/api/audit-logs/')
request.user = admin_user
# Create a proper DRF Request object by passing the user correctly
from django.contrib.auth.models import AnonymousUser
# Create a mock request object
request.user = admin_user

# Manually call the permission check since DRF Request might be wrapping things
permission_check = NotViewerPermission()
result = permission_check.has_permission(request, None)

print(f"Admin user role: {getattr(admin_user, 'role', 'UNDEFINED')}")
print(f"Admin access to audit logs: {result} (expected: True)")
assert result == True, "Admin should have permission!"
print("✅ PASS: Admin correctly granted access")

# Test with manager (should pass)
request = factory.get('/api/audit-logs/')
request.user = manager_user
result = permission_check.has_permission(request, None)
print(f"Manager access to audit logs: {result} (expected: True)")
assert result == True, "Manager should have permission!"
print("✅ PASS: Manager correctly granted access")

# Test with staff (should pass)
request = factory.get('/api/audit-logs/')
request.user = staff_user
result = permission_check.has_permission(request, None)
print(f"Staff access to audit logs: {result} (expected: True)")
assert result == True, "Staff should have permission!"
print("✅ PASS: Staff correctly granted access")

print("\n" + "="*50)
print("✨ All permission tests passed!")
print("="*50)
