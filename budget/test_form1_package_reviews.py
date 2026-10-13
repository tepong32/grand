from copy import deepcopy

from django.contrib.auth.models import Group,Permission
from django.core.exceptions import PermissionDenied,ValidationError
from accounting.cash_classifications import checksum
from accounting.budget_actuals import money
from accounting.models import JournalEntry
from vouchers.roles import FINANCE_ROLE_PERMISSIONS,FINANCE_UAT_VIEWER_GROUP
from . import test_form1_packages as fixtures,form1_package_reviews as service,form1_packages as packages
from .models import Form1PackageDecision


class Form1PackageReviewFixture(fixtures.Form1PackageFixture):
    def setUp(self):
        super().setUp()
        self.reviewers={'budget':self.reviewer,'accounting':self.checker,'treasury':self.treasurer}
        for role,actor in self.reviewers.items():
            actor.user_permissions.clear();actor.groups.clear()
            for permission in FINANCE_ROLE_PERMISSIONS[role.title()+' Form 1 Package Reviewer']:
                app,code=permission.split('.')
                actor.user_permissions.add(Permission.objects.get(content_type__app_label=app,codename=code))

    def decide_package(self,record,role='budget',**changes):
        args=dict(actor=self.reviewers[role],role=role,approve=True,
            checks={key:dict(verified=True,basis='Synthetic independent '+key+' inspection of original evidence')
                for key in service.CHECKS[role]},authority='Synthetic designated '+role+' reviewer',
            note='Independent original whole-package review; no statutory signature')
        args.update(changes);return service.review(record,**args)


class Form1PackageReviewTests(Form1PackageReviewFixture):
    def test_three_independent_decisions_pure_state_original_sources_and_no_issuance(self):
        before=JournalEntry.objects.count();record=self.retain();original=deepcopy(record.payload)
        self.assertEqual(service.snapshot(record,self.reviewer)['status'],'prepared')
        first=self.decide_package(record)
        self.assertEqual(service.snapshot(record,self.checker)['status'],'partially_reviewed')
        self.decide_package(record,'accounting');self.decide_package(record,'treasury')
        rows=list(record.decisions.all());attachments=list(record.attachments.all())
        with self.assertNumQueries(0,using='default'),self.assertNumQueries(0,using='finance'):
            state=service.verify(record,rows,attachments)
        self.assertEqual(state['status'],'reviewed');self.assertTrue(state['internal_review_complete'])
        self.assertEqual(len(state['decisions']),3)
        for flag in ('statutorily_certified','chief_executive_approved','form_issued','cash_available'):
            self.assertIs(state[flag],False)
        for actor in self.reviewers.values():
            self.assertEqual(service.snapshot(record,actor,export=True),state)
        with self.assertRaises(ValidationError):first.save()
        with self.assertRaises(ValidationError):first.delete()
        self.assertEqual(packages.snapshot(record,self.preparer)['payload'],original)
        self.assertEqual(JournalEntry.objects.count(),before)

    def test_roles_independence_explicit_checks_uat_and_revoked_source_permission(self):
        record=self.retain()
        with self.assertRaises(PermissionDenied):self.decide_package(record,actor=self.preparer)
        permission=Permission.objects.get(content_type__app_label='budget',codename='review_form1_package_budget')
        self.preparer.user_permissions.add(permission)
        with self.assertRaises(ValidationError):self.decide_package(record,actor=self.preparer)
        checks={key:dict(verified=True,basis='Synthetic explicit basis') for key in service.CHECKS['budget']}
        checks['stock_calendar']['verified']=False
        with self.assertRaises(ValidationError):self.decide_package(record,checks=checks)
        checks['stock_calendar']['verified']='true'
        with self.assertRaises(ValidationError):self.decide_package(record,checks=checks)
        self.treasurer.user_permissions.add(Permission.objects.get(
            content_type__app_label='budget',codename='review_form1_package_budget'))
        with self.assertRaises(ValidationError):self.decide_package(record,actor=self.treasurer)
        group,_=Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP);self.reviewer.groups.add(group)
        with self.assertRaises(PermissionDenied):self.decide_package(record)
        self.assertEqual(service.snapshot(record,self.reviewer)['status'],'prepared')
        self.reviewer.groups.remove(group)
        source=Permission.objects.get(content_type__app_label='budget',codename='view_budget_receipt_forecasts')
        self.treasurer.user_permissions.remove(source)
        with self.assertRaises(PermissionDenied):self.decide_package(record,'treasury')
        self.assertEqual(Form1PackageDecision.objects.count(),0)
        self.treasurer.user_permissions.add(source)
        first=self.decide_package(record)
        with self.assertRaises(ValidationError):self.decide_package(record)
        self.assertEqual(Form1PackageDecision.objects.count(),1)
        self.assertEqual(service.snapshot(record,self.checker)['decisions'][0]['checksum'],first.payload_checksum)

    def test_stale_package_and_forecast_return_preserve_decisions_and_rehashed_corruption_fails(self):
        record=self.retain();original=deepcopy(record.payload);first=self.decide_package(record)
        successor=self.retain(expected_latest=1)
        with self.assertRaisesMessage(ValidationError,'latest'):self.decide_package(record,'accounting')
        self.decide_package(record,'accounting',approve=False)
        history=service.snapshot(record,self.treasurer)
        self.assertEqual(history['status'],'returned');self.assertEqual(history['decisions'][0]['checksum'],first.payload_checksum)
        with self.assertRaises(ValidationError):self.decide_package(record,'treasury')
        self.prepare_forecast(expected_latest=1)
        with self.assertRaisesMessage(ValidationError,'latest'):self.decide_package(successor)
        returned=self.decide_package(successor,'treasury',approve=False)
        self.assertIs(returned.payload['observation']['source_current'],None)
        self.assertEqual(packages.snapshot(record,self.reviewer)['payload'],original)
        changed=deepcopy(returned.payload);changed['observation']['source_current']=True
        Form1PackageDecision.objects.filter(pk=returned.pk).update(payload=changed,payload_checksum=checksum(changed))
        with self.assertRaises(ValidationError):service.snapshot(successor,self.reviewer)

    def test_missing_policy_cannot_be_approved_by_checkboxes_but_can_be_returned(self):
        ph,documents=self.ph_draft(attach=False)
        envelope=self.assembled(philhealth_source=ph,documents=documents)
        record=self.retain(envelope=envelope,documents=documents)
        self.assertFalse(envelope['payload']['calculation_coverage_complete'])
        for role in self.reviewers:
            with self.assertRaisesMessage(ValidationError,'complete'):self.decide_package(record,role)
        self.assertEqual(Form1PackageDecision.objects.count(),0)
        self.decide_package(record,'budget',approve=False)
        self.assertEqual(service.snapshot(record,self.checker)['status'],'returned')

    def test_nonzero_overlap_and_shf_expense_stay_pending_despite_attached_policy(self):
        from . import form1_philhealth as ph
        body=self.ph_source['payload']
        parts=[{key:row[key] for key in ph.PART_FIELDS} for row in body['parts']]
        original={row['key']:row for row in body['inventory']['payload']['catalog']}
        receipt=next(row for row in parts if original[row['source']]['kind']=='receipt'
            and money(row['amount'])>0)
        expense=next(row for row in parts if original[row['source']]['kind']=='expense'
            and original[row['source']]['entity']==original[receipt['source']]['entity']
            and money(row['amount'])>=money(receipt['amount']))
        expense['treatment']='shf';receipt['treatment']='claimed_overlap';receipt['counterpart']=expense['source']
        pending=ph.propose(body['inventory'],parts,body['coverage'],
            coverage_reference=body['coverage_reference'],documents=body['documents'])
        envelope=self.assembled(philhealth_source=pending)
        self.assertFalse(envelope['payload']['calculation_coverage_complete'])
        self.assertTrue(any(member['pending_overlap_or_treatment'][column]
            for member in pending['payload']['members'] for column in ph.components.SOURCE_COLUMNS))
        record=self.retain(envelope=envelope)
        with self.assertRaisesMessage(ValidationError,'complete'):self.decide_package(record,'accounting')
        self.decide_package(record,'accounting',approve=False)
        self.assertEqual(service.snapshot(record,self.treasurer)['status'],'returned')
