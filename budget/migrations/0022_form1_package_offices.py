"""Index retained office scopes without changing original package history."""
import hashlib
import json
from django.db import migrations, models
import django.db.models.deletion


def inspected_scopes(apps,schema_editor):
    Package=apps.get_model('budget','Form1Package')
    alias=schema_editor.connection.alias
    # Inspect every retained root before writing any projection. Corrupt/missing
    # scopes require investigation; never guess an office or rewrite evidence.
    scopes=[]
    for record in Package.objects.using(alias).select_related('fund').iterator():
        try:
            root=record.payload
            digest=hashlib.sha256(json.dumps(root,sort_keys=True,separators=(',',':'),default=str).encode()).hexdigest()
            identity=root['identity']
            members=root['assembly']['payload']['members']
            if digest!=record.payload_checksum or not members or (
                identity['department_id']!=record.department_id or identity['fund_id']!=record.fund_id
                or identity['accounting_department_id']!=record.fund.department_id):
                raise ValueError('changed retained identity')
            offices={record.department_id,record.fund.department_id}
            for member in members:
                office=member['scope']['treasury_department_id']
                if type(office)is not int or office<=0: raise ValueError('invalid Treasury office')
                offices.add(office)
            if any(type(office)is not int or office<=0 for office in offices): raise ValueError('invalid office')
            scopes.append((record.pk,offices))
        except (KeyError,TypeError,ValueError,AttributeError) as error:
            raise RuntimeError(f'Inspect original Form 1 package {record.pk} before office indexing.') from error
    return scopes


def preflight(apps,schema_editor):
    inspected_scopes(apps,schema_editor)


def backfill(apps,schema_editor):
    scopes=inspected_scopes(apps,schema_editor)
    Office=apps.get_model('budget','Form1PackageOffice')
    alias=schema_editor.connection.alias
    for pk,offices in scopes:
        Office.objects.using(alias).bulk_create([Office(package_id=pk,department_id=office) for office in sorted(offices)])


class Migration(migrations.Migration):
    dependencies=[('budget','0021_form1_package_decisions')]
    operations=[
        # Native MySQL DDL is not transactional. Refuse bad historical roots
        # before creating a table, then recheck before populating it.
        migrations.RunPython(preflight,migrations.RunPython.noop),
        migrations.CreateModel(name='Form1PackageOffice',fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
            ('department_id',models.PositiveBigIntegerField(db_index=True)),
            ('package',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name='office_index',to='budget.form1package')),
        ],options={'constraints':[models.UniqueConstraint(fields=('package','department_id'),name='unique_form1_package_office')]}),
        migrations.RunPython(backfill,migrations.RunPython.noop),
    ]
