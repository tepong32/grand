from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("inventory_finance", "0001_initial")]

    operations = [migrations.AddField(
        model_name="receiptclaimattribution", name="receipt_snapshot",
        field=models.JSONField(null=True, blank=True),
    )]
