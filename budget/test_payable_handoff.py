from datetime import date
from decimal import Decimal
from django.contrib.auth.models import Group, Permission
from django.test import TestCase
from django.urls import reverse
from finance.models import FinanceConfigurationRelease
from vouchers.models import VoucherCase
from . import tests as fixtures
from .models import ObligationMovement, PayableObligationAllocation
from .services import transition_obligation_request
from .payable_handoff import payable_handoff


class PayableHandoffTests(TestCase):
    databases = {'default', 'finance'}
    setUpTestData = classmethod(fixtures.AnnualBudgetPreparationTests.setUpTestData.__func__)
    employee = classmethod(fixtures.AnnualBudgetPreparationTests.employee.__func__)
    for _name in ('make_call', 'add_ceiling', 'add_line', 'make_authorized_appropriation',
                  'make_allotment_order', 'add_allotment_line', 'make_executable_authority',
                  'make_obligation_request', 'add_obligation_line'):
        locals()[_name] = getattr(fixtures.AnnualBudgetPreparationTests, _name)

    def setUp(self):
        authority = self.make_executable_authority()
        self.obligation = self.make_obligation_request(authority)
        self.add_obligation_line(self.obligation)
        transition_obligation_request(self.obligation, 'submit', self.requester)
        self.obligation = transition_obligation_request(self.obligation, 'certify', self.certifier,
            'Synthetic independent certification', 'OBR-HANDOFF-001')
        self.requester.user_permissions.add(Permission.objects.get(content_type__app_label='vouchers', codename='initiate_payable_case'))
        self.release = FinanceConfigurationRelease.objects.create(department=self.accounting_office,
            code='handoff', version=1, title='Synthetic approved setup', fiscal_year=2026,
            status='active', effective_from=date(2026,1,1), created_by=self.certifier)
        self.url = reverse('budget:obligation_detail', args=[self.obligation.public_id])
        self.intake_url = reverse('vouchers:case_create') + '?obligation=' + str(self.obligation.public_id)

    def case(self, reference='CASE-HANDOFF', *, primary=True, department=None):
        return VoucherCase.objects.create(reference_code=reference, transaction_type='synthetic',
            requesting_department=department or self.requesting_office, current_department=self.accounting_office,
            configuration_release=self.release, payee_name='Synthetic Supplier', particulars='Synthetic evidence',
            authoritative_obligation_public_id=self.obligation.public_id if primary else None,
            obligation_binding_status=VoucherCase.BINDING_PENDING,
            current_stage=VoucherCase.PAYABLE_PREPARATION, created_by=self.requester)

    def allocate(self, case, amount):
        return PayableObligationAllocation.objects.create(department_id=self.budget_office.pk,
            department_label=self.budget_office.name, obligation=self.obligation,
            voucher_case_public_id=case.public_id, voucher_reference_snapshot=case.reference_code,
            relationship_type='partial', allocated_amount=Decimal(amount), obligation_amount_snapshot=Decimal('10000'),
            obligation_checksum_snapshot=self.obligation.snapshot_checksum, change_reason='Synthetic allocation',
            recorded_by_id=self.requester.pk, recorded_by_label=self.requester.username)

    def test_source_preselection_is_scoped_and_read_only(self):
        self.client.force_login(self.requester)
        before = (VoucherCase.objects.count(), ObligationMovement.objects.count(), PayableObligationAllocation.objects.count())
        response = self.client.get(self.url)
        self.assertContains(response, 'Prepare payable from this OBR')
        response = self.client.get(self.intake_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['form'].initial['authoritative_obligation'], self.obligation.pk)
        self.assertNotIn('claim_amount', response.context['form'].initial)
        self.assertContains(response, 'OBR-HANDOFF-001')
        self.assertEqual(before, (VoucherCase.objects.count(), ObligationMovement.objects.count(), PayableObligationAllocation.objects.count()))
        self.assertEqual(self.client.get(reverse('vouchers:case_create') + '?obligation=invalid').status_code, 404)
        self.outsider.user_permissions.add(Permission.objects.get(content_type__app_label='vouchers', codename='initiate_payable_case'))
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(self.intake_url).status_code, 404)

    def test_pending_and_secondary_links_preserve_scope_and_capacity(self):
        pending = self.case()
        secondary = self.case('SECONDARY', primary=False)
        self.allocate(secondary, '4000')
        self.case('FOREIGN-PRIVATE', department=self.other_office)
        self.client.force_login(self.requester)
        response = self.client.get(self.url)
        self.assertContains(response, pending.reference_code)
        self.assertContains(response, secondary.reference_code)
        self.assertNotContains(response, 'FOREIGN-PRIVATE')
        self.assertContains(response, 'do not replace it with a duplicate claim')
        self.assertEqual(response.context['payable_handoff']['remaining'], Decimal('6000'))
        self.assertEqual(response.context['payable_handoff']['page'].paginator.count, 2)
        self.client.force_login(self.certifier)
        self.assertNotContains(self.client.get(self.url), pending.reference_code)
        self.assertContains(self.client.get(self.url), 'require Voucher Workbench access')

    def test_fully_allocated_and_uat_cannot_prepare(self):
        self.allocate(self.case(), '10000')
        self.client.force_login(self.requester)
        self.assertNotContains(self.client.get(self.url), 'Prepare payable from this OBR')
        self.assertEqual(self.client.get(self.intake_url).status_code, 404)
        self.requester.groups.add(Group.objects.get_or_create(name='Finance UAT Viewer')[0])
        self.assertEqual(self.client.get(reverse('vouchers:case_create')).status_code, 403)
        self.assertEqual(self.client.post(reverse('vouchers:case_create'), {}).status_code, 403)
        self.assertNotContains(self.client.get(self.url), 'Prepare payable from this OBR')

    def test_complete_link_retrieval_has_pagination(self):
        for i in range(23):
            self.case(f'PAGED-{i:02d}')
        page = payable_handoff(self.obligation, self.requester)
        self.assertEqual(page['page'].paginator.count, 23)
        self.assertEqual(len(page['rows']), 20)
        next_page = payable_handoff(self.obligation, self.requester, 2)
        self.assertEqual(len(next_page['rows']), 3)
        self.assertFalse({row['case'].pk for row in page['rows']} & {row['case'].pk for row in next_page['rows']})
