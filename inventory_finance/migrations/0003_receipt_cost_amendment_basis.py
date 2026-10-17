from django.db import migrations


class Migration(migrations.Migration):
    # The optional adapter now reads effective documentary costs from inventory.
    dependencies = [("inventory_finance", "0002_receipt_review_basis"),
                    ("inventory", "0020_receipt_cost_amendments")]
    operations = []
