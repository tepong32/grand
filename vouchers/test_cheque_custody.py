from unittest import skipUnless
from django.contrib.auth.models import Permission, Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connections, IntegrityError, transaction
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from tracepoint.services import create_packet,add_packet_item
from tracepoint.credentials import issue_daily_credential
from tracepoint.handoffs import start_scan_session,attach_recipient_code,confirm_handoff
from . import test_cheque_returns as fixtures
from .test_cheque_redemptions import RedemptionTests
from .models import CollectionChequeCustodyLink as Link
from . import cheque_custody as custody
from .collection_outputs import generate,content


class CustodyTests(TestCase):
    databases = {'default','finance'}
    setUpTestData = classmethod(fixtures.ReturnTests.setUpTestData.__func__)
    employee = classmethod(fixtures.ReturnTests.employee.__func__)
    cheque_receipt = fixtures.ReturnTests.cheque_receipt
    deposit = fixtures.ReturnTests.deposit
    post_source = fixtures.ReturnTests.post_source
    sources = fixtures.ReturnTests.sources
    bank_return = fixtures.ReturnTests.bank_return
    returned_source = RedemptionTests.returned_source

    def setUp(self):
        fixtures.ReturnTests.setUp(self)
        self.treasury_user.user_permissions.add(Permission.objects.get(codename='link_collection_custody'))
        self.treasury_user.user_permissions.add(*Permission.objects.filter(content_type__app_label='tracepoint',
            codename__in=('view_tracepoint_workspace','prepare_tracked_packets','print_packet_labels')))
        self.checker = self.employee('custody.checker',self.treasury,'view_collection_register','link_collection_custody')
        self.checker.user_permissions.add(*Permission.objects.filter(content_type__app_label='tracepoint',
            codename__in=('view_tracepoint_workspace','resolve_tracepoint_exceptions','view_restricted_tracepoint')))

    def packet_item(self):
        packet = create_packet(actor=self.treasury_user,title='Synthetic returned cheque custody',
            contents_manifest='Actual item is identified in the authorized Treasury source.',
            final_destination_department=self.treasury,confidentiality='restricted')
        item = add_packet_item(packet=packet,actor=self.treasury_user,title='Returned cheque and source evidence')
        return packet,item

    def activate(self,packet):
        issued = issue_daily_credential(employee=self.treasury_user)
        scan = start_scan_session(packet=packet,operator=self.treasury_user,idempotency_key='actual-custody')
        attach_recipient_code(session=scan,operator=self.treasury_user,token=issued.token)
        confirm_handoff(session=scan,operator=self.treasury_user,receipt_note='Synthetic physical packet actually received')

    def test_link_is_not_physical_receipt_and_issued_copies_keep_their_state(self):
        source = self.returned_source(); packet,item = self.packet_item()
        row = custody.link(source=source,item=item,actor=self.treasury_user,evidence_reference='Actual instrument identified')
        self.assertEqual(custody.link(source=source,item=item,actor=self.treasury_user,
            evidence_reference='Actual instrument identified').pk,row.pk)
        self.assertFalse(custody.evidence(source,self.treasury_user)['physical_confirmation'])
        output = generate(source=source,actor=self.treasury_user,include_custody=True)
        frozen = content(output,self.treasury_user)
        self.assertIn(b'Physical receipt has not been confirmed',frozen)
        self.activate(packet)
        self.assertTrue(custody.evidence(source,self.treasury_user)['physical_confirmation'])
        self.assertEqual(content(output,self.treasury_user),frozen)
        after = generate(source=source,actor=self.treasury_user,include_custody=True)
        self.assertIn(b'TracePoint holder',content(after,self.treasury_user))

    def test_custody_export_requires_both_authorities_and_withdrawal_preserves_history(self):
        source = self.returned_source(); packet,item = self.packet_item()
        row = custody.link(source=source,item=item,actor=self.treasury_user,evidence_reference='Actual instrument identified')
        financial = generate(source=source,actor=self.validator)
        self.assertTrue(content(financial,self.validator))
        with self.assertRaises(PermissionDenied): custody.evidence(source,self.validator)
        self.client.force_login(self.validator)
        page = self.client.get(reverse('vouchers:collection_detail',args=[source.public_id]))
        self.assertNotContains(page,item.reference_number)
        with self.assertRaises(PermissionDenied): generate(source=source,actor=self.validator,include_custody=True)
        full = generate(source=source,actor=self.treasury_user,include_custody=True)
        with self.assertRaises(PermissionDenied): content(full,self.validator)
        with self.assertRaises((PermissionDenied,ValidationError)):
            custody.withdraw(link=row,actor=self.treasury_user,reason='Self')
        custody.withdraw(link=row,actor=self.checker,reason='Wrong item association; physical history remains')
        row.refresh_from_db(); self.assertIsNotNone(row.withdrawn_at)
        self.assertNotContains(self.client.get(reverse('vouchers:collection_detail',args=[source.public_id])),row.withdrawal_reason)
        replacement = custody.link(source=source,item=item,actor=self.treasury_user,evidence_reference='Rechecked source identity')
        self.assertEqual(replacement.version,2)
        self.assertTrue(content(full,self.treasury_user))

    def test_web_link_uat_denial_and_generated_active_item_identity(self):
        from .roles import FINANCE_UAT_VIEWER_GROUP
        source = self.returned_source(); packet,item = self.packet_item()
        self.client.force_login(self.treasury_user)
        response = self.client.post(reverse('vouchers:cheque_custody_create',args=[source.public_id]),
            {'item':item.pk,'evidence_reference':'Actual physical identity verified'})
        self.assertEqual(response.status_code,302)
        self.assertContains(self.client.get(response.url),'Physical receipt has not been confirmed')
        with self.assertRaises(IntegrityError),transaction.atomic():
            Link.objects.create(source=source.return_receipt,item=item,version=1,snapshot={},checksum='x',linked_by=self.treasury_user)
        self.treasury_user.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        with self.assertRaises(PermissionDenied):
            custody.link(source=source,item=item,actor=self.treasury_user,evidence_reference='UAT mutation')


@skipUnless(connections['finance'].vendor == 'mysql','Requires native MySQL row locks')
class CustodyConcurrencyTests(TransactionTestCase):
    databases = {'default','finance'}
    employee = classmethod(CustodyTests.employee.__func__)
    cheque_receipt = CustodyTests.cheque_receipt
    deposit = CustodyTests.deposit
    post_source = CustodyTests.post_source
    sources = CustodyTests.sources
    bank_return = CustodyTests.bank_return
    returned_source = CustodyTests.returned_source
    packet_item = CustodyTests.packet_item
    race = fixtures.ReturnConcurrencyTests.race

    def setUp(self):
        CustodyTests.setUpTestData.__func__(type(self))
        CustodyTests.setUp(self)

    def test_competing_custody_items_keep_one_source_association(self):
        source = self.returned_source(); packet,first = self.packet_item()
        second = add_packet_item(packet=packet,actor=self.treasury_user,title='Another actual item')
        def compete(number):
            custody.link(source=source,item=first if number == 1 else second,actor=self.treasury_user,
                evidence_reference=f'Actual item candidate {number}')
            return 'accepted'
        result = self.race(compete)
        self.assertEqual(result.count('accepted'),1,result)
        self.assertEqual(source.custody_links.filter(withdrawn_at__isnull=True).count(),1)

    def test_cheque_and_voucher_cannot_claim_the_same_item(self):
        from .tests import VoucherWorkflowTests
        from .services import link_tracepoint_item
        source = self.returned_source()
        case = VoucherWorkflowTests.create_case(self,'cheque-custody-case')
        VoucherWorkflowTests.budget_certify(self,case)
        VoucherWorkflowTests.accounting_prepare(self,case)
        case.refresh_from_db()
        packet = create_packet(actor=self.treasury_user,title='Synthetic shared item candidate',
            contents_manifest='Synthetic financial source evidence',final_destination_department=self.accounting,
            final_destination_employee=self.preparer,confidentiality='restricted')
        item = add_packet_item(packet=packet,actor=self.treasury_user,title='One physical item')
        def compete(number):
            if number == 1:
                custody.link(source=source,item=item,actor=self.treasury_user,evidence_reference='Actual cheque identity')
            else:
                link_tracepoint_item(case=case,item=item,actor=self.preparer,
                    expected_version=case.state_version,idempotency_key='same-physical-item')
            return 'accepted'
        result = self.race(compete)
        self.assertEqual(result.count('accepted'),1,result)
        case.refresh_from_db()
        self.assertEqual(int(bool(case.tracepoint_item_id))+Link.objects.filter(item=item,withdrawn_at__isnull=True).count(),1)
