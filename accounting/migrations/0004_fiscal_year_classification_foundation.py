import datetime
import uuid

import django.db.models.deletion
from django.db import migrations, models


READINESS_LAYERS = ("technical", "budget", "accounting", "treasury", "forms")


def adopt_existing_setup(apps, schema_editor):
    if schema_editor.connection.alias != "finance":
        return
    AccountingPeriod = apps.get_model("accounting", "AccountingPeriod")
    FiscalYear = apps.get_model("accounting", "FiscalYear")
    Readiness = apps.get_model("accounting", "FiscalYearReadinessApproval")
    for model_name in ("Fund", "ResponsibilityCenter", "LedgerAccount"):
        model = apps.get_model("accounting", model_name)
        for record in model.objects.filter(public_id__isnull=True).iterator():
            record.public_id = uuid.uuid4()
            record.save(update_fields=("public_id",))
    keys = AccountingPeriod.objects.order_by().values_list(
        "department_id", "department_label", "fiscal_year",
    ).distinct()
    for department_id, department_label, year in keys:
        periods = AccountingPeriod.objects.filter(department_id=department_id, fiscal_year=year)
        starts_on = min(datetime.date(year, 1, 1), *(period.starts_on for period in periods))
        ends_on = max(datetime.date(year, 12, 31), *(period.ends_on for period in periods))
        fiscal_year, _created = FiscalYear.objects.get_or_create(
            department_id=department_id,
            year=year,
            defaults={
                "department_label": department_label,
                "label": f"FY {year}",
                "starts_on": starts_on,
                "ends_on": ends_on,
                "business_date": starts_on,
            },
        )
        periods.filter(fiscal_year_record__isnull=True).update(fiscal_year_record=fiscal_year)
        for layer in READINESS_LAYERS:
            Readiness.objects.get_or_create(
                fiscal_year=fiscal_year,
                layer=layer,
                defaults={"department_id": department_id, "department_label": department_label},
            )


class Migration(migrations.Migration):
    dependencies = [("accounting", "0003_journalentry_reversal_of_and_more")]

    operations = [
        migrations.AddField(
            model_name="accountingperiod", name="is_adjustment_period",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(model_name="fund", name="category", field=models.CharField(blank=True, max_length=80)),
        migrations.AddField(model_name="fund", name="effective_from", field=models.DateField(blank=True, null=True)),
        migrations.AddField(model_name="fund", name="effective_to", field=models.DateField(blank=True, null=True)),
        migrations.AddField(model_name="fund", name="public_id", field=models.UUIDField(editable=False, null=True)),
        migrations.AddField(model_name="ledgeraccount", name="effective_from", field=models.DateField(blank=True, null=True)),
        migrations.AddField(model_name="ledgeraccount", name="effective_to", field=models.DateField(blank=True, null=True)),
        migrations.AddField(model_name="ledgeraccount", name="government_account_code", field=models.CharField(blank=True, max_length=40)),
        migrations.AddField(model_name="ledgeraccount", name="public_id", field=models.UUIDField(editable=False, null=True)),
        migrations.AddField(model_name="ledgeraccount", name="subsidiary_reference_type", field=models.CharField(blank=True, max_length=80)),
        migrations.AddField(model_name="responsibilitycenter", name="effective_from", field=models.DateField(blank=True, null=True)),
        migrations.AddField(model_name="responsibilitycenter", name="effective_to", field=models.DateField(blank=True, null=True)),
        migrations.AddField(model_name="responsibilitycenter", name="office_code", field=models.CharField(blank=True, max_length=40)),
        migrations.AddField(
            model_name="responsibilitycenter", name="office_id",
            field=models.PositiveBigIntegerField(blank=True, help_text="Stable snapshot of the core office identity, not a cross-database relation.", null=True),
        ),
        migrations.AddField(model_name="responsibilitycenter", name="public_id", field=models.UUIDField(editable=False, null=True)),
        migrations.AlterField(
            model_name="accountingperiod", name="fiscal_year",
            field=models.PositiveSmallIntegerField(help_text="Compatibility snapshot of the typed fiscal year."),
        ),
        migrations.CreateModel(
            name="FiscalYear",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("department_id", models.PositiveBigIntegerField(db_index=True)),
                ("department_label", models.CharField(max_length=160)),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("year", models.PositiveSmallIntegerField()),
                ("label", models.CharField(max_length=80)),
                ("starts_on", models.DateField()),
                ("ends_on", models.DateField()),
                ("business_date", models.DateField(help_text="The controlled operational date used by Finance workflows.")),
                ("status", models.CharField(choices=[("draft", "Draft"), ("for_review", "For review"), ("approved", "Approved"), ("active", "Active"), ("closed", "Closed")], default="draft", max_length=16)),
                ("source_release_id", models.PositiveBigIntegerField(blank=True, null=True)),
                ("source_release_code", models.CharField(blank=True, max_length=80)),
                ("source_release_version", models.PositiveIntegerField(blank=True, null=True)),
                ("source_checksum", models.CharField(blank=True, max_length=64)),
                ("created_by_id", models.PositiveBigIntegerField(blank=True, null=True)),
                ("created_by_label", models.CharField(blank=True, max_length=160)),
                ("submitted_by_id", models.PositiveBigIntegerField(blank=True, null=True)),
                ("submitted_by_label", models.CharField(blank=True, max_length=160)),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("approved_by_id", models.PositiveBigIntegerField(blank=True, null=True)),
                ("approved_by_label", models.CharField(blank=True, max_length=160)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("state_version", models.PositiveIntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ("-year", "department_id"),
                "permissions": (("approve_fiscal_readiness", "Can approve fiscal-year setup and readiness layers"),),
                "constraints": [models.UniqueConstraint(fields=("department_id", "year"), name="unique_typed_fiscal_year")],
            },
        ),
        migrations.AddField(
            model_name="accountingperiod", name="fiscal_year_record",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="periods", to="accounting.fiscalyear"),
        ),
        migrations.CreateModel(
            name="FiscalYearReadinessApproval",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("department_id", models.PositiveBigIntegerField(db_index=True)),
                ("department_label", models.CharField(max_length=160)),
                ("layer", models.CharField(choices=[("technical", "Technical setup"), ("budget", "Budget approval"), ("accounting", "Accounting approval"), ("treasury", "Treasury readiness"), ("forms", "Form readiness")], max_length=16)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("approved", "Approved"), ("returned", "Returned")], default="pending", max_length=12)),
                ("evidence_note", models.TextField(blank=True)),
                ("decided_by_id", models.PositiveBigIntegerField(blank=True, null=True)),
                ("decided_by_label", models.CharField(blank=True, max_length=160)),
                ("decided_at", models.DateTimeField(blank=True, null=True)),
                ("state_version", models.PositiveIntegerField(default=1)),
                ("fiscal_year", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="readiness_layers", to="accounting.fiscalyear")),
            ],
            options={
                "ordering": ("fiscal_year__year", "layer"),
                "constraints": [models.UniqueConstraint(fields=("fiscal_year", "layer"), name="unique_fiscal_readiness_layer")],
            },
        ),
        migrations.RunPython(adopt_existing_setup, migrations.RunPython.noop),
        migrations.AlterField(model_name="fund", name="public_id", field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
        migrations.AlterField(model_name="ledgeraccount", name="public_id", field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
        migrations.AlterField(model_name="responsibilitycenter", name="public_id", field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
        migrations.CreateModel(
            name="FundingSource",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("department_id", models.PositiveBigIntegerField(db_index=True)),
                ("department_label", models.CharField(max_length=160)),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("code", models.CharField(max_length=40)),
                ("name", models.CharField(max_length=180)),
                ("kind", models.CharField(choices=[("local", "Local source"), ("national", "National government transfer"), ("grant", "Grant"), ("loan", "Loan proceeds"), ("trust", "Trust / special purpose"), ("other", "Other approved source")], default="local", max_length=16)),
                ("authority_reference", models.CharField(blank=True, max_length=160)),
                ("effective_from", models.DateField()),
                ("effective_to", models.DateField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("fiscal_year", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="funding_sources", to="accounting.fiscalyear")),
                ("fund", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="funding_sources", to="accounting.fund")),
            ],
            options={"ordering": ("fiscal_year__year", "code")},
        ),
        migrations.CreateModel(
            name="ProgramActivityProject",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("department_id", models.PositiveBigIntegerField(db_index=True)),
                ("department_label", models.CharField(max_length=160)),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("code", models.CharField(max_length=60)),
                ("name", models.CharField(max_length=220)),
                ("kind", models.CharField(choices=[("mfo", "Major final output"), ("program", "Program"), ("ppa", "Program / project / activity group"), ("project", "Project"), ("activity", "Activity")], max_length=16)),
                ("authority_reference", models.CharField(blank=True, max_length=160)),
                ("effective_from", models.DateField()),
                ("effective_to", models.DateField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("fiscal_year", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="program_classifications", to="accounting.fiscalyear")),
                ("funding_source", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="program_classifications", to="accounting.fundingsource")),
                ("parent", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="children", to="accounting.programactivityproject")),
                ("responsibility_center", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="program_classifications", to="accounting.responsibilitycenter")),
            ],
            options={"ordering": ("fiscal_year__year", "code")},
        ),
        migrations.AddConstraint(
            model_name="fundingsource",
            constraint=models.UniqueConstraint(fields=("department_id", "fiscal_year", "code"), name="unique_funding_source"),
        ),
        migrations.AddConstraint(
            model_name="programactivityproject",
            constraint=models.UniqueConstraint(fields=("department_id", "fiscal_year", "code"), name="unique_program_classification"),
        ),
    ]
