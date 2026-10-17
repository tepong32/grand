"""Preserve local keys and history while assigning distinct portable identities."""
from uuid import uuid4

from django.db import migrations, models


MODEL_NAMES = ("Asset", "ConsumableItem", "StockMovement")


def populate_public_ids(apps, schema_editor):
    for name in MODEL_NAMES:
        model = apps.get_model("inventory", name)
        rows = model.objects.using(schema_editor.connection.alias)
        # Do not evaluate a single callable default for every existing row.
        while True:
            batch = list(rows.filter(public_id__isnull=True).order_by("pk")[:500])
            if not batch:
                break
            for row in batch:
                row.public_id = uuid4()
            rows.bulk_update(batch, ["public_id"])


class Migration(migrations.Migration):
    dependencies = [("inventory", "0011_assetaccountingimport_source_file")]
    operations = [
        migrations.AddField(
            model_name=name.lower(), name="public_id",
            field=models.UUIDField(null=True, editable=False),
        ) for name in MODEL_NAMES
    ] + [
        migrations.RunPython(populate_public_ids, migrations.RunPython.noop),
    ] + [
        migrations.AlterField(
            model_name=name.lower(), name="public_id",
            field=models.UUIDField(default=uuid4, unique=True, editable=False),
        ) for name in MODEL_NAMES
    ]
