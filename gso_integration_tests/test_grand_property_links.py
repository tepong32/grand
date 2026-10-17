"""Native identities and two-store property association boundaries."""
from datetime import timedelta
from uuid import uuid4
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission, Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connections
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from django.urls import reverse
from accounting.models import Fund, LedgerAccount
from departments.models import Department
from profiles.models import EmployeeProfile
from vouchers.roles import FINANCE_UAT_VIEWER_GROUP
from inventory import property_determinations as properties
from inventory_finance import property_links as service
from inventory_finance.models import PropertyFinanceLink as Link
from . import test_grand_property
from . import test_grand_journal_mappings, test_grand_attribution


class PropertyLinkTests(TestCase):
    databases = {"default", "finance"}

    @classmethod
    def setUpTestData(cls):
        test_grand_property.GrandPropertyTests.setUpTestData.__func__(cls)
        cls.finance = Department.objects.create(name="Accounting", slug="accounting")
        cls.proposer = get_user_model().objects.create_user(username="property-finance-proposer", email="pfp@example.test")
        cls.checker = get_user_model().objects.create_user(username="property-finance-checker", email="pfc@example.test")
        cls.finance_uat = get_user_model().objects.create_user(username="property-finance-uat", email="pfu@example.test")
        for actor in (cls.proposer, cls.checker, cls.finance_uat):
            EmployeeProfile.objects.filter(user=actor).update(assigned_department=cls.finance)
            actor.refresh_from_db()
            actor.user_permissions.add(Permission.objects.get(content_type__app_label="accounting", codename="view_general_ledger"))
        cls.finance_uat.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        for actor in (cls.clerk, cls.proposer, cls.checker, cls.finance_uat, cls.outsider, cls.viewer):
            actor.user_permissions.add(*Permission.objects.filter(content_type__app_label="inventory_finance", codename__endswith="_propertyfinancelink"))
        owner = dict(department_id=cls.finance.pk, department_label=cls.finance.name)
        cls.fund = Fund.objects.create(**owner, code="GF-PROP", name="Property test fund")
        cls.account = LedgerAccount.objects.create(**owner, code="PROP-EXP", title="Supplied expense", account_type="expense", normal_balance="debit")

    def setUp(self):
        test_grand_property.GrandPropertyTests.setUp(self)
        self.determination = test_grand_property.GrandPropertyTests.record(self)
        self.determination = properties.decide(actor=self.reviewer, row=self.determination,
            expected_version=1, action="verify", note="Supplied document checked")

    def request(self, **changes):
        args = dict(actor=self.clerk, determination_id=self.determination.public_id,
            finance_department_id=self.finance.pk, reason="Please identify native dimensions", request_id=uuid4(),
            expected_property=service.property_basis(self.determination), expected_predecessor=None)
        args.update(changes)
        return service.request_link(**args)

    def propose(self, row, **changes):
        args = dict(actor=self.proposer, link_id=row.public_id, expected_version=row.state_version,
            as_of=timezone.localdate(), fund_id=self.fund.public_id, account_id=self.account.public_id,
            reason="Checked supplied authority", expected_dimensions=service.dimensions(actor=self.proposer,
                owner_id=self.finance.pk, as_of=timezone.localdate(), fund_id=self.fund.public_id, account_id=self.account.public_id))
        args.update(changes)
        return service.propose(**args)

    def decide(self, row, **changes):
        args = dict(actor=self.checker, link_id=row.public_id, expected_version=row.state_version,
            action="approve", reason="Independent association review")
        args.update(changes)
        return service.decide(**args)

    def test_distinct_offices_legacy_no_voucher_and_no_finance_writes(self):
        original = self.asset.assigned_department_id
        with CaptureQueriesContext(connections["finance"]) as queries:
            row = self.request()
            self.assertTrue(service.visible(self.proposer).filter(pk=row.pk).exists())
            self.assertFalse(properties.visible(self.proposer).filter(pk=self.determination.pk).exists())
            row = self.propose(row)
            row = self.decide(row)
            service.verify(row)
            self.assertEqual(service.current(row, self.checker)["fund"]["uuid"], str(self.fund.public_id))
        self.assertFalse(any(q["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for q in queries))
        self.assertEqual(row.status, "approved")
        self.assertEqual(row.events.count(), 3)

        self.assertIsNone(row.journal_mapping_id)
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.assigned_department_id, original)

    def test_scope_grants_uat_and_independent_review(self):
        for actor in (self.outsider, self.super_no_grant, self.viewer, self.proposer):
            with self.subTest(actor=actor.username), self.assertRaises(PermissionDenied):
                self.request(actor=actor)
        row = self.request()
        for actor in (self.outsider, self.super_no_grant):
            self.assertFalse(service.visible(actor).exists())
        with self.assertRaises(PermissionDenied):
            self.propose(row, actor=self.finance_uat)
        row = self.propose(row)
        with self.assertRaises(PermissionDenied):
            self.decide(row, actor=self.proposer)
        with self.assertRaises(PermissionDenied):
            self.decide(row, actor=self.finance_uat)
        self.checker.user_permissions.remove(Permission.objects.get(content_type__app_label="accounting", codename="view_general_ledger"))
        with self.assertRaises(PermissionDenied):
            self.decide(row)

    def test_exact_request_replay_pending_uniqueness_and_replacement(self):
        request_id = uuid4()
        row = self.request(request_id=request_id)
        self.assertEqual(self.request(request_id=request_id).pk, row.pk)
        with self.assertRaises(ValidationError):
            self.request(request_id=request_id, reason="Changed")
        with self.assertRaises(ValidationError):
            self.request()
        row = self.decide(row, action="withdraw", actor=self.clerk)
        replacement = self.request(expected_predecessor=str(row.public_id))
        self.assertEqual(replacement.predecessor_id, row.pk)
        self.assertEqual(self.request(request_id=request_id).pk, row.pk)
        self.assertEqual(Link.objects.count(), 2)

    def test_stale_dimensions_block_approval_but_allow_gso_withdrawal(self):
        row = self.propose(self.request())
        Fund.objects.filter(pk=self.fund.pk).update(name="Changed native name")
        with self.assertRaisesMessage(ValidationError, "source changed"):
            self.decide(row)
        row = self.decide(row, action="withdraw", actor=self.clerk)
        self.assertEqual(row.status, "withdrawn")
        service.verify(row)

    def test_dimension_eligibility_owner_date_and_account_type(self):
        for changes in ({"is_active": False}, {"effective_from": timezone.localdate()+timedelta(days=1)}, {"department_id": self.other.pk}):
            Fund.objects.filter(pk=self.fund.pk).update(**changes)
            with self.assertRaises(ValidationError):
                service.dimensions(actor=self.proposer, owner_id=self.finance.pk, as_of=timezone.localdate(),
                    fund_id=self.fund.public_id, account_id=self.account.public_id)
            Fund.objects.filter(pk=self.fund.pk).update(is_active=True, effective_from=None, department_id=self.finance.pk)
        for changes in ({"account_type": "liability"}, {"allow_posting": False}):
            LedgerAccount.objects.filter(pk=self.account.pk).update(**changes)
            with self.assertRaises(ValidationError):
                service.dimensions(actor=self.proposer, owner_id=self.finance.pk, as_of=timezone.localdate(),
                    fund_id=self.fund.public_id, account_id=self.account.public_id)
            LedgerAccount.objects.filter(pk=self.account.pk).update(account_type="expense", allow_posting=True)

    def test_property_change_history_tamper_and_event_failure(self):
        with patch.object(service, "event", side_effect=RuntimeError("Injected event failure")):
            with self.assertRaises(RuntimeError):
                self.request()
        self.assertEqual(Link.objects.count(), 0)
        row = self.propose(self.request())
        type(self.asset).objects.filter(pk=self.asset.pk).update(asset_name="Changed material fact")
        with self.assertRaises(ValidationError):
            self.decide(row)
        row = self.decide(row, action="withdraw", actor=self.clerk)
        Link.objects.filter(pk=row.pk).update(request_reason="Tampered")
        row.refresh_from_db()
        with self.assertRaises(ValidationError):
            service.verify(row)

    def test_stale_review_and_immutable_proposal(self):
        row = self.propose(self.request())
        row = self.decide(row)
        with self.assertRaises(ValidationError):
            self.decide(row, expected_version=2)
        row.proposal_reason = "Changed"
        with self.assertRaises(ValidationError):
            row.save()
        row._workflow_write = True
        with self.assertRaises(ValidationError):
            row.save()
        with self.assertRaises(ValidationError):
            row.events.first().delete()

    def test_signed_http_sharing_proposal_review_and_packet_scope(self):
        self.client.force_login(self.clerk)
        url = reverse("inventory_finance:property-link-request", args=[self.determination.public_id])
        page = self.client.get(url)
        self.assertContains(page, "shares this property's retained facts")
        token = page.context["form"].initial["source_token"]
        payload = {"finance_department": self.finance.pk, "reason": "Share supplied source", "source_token": token+"bad"}
        self.assertEqual(self.client.post(url, payload).status_code, 200)
        self.assertFalse(Link.objects.exists())
        payload["source_token"] = token
        self.assertEqual(self.client.post(url, payload).status_code, 302)
        self.assertEqual(self.client.post(url, payload).status_code, 302)
        self.assertEqual(Link.objects.count(), 1)
        row = Link.objects.get()
        detail = reverse("inventory_finance:property-link-detail", args=[row.public_id])
        packet = reverse("inventory_finance:property-link-evidence", args=[row.public_id])
        self.client.force_login(self.proposer)
        self.assertEqual(self.client.get(reverse("inventory:property-evidence", args=[self.determination.pk])).status_code, 404)
        response = self.client.get(packet)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertTrue(b"".join(response.streaming_content).startswith(b"%PDF"))
        page = self.client.post(detail, {"action": "preview", "proposal-as_of": timezone.localdate().isoformat(),
            "proposal-fund": self.fund.pk, "proposal-account": self.account.pk, "proposal-reason": "Source matched"})
        self.assertContains(page, "Confirm proposal")
        confirm = {"action": "propose", "proposal_token": page.context["preview_token"]}
        self.assertEqual(self.client.post(detail, confirm).status_code, 302)
        self.assertEqual(self.client.post(detail, confirm).status_code, 403)
        self.assertNotContains(self.client.get(detail), "Approve association</button>")
        self.client.force_login(self.checker)
        self.assertContains(self.client.get(detail), "Approve association</button>")
        self.assertEqual(self.client.post(detail, {"action": "approve", "decision-expected_version": 2, "decision-reason": "Independent check"}).status_code, 302)
        self.assertContains(self.client.get(detail), "match this association at this read")
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(detail).status_code, 404)
        self.assertEqual(self.client.get(packet).status_code, 404)
        self.client.force_login(self.finance_uat)
        self.assertContains(self.client.get(detail), "Retained Finance proposal")
        self.assertEqual(self.client.post(detail, {"action": "withdraw", "decision-expected_version": 3, "decision-reason": "Denied"}).status_code, 403)

    def test_current_reloads_asset_and_retains_approval_when_stale(self):
        row = self.decide(self.propose(self.request()))
        service.current(row, self.checker)
        type(self.asset).objects.filter(pk=self.asset.pk).update(asset_name="Later correction")
        with self.assertRaises(ValidationError):
            service.current(row, self.checker)
        row.refresh_from_db()
        self.assertEqual(row.status, "approved")
        self.assertEqual(row.events.count(), 3)


    def test_acquisition_successor_preserves_link_history_but_requires_new_association(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        row = self.decide(self.propose(self.request()))
        retained = list(row.events.values('snapshot', 'checksum'))
        data = {name: getattr(self.determination, name) for name in properties.CONTENT_FIELDS}
        data.update(acquisition_reference='SUPPLIED-IAR-01', acquisition_date=timezone.localdate(),
                    receipt_item_number='26-01-01', reason='Retain additional supplied acquisition facts')
        with CaptureQueriesContext(connections['finance']) as queries:
            successor = properties.record(actor=self.clerk, asset=self.asset, request_id=uuid4(),
                expected_source=properties.source_basis(self.asset),
                expected_predecessor=str(self.determination.public_id), data=data,
                upload=SimpleUploadedFile('acquisition.pdf', b'%PDF-synthetic acquisition packet'))
            properties.decide(actor=self.reviewer, row=successor, expected_version=1,
                action='verify', note='Checked acquisition source')
        self.assertEqual(len(queries), 0)
        service.verify(row)
        self.assertEqual(list(row.events.values('snapshot', 'checksum')), retained)
        with self.assertRaises(ValidationError):
            service.current(row, self.checker)


class PropertyJournalLinkTests(TestCase):
    databases = {"default", "finance"}

    @classmethod
    def setUpTestData(cls):
        test_grand_journal_mappings.MappingTests.setUpTestData.__func__(cls)
        from inventory.models import Asset, ReceivingLine
        from inventory_finance.services import close_attribution
        cls.asset = Asset.objects.create(department_id=cls.gso.pk, asset_name="Journal-linked property", unit_cost=100)
        ReceivingLine.objects.filter(pk=cls.receipt_line.pk).update(registered_asset=cls.asset)
        # Replace the old synthetic claim basis explicitly after materialization.
        close_attribution(actor=cls.reviewer, attribution_id=cls.claim.public_id,
            expected_version=cls.claim.state_version, action="withdraw", reason="Synthetic materialization before new support")
        fixture = cls()
        cls.claim = test_grand_attribution.AttributionTests.propose(fixture, amount="100.00")
        cls.claim = test_grand_attribution.AttributionTests.approve(fixture, cls.claim)
        cls.property_checker = get_user_model().objects.create_user(username="property-source-checker", email="psc@example.test")
        EmployeeProfile.objects.filter(user=cls.property_checker).update(assigned_department=cls.gso)
        cls.property_checker.refresh_from_db()
        for actor in (cls.clerk, cls.property_checker):
            actor.user_permissions.add(*Permission.objects.filter(content_type__app_label="inventory", codename__in=(
                "view_asset", "view_property_determination", "record_property_determination", "review_property_determination")))
        for actor in (cls.clerk, cls.reviewer, cls.mapping_reviewer):
            actor.user_permissions.add(*Permission.objects.filter(content_type__app_label="inventory_finance", codename__endswith="_propertyfinancelink"))

    def setUp(self):
        test_grand_property.GrandPropertyTests.setUp(self)
        self.asset.refresh_from_db()
        self.determination = test_grand_property.GrandPropertyTests.record(self)
        self.determination = properties.decide(actor=self.property_checker, row=self.determination,
            expected_version=1, action="verify", note="Supplied source reviewed")

    def test_exact_materialized_asset_mapping_and_withdrawn_support(self):
        from inventory_finance import journal_mappings
        mapping = test_grand_journal_mappings.MappingTests.propose(self)
        mapping = test_grand_journal_mappings.MappingTests.decide(self, mapping)
        row = service.request_link(actor=self.clerk, determination_id=self.determination.public_id,
            finance_department_id=self.finance.pk, reason="Link exact recognition source", request_id=uuid4(),
            expected_property=service.property_basis(self.determination), expected_predecessor=None)
        fund = self.entry.fund
        account = self.entry.lines.get(sequence=1).account
        basis = service.dimensions(actor=self.reviewer, owner_id=self.finance.pk, as_of=timezone.localdate(),
            fund_id=fund.public_id, account_id=account.public_id)
        row = service.propose(actor=self.reviewer, link_id=row.public_id, expected_version=1,
            as_of=timezone.localdate(), fund_id=fund.public_id, account_id=account.public_id,
            mapping_id=mapping.public_id, reason="Exact approved support", expected_dimensions=basis)
        row = service.decide(actor=self.mapping_reviewer, link_id=row.public_id, expected_version=2,
            action="approve", reason="Independently checked")
        self.assertEqual(row.mapping_snapshot["uuid"], str(mapping.public_id))
        service.current(row, self.mapping_reviewer)
        journal_mappings.decide(actor=self.mapping_reviewer, mapping_id=mapping.public_id,
            expected_version=mapping.state_version, action="withdraw", note="Later source correction")
        with self.assertRaises(ValidationError):
            service.current(row, self.mapping_reviewer)
        row = service.decide(actor=self.clerk, link_id=row.public_id, expected_version=3,
            action="withdraw", reason="Retain obsolete association")
        self.assertEqual(row.status, "withdrawn")
