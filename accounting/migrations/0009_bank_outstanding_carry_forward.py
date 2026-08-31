# Generated for F8.5 governed prior-period bank timing-item carry-forward.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounting", "0008_bankstatementbatch_bankreconciliationevent_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="bankoutstandingitem",
            name="carried_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="bankoutstandingitem",
            name="carried_by_id",
            field=models.PositiveBigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="bankoutstandingitem",
            name="carried_by_label",
            field=models.CharField(blank=True, max_length=160),
        ),
        migrations.AddField(
            model_name="bankoutstandingitem",
            name="carried_from",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="carry_forward_versions",
                to="accounting.bankoutstandingitem",
            ),
        ),
        migrations.AddField(
            model_name="bankoutstandingitem",
            name="cleared_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="bankoutstandingitem",
            name="cleared_by_id",
            field=models.PositiveBigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="bankoutstandingitem",
            name="cleared_by_label",
            field=models.CharField(blank=True, max_length=160),
        ),
        migrations.AddField(
            model_name="bankoutstandingitem",
            name="cleared_by_match",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="cleared_outstanding_items",
                to="accounting.bankstatementmatch",
            ),
        ),
        migrations.AlterField(
            model_name="bankoutstandingitem",
            name="status",
            field=models.CharField(
                choices=[
                    ("active", "Outstanding"),
                    ("superseded", "Superseded"),
                    ("cleared", "Cleared by later bank statement"),
                ],
                default="active",
                max_length=12,
            ),
        ),
    ]
