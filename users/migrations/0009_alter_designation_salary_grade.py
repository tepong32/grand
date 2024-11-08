# Generated by Django 5.1 on 2024-09-24 01:36

import users.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0008_designation_remove_department_allowed_leaves_per_day_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='designation',
            name='salary_grade',
            field=models.PositiveIntegerField(default=1, validators=[users.models.validate_salary_grade], verbose_name='Salary Grade'),
        ),
    ]
