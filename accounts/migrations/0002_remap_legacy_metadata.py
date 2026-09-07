"""Re-point Django's bookkeeping rows from the old single ``inventory`` app to
the new per-domain apps.

The tables themselves never moved (every model keeps its original
``db_table``), so this only rewrites ``django_content_type`` labels and drops
the now-orphaned ``inventory`` rows from ``django_migrations``. Permissions
follow automatically because they reference the content-type row by id.
"""

from django.db import migrations

# new app label -> model names (ContentType.model is lowercase, no underscores)
MODEL_MOVES = {
    "accounts": ["user", "passwordresettoken"],
    "audit": ["auditlog"],
    "catalog": ["category", "room", "item", "pendingitem"],
    "keys": ["roomkey", "keyborrow", "keyauditlog"],
    "requisitions": ["requisition", "requisitionitem"],
    "stock": ["pendingstocktransaction", "roomitemhistory", "stocktransaction"],
}
OLD_LABEL = "inventory"


def _remap(apps, old_label, moves):
    ContentType = apps.get_model("contenttypes", "ContentType")
    for new_label, model_names in moves.items():
        for model_name in model_names:
            legacy = ContentType.objects.filter(app_label=old_label, model=model_name).first()
            if legacy is None:
                continue
            if ContentType.objects.filter(app_label=new_label, model=model_name).exists():
                legacy.delete()  # a fresh row already exists; drop the stale one
            else:
                legacy.app_label = new_label
                legacy.save(update_fields=["app_label"])


def forwards(apps, schema_editor):
    _remap(apps, OLD_LABEL, MODEL_MOVES)
    # Forget the retired app's migration history.
    from django.db.migrations.recorder import MigrationRecorder

    MigrationRecorder(schema_editor.connection).migration_qs.filter(app=OLD_LABEL).delete()


def backwards(apps, schema_editor):
    # Move every content type back under the old label.
    ContentType = apps.get_model("contenttypes", "ContentType")
    for new_label, model_names in MODEL_MOVES.items():
        for model_name in model_names:
            ContentType.objects.filter(app_label=new_label, model=model_name).update(
                app_label=OLD_LABEL
            )


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
        ("audit", "0001_initial"),
        ("catalog", "0001_initial"),
        ("keys", "0001_initial"),
        ("requisitions", "0001_initial"),
        ("stock", "0001_initial"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
