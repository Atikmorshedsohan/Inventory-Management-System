#!/usr/bin/env python
"""
Django management command to seed room keys data.
Usage: python manage.py seed_keys
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from inventory.models import RoomKey, KeyAuditLog, User

class Command(BaseCommand):
    help = 'Seed the database with sample room keys data'

    def handle(self, *args, **options):
        # Get or create admin user for audit logs
        try:
            admin_user = User.objects.filter(role='admin').first()
        except:
            admin_user = None

        # Sample keys data
        keys_data = [
            {
                'room_name': 'Room 101',
                'key_number': 'K-001',
                'description': 'Master key for Room 101',
                'status': 'available',
                'last_location': 'Key Cabinet A'
            },
            {
                'room_name': 'Room 102',
                'key_number': 'K-002',
                'description': 'Key for Room 102 Lab',
                'status': 'available',
                'last_location': 'Key Cabinet A'
            },
            {
                'room_name': 'Room 103',
                'key_number': 'K-003',
                'description': 'Storage room key',
                'status': 'in_use',
                'last_location': 'With Staff'
            },
            {
                'room_name': 'Room 104',
                'key_number': 'K-004',
                'description': 'Conference room key',
                'status': 'available',
                'last_location': 'Key Cabinet B'
            },
            {
                'room_name': 'Room 105',
                'key_number': 'K-005',
                'description': 'Server room key',
                'status': 'maintenance',
                'last_location': 'Maintenance Dept'
            },
            {
                'room_name': 'Library',
                'key_number': 'K-006',
                'description': 'Main library access key',
                'status': 'available',
                'last_location': 'Key Cabinet A'
            },
            {
                'room_name': 'Cafeteria',
                'key_number': 'K-007',
                'description': 'Cafeteria storage key',
                'status': 'in_use',
                'last_location': 'With Staff'
            },
            {
                'room_name': 'Admin Office',
                'key_number': 'K-008',
                'description': 'Admin office master key',
                'status': 'available',
                'last_location': 'Key Cabinet C'
            },
            {
                'room_name': 'Security Room',
                'key_number': 'K-009',
                'description': 'Security control room key',
                'status': 'lost',
                'last_location': 'Unknown'
            },
            {
                'room_name': 'Parking Area',
                'key_number': 'K-010',
                'description': 'Parking gate access key',
                'status': 'available',
                'last_location': 'Security Office'
            },
        ]

        created_count = 0
        for key_data in keys_data:
            key, created = RoomKey.objects.get_or_create(
                key_number=key_data['key_number'],
                defaults={
                    'room_name': key_data['room_name'],
                    'description': key_data['description'],
                    'status': key_data['status'],
                    'last_location': key_data['last_location'],
                }
            )

            if created:
                # Create audit log for key creation
                if admin_user:
                    KeyAuditLog.objects.create(
                        key=key,
                        action='created',
                        performed_by=admin_user,
                        notes=f'Key created: {key_data["description"]}'
                    )
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Created key: {key_data["key_number"]} - {key_data["room_name"]}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'⊘ Key already exists: {key_data["key_number"]}')
                )

        self.stdout.write(
            self.style.SUCCESS(f'\nSuccessfully created {created_count} new room keys!')
        )

        # Print summary
        summary = RoomKey.objects.values('status').annotate(
            count=__import__('django.db.models', fromlist=['Count']).Count('key_id')
        )
        self.stdout.write('\n' + self.style.SUCCESS('Key Status Summary:'))
        for item in summary:
            self.stdout.write(f"  {item['status']}: {item['count']} keys")
