#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'inventory_backend.settings')
django.setup()

from django.db import connection

cursor = connection.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%pending%'")
tables = cursor.fetchall()

if tables:
    print("Pending tables found:")
    for table in tables:
        print(f"  - {table[0]}")
else:
    print("No pending tables found!")
    
# Also show all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
all_tables = cursor.fetchall()
print("\nAll tables in database:")
for table in all_tables:
    print(f"  - {table[0]}")
