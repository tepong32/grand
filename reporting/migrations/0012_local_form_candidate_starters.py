import django.core.validators
import reporting.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reporting", "0011_financelocalformacceptance_financelocalformevent_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="financelocalformacceptance",
            name="delivery_mode",
            field=models.CharField(
                choices=[
                    ("unconfirmed", "Candidate starter — confirm locally"),
                    ("digital", "Digital file only"),
                    ("print", "Printed or pre-printed form"),
                    ("both", "Digital file and printed copy"),
                ],
                default="both",
                max_length=12,
            ),
        ),
        migrations.AlterField(
            model_name="financelocalformacceptance",
            name="reference_file",
            field=models.FileField(
                blank=True,
                help_text=(
                    "Upload only a blank or safely redacted reference up to 10 MB. "
                    "A candidate starter may remain blank while the office collects the current local copy."
                ),
                max_length=500,
                upload_to=reporting.models.local_form_reference_path,
                validators=[
                    django.core.validators.FileExtensionValidator(
                        ("pdf", "xlsx", "xls", "docx", "png", "jpg", "jpeg")
                    )
                ],
            ),
        ),
        migrations.AddField(
            model_name="financelocalformsection",
            name="field_instructions",
            field=models.TextField(
                blank=True,
                help_text="List the familiar fields or column group employees expect in this section.",
            ),
        ),
        migrations.AddField(
            model_name="financelocalformsection",
            name="source_instructions",
            field=models.TextField(
                blank=True,
                help_text="Name the governed GRAND record or retained source that supplies this section.",
            ),
        ),
        migrations.AddField(
            model_name="financelocalformsection",
            name="control_instructions",
            field=models.TextField(
                blank=True,
                help_text="Explain totals, cross-checks, limits, and other observable validation rules.",
            ),
        ),
        migrations.AddField(
            model_name="financelocalformsection",
            name="owner_instructions",
            field=models.TextField(
                blank=True,
                help_text="Name the office/role that prepares, reviews, signs, or keeps this section.",
            ),
        ),
        migrations.AddField(
            model_name="financelocalformsection",
            name="print_instructions",
            field=models.TextField(
                blank=True,
                help_text="Explain headings, page breaks, continuation, amount format, and signature space.",
            ),
        ),
        migrations.AddField(
            model_name="financelocalformsection",
            name="starter_reference",
            field=models.CharField(
                blank=True,
                help_text="Official-source page anchor supplied by a built-in candidate starter.",
                max_length=120,
            ),
        ),
        migrations.AddField(
            model_name="financelocalformsection",
            name="confirmation_status",
            field=models.CharField(
                choices=[
                    ("candidate", "Candidate starter — confirm locally"),
                    ("local_entry", "Entered from the current local form"),
                    ("confirmed", "Starter row matched to the current local form"),
                    ("not_applicable", "Starter row documented as not applicable"),
                ],
                default="local_entry",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="financelocalformsection",
            name="local_confirmation_reference",
            field=models.TextField(
                blank=True,
                help_text=(
                    "For a built-in starter row, cite the current local form, page/section, comparison, "
                    "or decision that confirms or excludes it."
                ),
            ),
        ),
    ]
