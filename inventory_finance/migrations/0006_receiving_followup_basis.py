from django.db import migrations


class Migration(migrations.Migration):
    # Adapter snapshots now read the original-delivery relation on new follow-ups.
    # No Finance tables or prior attribution snapshots are rewritten.
    dependencies = [
        ("inventory_finance", "0005_propertyfinancelink_propertyfinancelinkevent_and_more"),
        ("inventory", "0028_receiving_followup_source"),
    ]
    operations = []
