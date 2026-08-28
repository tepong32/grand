from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("finance", "0004_financeworkflowexemption")]

    operations = [
        migrations.AlterField(
            model_name="financeconfigurationitem",
            name="category",
            field=models.CharField(
                choices=[
                    ("transaction_type", "Voucher / transaction type"),
                    ("payee_classification", "Payee classification"),
                    ("fund", "Fund"),
                    ("funding_source", "Funding source"),
                    ("responsibility_center", "Office / responsibility center"),
                    ("ppa_mfo", "PPA / major final output"),
                    ("project_activity", "Project / activity"),
                    ("bank_account", "Bank / payment account"),
                    ("payment_method", "Payment method"),
                    ("account_classification", "Account / expenditure classification"),
                    ("obligation_behavior", "OBR / obligation behavior"),
                    ("tax_rule", "Tax / deduction / rounding rule"),
                    ("document_requirement", "Supporting-document requirement"),
                    ("approval_route", "Approval step / threshold / route"),
                    ("confidentiality", "Confidentiality / retention setting"),
                ],
                max_length=32,
            ),
        ),
    ]
