from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("reporting", "0005_controlled_template_mappers"),
    ]

    operations = [
        migrations.AddField(
            model_name="reportdefinition",
            name="applicability_status",
            field=models.CharField(
                choices=[
                    ("departmental", "Departmental / management output"),
                    ("candidate", "Controlled official-form candidate — local confirmation pending"),
                    ("confirmed", "Locally confirmed official requirement"),
                ],
                default="departmental",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="reportdefinition",
            name="authority_reference",
            field=models.TextField(
                blank=True,
                help_text="Plain-language COA, DBM, BIR, ordinance, memorandum, or local-procedure basis. Do not paste secrets or credentials.",
            ),
        ),
        migrations.AddField(
            model_name="reportdefinition",
            name="local_acceptance_note",
            field=models.TextField(
                blank=True,
                help_text="Record who confirmed local applicability, the accepted form/schedule, and where the retained evidence can be checked.",
            ),
        ),
        migrations.AddField(
            model_name="reportrun",
            name="control_checksum",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="reportrun",
            name="control_gate_required",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="reportrun",
            name="control_message",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="reportrun",
            name="control_status",
            field=models.CharField(
                choices=[
                    ("not_applicable", "Not applicable"),
                    ("reconciled", "Control totals reconciled"),
                    ("exception", "Control exception"),
                    ("unavailable", "Control evidence unavailable"),
                ],
                default="not_applicable",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="reportrun",
            name="control_totals",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="reportrun",
            name="dataset_checksum",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="reportrun",
            name="dataset_snapshot",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="reportrun",
            name="reproduction_key",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="reportrun",
            name="source_freshness_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="reportrun",
            name="source_record_count",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.CreateModel(
            name="ReportRunSource",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source_app", models.CharField(max_length=40)),
                ("source_model", models.CharField(max_length=80)),
                ("source_pk", models.CharField(max_length=80)),
                ("source_public_id", models.CharField(blank=True, max_length=80)),
                ("source_reference", models.CharField(max_length=180)),
                ("source_date", models.DateField(blank=True, null=True)),
                ("control_group", models.CharField(max_length=80)),
                ("amount", models.DecimalField(decimal_places=2, default=0, max_digits=18)),
                ("source_checksum", models.CharField(blank=True, max_length=64)),
                ("source_url", models.CharField(blank=True, max_length=500)),
                ("snapshot", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("run", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="source_records", to="reporting.reportrun")),
            ],
            options={
                "ordering": ("source_date", "source_app", "source_model", "source_reference", "pk"),
            },
        ),
        migrations.AddIndex(
            model_name="reportrunsource",
            index=models.Index(fields=["run", "control_group"], name="report_source_control_idx"),
        ),
    ]
