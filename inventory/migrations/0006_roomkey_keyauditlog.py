# Generated migration for adding RoomKey and KeyAuditLog models

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0005_item_room'),
    ]

    operations = [
        migrations.CreateModel(
            name='RoomKey',
            fields=[
                ('key_id', models.AutoField(primary_key=True, serialize=False)),
                ('room_name', models.CharField(max_length=100)),
                ('key_number', models.CharField(max_length=50, unique=True)),
                ('description', models.TextField(blank=True, null=True)),
                ('status', models.CharField(choices=[('available', 'Available'), ('in_use', 'In Use'), ('lost', 'Lost'), ('maintenance', 'Maintenance')], default='available', max_length=20)),
                ('assigned_date', models.DateTimeField(blank=True, null=True)),
                ('last_location', models.CharField(blank=True, max_length=200, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('assigned_to', models.ForeignKey(blank=True, db_column='assigned_to_id', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assigned_keys', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'room_keys',
                'ordering': ['room_name', 'key_number'],
            },
        ),
        migrations.CreateModel(
            name='KeyAuditLog',
            fields=[
                ('log_id', models.AutoField(primary_key=True, serialize=False)),
                ('action', models.CharField(choices=[('assigned', 'Assigned'), ('returned', 'Returned'), ('lost', 'Lost'), ('found', 'Found'), ('maintenance', 'Sent to Maintenance'), ('restored', 'Restored'), ('created', 'Created')], max_length=20)),
                ('notes', models.TextField(blank=True, null=True)),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('key', models.ForeignKey(db_column='key_id', on_delete=django.db.models.deletion.CASCADE, related_name='audit_logs', to='inventory.roomkey')),
                ('performed_by', models.ForeignKey(db_column='performed_by_id', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='key_audit_logs', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'key_audit_log',
                'ordering': ['-timestamp'],
            },
        ),
    ]
