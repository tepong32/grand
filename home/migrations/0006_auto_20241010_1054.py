# Generated by Django 5.1 on 2024-10-10 02:54

from django.db import migrations

def delete_my_model_data(apps, schema_editor):
    MyModel = apps.get_model('home', 'Leave')
    MyModel.objects.all().delete()

class Migration(migrations.Migration):

    dependencies = [
        ('home', '0005_alter_leave_employee_alter_leavecounter_employee'),
    ]

    operations = [
        migrations.RunPython(delete_my_model_data),
    ]

## delete this migration then restore the copy of db if needed
## test migration for deleting db records