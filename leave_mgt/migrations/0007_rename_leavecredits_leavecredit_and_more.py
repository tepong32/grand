# Generated by Django 5.1 on 2024-11-24 06:58

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('leave_mgt', '0006_leavecreditlog_leaverequest_delete_leave'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='LeaveCredits',
            new_name='LeaveCredit',
        ),
        migrations.AlterModelOptions(
            name='leaverequest',
            options={'ordering': ['-date_filed']},
        ),
    ]