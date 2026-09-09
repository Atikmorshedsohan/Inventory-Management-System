from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="notification",
            name="category",
            field=models.CharField(
                choices=[("reorder", "Reorder alert"), ("general", "General")],
                default="general",
                max_length=20,
            ),
        ),
    ]
