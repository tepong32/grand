from django.db import migrations


class Migration(migrations.Migration):
    # Source snapshots/ceilings consume retained GSO corrections in default only.
    dependencies = [
        ("inventory_finance", "0006_receiving_followup_basis"),
        ("inventory", "0029_receipt_quantity_corrections"),
    ]
    operations = []
