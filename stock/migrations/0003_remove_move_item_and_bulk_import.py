"""Drop the Move Item (transfer) scaffolding and Bulk Import batches.

Reverses stock/0002: the ``RoomItemHistory`` transfer snapshot columns and the
``StockImportBatch`` model. ``RoomItemHistory`` stays as a plain audit trail of
a stocked item's room changing (written by Stock IN/OUT).
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("stock", "0002_transfers_and_import_batches"),
    ]

    operations = [
        migrations.RemoveField(model_name="roomitemhistory", name="transfer_type"),
        migrations.RemoveField(model_name="roomitemhistory", name="quantity"),
        migrations.RemoveField(model_name="roomitemhistory", name="dest_item"),
        migrations.RemoveField(model_name="roomitemhistory", name="source_qty_before"),
        migrations.RemoveField(model_name="roomitemhistory", name="source_qty_after"),
        migrations.RemoveField(model_name="roomitemhistory", name="dest_qty_before"),
        migrations.RemoveField(model_name="roomitemhistory", name="dest_qty_after"),
        migrations.DeleteModel(name="StockImportBatch"),
    ]
