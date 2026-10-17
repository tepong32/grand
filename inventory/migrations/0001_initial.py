# Initial GSO inventory schema.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="Asset",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("department_id", models.PositiveBigIntegerField(db_index=True)),
                ("department_label", models.CharField(default="General Services", max_length=160)),
                ("asset_name", models.CharField(max_length=180, verbose_name="Asset name")),
                ("category", models.CharField(blank=True, max_length=100)),
                ("property_tag", models.CharField(blank=True, max_length=100, verbose_name="Property tag / asset number")),
                ("brand", models.CharField(blank=True, max_length=100)),
                ("model_number", models.CharField(blank=True, max_length=100, verbose_name="Model")),
                ("serial_number", models.CharField(blank=True, max_length=120)),
                ("obr_reference", models.CharField(blank=True, max_length=80, verbose_name="OBR / reference number")),
                ("purchase_date", models.DateField(blank=True, null=True)),
                ("supplier", models.CharField(blank=True, max_length=160)),
                ("unit_cost", models.DecimalField(blank=True, decimal_places=2, max_digits=13, null=True)),
                ("quantity", models.PositiveIntegerField(default=1)),
                ("assigned_department_id", models.PositiveBigIntegerField(blank=True, db_index=True, null=True)),
                ("assigned_department_label", models.CharField(blank=True, max_length=160)),
                ("assigned_office", models.CharField(blank=True, max_length=160, verbose_name="Assigned office / custodian")),
                ("status", models.CharField(choices=[("active", "In service"), ("maintenance", "Under maintenance"), ("transferred", "Transferred"), ("retired", "Retired")], default="active", max_length=20)),
                ("returned_date", models.DateField(blank=True, null=True)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="gso_assets_created", to=settings.AUTH_USER_MODEL)),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="gso_assets_updated", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ("asset_name", "pk"),
                "permissions": [("view_asset_audit", "Can view GSO asset change history")],
                "indexes": [models.Index(fields=["department_id", "status"], name="gso_asset_dept_status"), models.Index(fields=["department_id", "asset_name"], name="gso_asset_dept_name")],
            },
        ),
        migrations.CreateModel(
            name="AssetAuditEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("department_id", models.PositiveBigIntegerField(db_index=True)),
                ("action", models.CharField(choices=[("created", "Created"), ("updated", "Updated"), ("retired", "Retired")], max_length=12)),
                ("occurred_at", models.DateTimeField(auto_now_add=True)),
                ("snapshot", models.JSONField()),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="gso_asset_audit_events", to=settings.AUTH_USER_MODEL)),
                ("asset", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="audit_events", to="inventory.asset")),
            ],
            options={
                "ordering": ("-occurred_at", "-pk"),
            },
        ),
    ]
