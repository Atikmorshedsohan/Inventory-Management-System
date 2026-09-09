import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0001_initial"),
        ("stock", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="roomitemhistory",
            name="transfer_type",
            field=models.CharField(
                choices=[("full", "Full move"), ("partial", "Partial move")],
                default="full",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="roomitemhistory",
            name="quantity",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="roomitemhistory",
            name="dest_item",
            field=models.ForeignKey(
                blank=True,
                db_column="dest_item_id",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="incoming_transfers",
                to="catalog.item",
            ),
        ),
        migrations.AddField(
            model_name="roomitemhistory",
            name="source_qty_before",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="roomitemhistory",
            name="source_qty_after",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="roomitemhistory",
            name="dest_qty_before",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="roomitemhistory",
            name="dest_qty_after",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name="StockImportBatch",
            fields=[
                ("batch_id", models.AutoField(primary_key=True, serialize=False)),
                ("filename", models.CharField(blank=True, default="", max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("total_rows", models.IntegerField(default=0)),
                ("success_count", models.IntegerField(default=0)),
                ("error_count", models.IntegerField(default=0)),
                ("report", models.JSONField(blank=True, default=list)),
                (
                    "uploaded_by",
                    models.ForeignKey(
                        db_column="uploaded_by_id",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="stock_import_batches",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "stock_import_batches",
                "ordering": ["-created_at"],
            },
        ),
    ]
