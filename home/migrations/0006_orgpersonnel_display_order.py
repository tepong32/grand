# Generated by Django 5.1 on 2025-03-12 06:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0005_departmentcontact_email'),
    ]

    operations = [
        migrations.AddField(
            model_name='orgpersonnel',
            name='display_order',
            field=models.PositiveIntegerField(blank=True, help_text='Mayor as 1, VM as 2, etc.', null=True),
        ),
    ]
