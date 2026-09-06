# Generated migration for adding room field to Item model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0004_passwordresettoken'),
    ]

    operations = [
        migrations.AddField(
            model_name='item',
            name='room',
            field=models.CharField(blank=True, default='General Storage', max_length=100, null=True),
        ),
    ]
