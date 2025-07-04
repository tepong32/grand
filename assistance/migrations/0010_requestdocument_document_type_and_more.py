# Generated by Django 5.2 on 2025-06-27 06:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('assistance', '0009_assistancerequest_telegram_chat_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='requestdocument',
            name='document_type',
            field=models.CharField(choices=[('birth_cert', 'Birth Certificate'), ('indigency', 'Certificate of Indigency'), ('school_id', 'School ID'), ('grade_card', 'Report Card / Grade Card'), ('cert_of_enrollment', 'Certificate of Enrollment/Registration'), ('others', 'Other Supporting Document')], default='others', max_length=30),
        ),
        migrations.AlterUniqueTogether(
            name='requestdocument',
            unique_together={('request', 'document_type')},
        ),
    ]
