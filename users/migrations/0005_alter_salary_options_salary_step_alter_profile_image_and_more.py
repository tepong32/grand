# Generated by Django 5.1 on 2024-09-20 05:15

import users.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0004_alter_salary_amount_alter_salary_grade'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='salary',
            options={'verbose_name_plural': 'Salaries'},
        ),
        migrations.AddField(
            model_name='salary',
            name='step',
            field=models.PositiveIntegerField(blank=True, default=0),
        ),
        migrations.AlterField(
            model_name='profile',
            name='image',
            field=models.ImageField(blank=True, default='defaults/default_user_dp.png', upload_to=users.models.Profile.dp_directory_path, verbose_name='Profile Picture: '),
        ),
        migrations.AlterUniqueTogether(
            name='salary',
            unique_together={('grade', 'step')},
        ),
    ]