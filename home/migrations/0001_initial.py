# Generated by Django 4.2.6 on 2024-01-07 03:41

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Leave',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')], default='pending', max_length=10, verbose_name='Status')),
                ('start_date', models.DateField(verbose_name='Start Date')),
                ('end_date', models.DateField(verbose_name='End Date')),
                ('note', models.TextField(blank=True, null=True)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('modified', models.DateTimeField(auto_now=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='LeaveCounter',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('max_instances_per_year', models.PositiveIntegerField(default=25, help_text="This count shows the default. Always check for 'additional_instances' for the actual computation of the max_allowed instances per_year and per_quarter.", verbose_name='Max. Instances Per Year')),
                ('max_instances_per_quarter', models.PositiveIntegerField(default=6, help_text="This count shows the default. Always check for 'additional_instances' for the actual computation of the max_allowed instances per_year and per_quarter.", verbose_name='Max. Instances Per Quarter')),
                ('instances_used_this_year', models.PositiveIntegerField(default=0, verbose_name='Instances Used This Year')),
                ('instances_used_this_quarter', models.PositiveIntegerField(default=0, verbose_name='Instances Used This Quarter')),
                ('last_year_reset_date', models.DateField(blank=True, null=True, verbose_name='Last Year Reset Date')),
                ('last_quarter_reset_date', models.DateField(blank=True, null=True, verbose_name='Last Quarter Reset Date')),
                ('additional_instances_per_year', models.PositiveIntegerField(default=0, verbose_name='Additional Instances Per Year')),
                ('additional_instances_per_quarter', models.PositiveIntegerField(default=0, verbose_name='Additional Instances Per Quarter')),
                ('reset_this_quarter', models.BooleanField(default=False)),
            ],
        ),
        migrations.CreateModel(
            name='LeaveType',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, verbose_name='Name')),
            ],
        ),
    ]
