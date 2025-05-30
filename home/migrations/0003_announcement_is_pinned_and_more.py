# Generated by Django 5.1 on 2025-01-02 06:25

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0002_rename_annnouncement_type_announcement_announcement_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='announcement',
            name='is_pinned',
            field=models.BooleanField(default=False, help_text='Indicates if the announcement is pinned.', verbose_name='Pinned'),
        ),
        migrations.AlterField(
            model_name='announcement',
            name='announcement_type',
            field=models.CharField(blank=True, choices=[('Public', 'Public - for the general masses'), ('Internal', 'Internal - for employees only')], default='Public', help_text='Select the type of announcement. Public is for everyone, Internal is for employees only', max_length=20, verbose_name='Type: '),
        ),
    ]
