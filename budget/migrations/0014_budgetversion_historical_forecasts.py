from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('budget', '0013_combined_version_identity')]
    operations = [migrations.AddField(model_name='budgetversion', name='historical_forecasts',
        field=models.JSONField(blank=True, default=dict, editable=False))]
