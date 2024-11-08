# Generated by Django 5.1 on 2024-09-18 07:31

import django.db.models.deletion
import django.utils.timezone
import users.models
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.CreateModel(
            name='Manager',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
            ],
        ),
        migrations.CreateModel(
            name='User',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('password', models.CharField(max_length=128, verbose_name='password')),
                ('username', models.CharField(max_length=255, unique=True)),
                ('email', models.EmailField(max_length=254, unique=True)),
                ('date_joined', models.DateTimeField(default=django.utils.timezone.now)),
                ('last_login', models.DateTimeField(auto_now=True)),
                ('is_active', models.BooleanField(default=True)),
                ('is_staff', models.BooleanField(default=False)),
                ('is_superuser', models.BooleanField(default=False)),
                ('first_name', models.CharField(max_length=50)),
                ('middle_name', models.CharField(blank=True, max_length=50)),
                ('last_name', models.CharField(max_length=50)),
                ('ext_name', models.CharField(blank=True, max_length=3, null=True, verbose_name='Extension')),
                ('groups', models.ManyToManyField(blank=True, help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.', related_name='user_set', related_query_name='user', to='auth.group', verbose_name='groups')),
                ('user_permissions', models.ManyToManyField(blank=True, help_text='Specific permissions for this user.', related_name='user_set', related_query_name='user', to='auth.permission', verbose_name='user permissions')),
            ],
            options={
                'verbose_name': 'User',
                'verbose_name_plural': 'Users',
            },
            managers=[
                ('objects', users.models.CustomUserManager()),
            ],
        ),
        migrations.CreateModel(
            name='Department',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(blank=True, choices=[('---select one---', 'select'), ('Accounting Office', 'ACCTG'), ('Agriculture Office', 'AGRI'), ('Business Processes & Licensing Office', 'BPLO'), ('General Services Office', 'GSO'), ('Human Resources', 'HR'), ("Local Civil Registrar's Office", 'LCR'), ("Municipal Administrator's Office", 'MA'), ('Environment & Natural Resources Office', 'MENRO'), ("Mayor's Office", 'MO'), ('Social Welfare & Development', 'MSWD'), ("Treasurer's Office", 'MTO'), ('Senior Citizen Affairs', 'OSCA')], default='---select one---', max_length=80, verbose_name='Department: ')),
                ('allowed_leaves_per_day', models.PositiveIntegerField(blank=True, default=99, help_text='\n            This will help with auto-approve leave requests.\n            Computation will be: allowed leaves - approved leaves for the day. If there are still available allowed_leaves_per_day instances, the leave requests will be auto-approved.\n            If there are none, the leave status will just be set to default: "Pending".\n        ', null=True)),
                ('manager', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='users.manager')),
            ],
            options={
                'verbose_name_plural': 'Departments',
            },
        ),
        migrations.CreateModel(
            name='Profile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('contact_number', models.PositiveIntegerField(max_length=11, null=True)),
                ('address', models.CharField(max_length=255, null=True)),
                ('designation', models.CharField(max_length=255, null=True)),
                ('salary_grade', models.PositiveIntegerField(blank=True, help_text='Only visible to you or Administrators.', max_length=10, null=True)),
                ('sg_step', models.PositiveIntegerField(blank=True, help_text='Only visible to you or Administrators.', max_length=1, null=True)),
                ('image', models.ImageField(blank=True, default='defaults/default_user_dp.png', help_text='Help us recognize you. ;)', upload_to=users.models.Profile.dp_directory_path, verbose_name='Profile Picture: ')),
                ('department', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='users.department')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
