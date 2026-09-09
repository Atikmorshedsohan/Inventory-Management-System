from django.db import migrations, models
from django.db.models import Q, Sum


def backfill_opening_quantity(apps, schema_editor):
    """Seed ``opening_quantity`` so every existing item starts out balanced.

    opening = current quantity - (IN - OUT + ADJUST) already on the ledger.
    """
    Item = apps.get_model("catalog", "Item")
    StockTransaction = apps.get_model("stock", "StockTransaction")

    for item in Item.objects.all().iterator():
        agg = StockTransaction.objects.filter(item_id=item.pk).aggregate(
            ins=Sum("quantity", filter=Q(type="IN")),
            outs=Sum("quantity", filter=Q(type="OUT")),
            adj=Sum("quantity", filter=Q(type="ADJUST")),
        )
        net = (agg["ins"] or 0) - (agg["outs"] or 0) + (agg["adj"] or 0)
        item.opening_quantity = item.quantity - net
        item.save(update_fields=["opening_quantity"])


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0001_initial"),
        ("stock", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="item",
            name="opening_quantity",
            field=models.IntegerField(default=0),
        ),
        migrations.RunPython(backfill_opening_quantity, migrations.RunPython.noop),
    ]
