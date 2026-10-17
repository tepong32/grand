from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import Barrier, Event
from unittest import skipUnless
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db import connection, close_old_connections, connections
from django.test import TransactionTestCase, Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from inventory import property_determinations as properties
from inventory.models import PropertyDetermination
from accounting.models import Fund
from inventory_finance import property_links as service
from inventory_finance.models import PropertyFinanceLink as Link
from . import test_grand_property_links as fixtures


@skipUnless(connection.vendor == "mysql", "Native MySQL row locks required")
class PropertyLinkRaceTests(TransactionTestCase):
    databases = {"default", "finance"}

    def setUp(self):
        fixtures.PropertyLinkTests.setUpTestData.__func__(type(self))
        fixtures.PropertyLinkTests.setUp(self)
        row = fixtures.PropertyLinkTests.request(self)
        self.row = fixtures.PropertyLinkTests.propose(self, row)

    def test_review_and_withdraw_keep_one_transition(self):
        barrier = Barrier(2)
        def worker(action):
            close_old_connections()
            try:
                actor = get_user_model().objects.get(pk=self.checker.pk if action == "approve" else self.clerk.pk)
                barrier.wait(timeout=10)
                try:
                    service.decide(actor=actor, link_id=self.row.public_id, expected_version=2,
                        action=action, reason="Competing decision")
                    return "decided"
                except ValidationError:
                    return "stale"
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(list(pool.map(worker, ("approve", "withdraw"))), ["decided", "stale"])
        row = Link.objects.get(pk=self.row.pk)
        self.assertEqual(row.state_version, 3)
        self.assertEqual(row.events.count(), 3)
        service.verify(row)

    def test_property_successor_and_approval_serialize_on_asset(self):
        data = {name: getattr(self.determination, name) for name in properties.CONTENT_FIELDS}
        data["reference"] = "SUCCESSOR-PROPERTY"
        successor = properties.record(actor=self.clerk, asset=self.asset, request_id=uuid4(),
            expected_source=properties.source_basis(self.asset), expected_predecessor=str(self.determination.public_id),
            data=data, upload=SimpleUploadedFile("successor.pdf", b"%PDF-successor"))
        barrier = Barrier(2)
        def worker(action):
            close_old_connections()
            try:
                actor = get_user_model().objects.get(pk=self.checker.pk if action == "associate" else self.reviewer.pk)
                barrier.wait(timeout=10)
                if action == "verify":
                    properties.decide(actor=actor, row=PropertyDetermination.objects.select_related("asset").get(pk=successor.pk),
                        expected_version=1, action="verify", note="Verified successor source")
                    return "verified"
                try:
                    service.decide(actor=actor, link_id=self.row.public_id, expected_version=2,
                        action="approve", reason="Concurrent source review")
                    return "approved_before_successor"
                except ValidationError:
                    return "stale"
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(worker, ("verify", "associate")))
        self.assertEqual(outcomes[0], "verified")
        self.assertIn(outcomes[1], ("stale", "approved_before_successor"))
        row = Link.objects.get(pk=self.row.pk)
        service.verify(row)
        with self.assertRaises(ValidationError):
            service.current(row, self.checker)

    def test_native_setup_archive_waits_for_association_commit_then_marks_current_stale(self):
        self._assert_native_setup_wait("archive")

    def test_native_setup_edit_waits_for_association_commit_then_marks_current_stale(self):
        self._assert_native_setup_wait("edit")

    def _assert_native_setup_wait(self, mode):
        self.proposer.user_permissions.add(Permission.objects.get(content_type__app_label="accounting", codename="manage_accounting_setup"))
        approval_ready, release_approval, archive_entered = Event(), Event(), Event()
        original_save, original_fund_save = service._save, Fund.save
        def retained_save(row, actor, action):
            result = original_save(row, actor, action)
            if action == "approved":
                approval_ready.set()
                if not release_approval.wait(15):
                    raise RuntimeError("Test approval barrier timed out")
            return result
        def fund_save(instance, *args, **kwargs):
            if instance.pk == self.fund.pk and (not instance.is_active or instance.name == "Amended native name"):
                archive_entered.set()
            return original_fund_save(instance, *args, **kwargs)
        def approve():
            close_old_connections()
            try:
                return service.decide(actor=get_user_model().objects.get(pk=self.checker.pk), link_id=self.row.public_id,
                    expected_version=2, action="approve", reason="Native lock proof").status
            finally:
                connections.close_all()
        def archive():
            close_old_connections()
            try:
                client = Client()
                client.force_login(get_user_model().objects.get(pk=self.proposer.pk))
                if mode == "edit":
                    return client.post(reverse("accounting:setup_edit", args=("funds", self.fund.pk)), {
                        "code": self.fund.code, "name": "Amended native name", "is_active": "on",
                        "change_reason": "Native source concurrency validation"}).status_code
                return client.post(reverse("accounting:setup_toggle", args=("funds", self.fund.pk))).status_code
            finally:
                connections.close_all()
        with patch.object(service, "_save", retained_save), patch.object(Fund, "save", fund_save):
            with ThreadPoolExecutor(max_workers=2) as pool:
                approval = pool.submit(approve)
                try:
                    self.assertTrue(approval_ready.wait(15))
                    toggle = pool.submit(archive)
                    self.assertTrue(archive_entered.wait(15))
                    # Give the UPDATE a real execution window while the approval
                    # still holds its Finance lock; scheduling alone is not proof.
                    with self.assertRaises(TimeoutError):
                        toggle.result(timeout=0.25)
                finally:
                    release_approval.set()
                self.assertEqual(approval.result(timeout=15), "approved")
                self.assertEqual(toggle.result(timeout=15), 302)
        changed = Fund.objects.get(pk=self.fund.pk)
        if mode == "archive":
            self.assertFalse(changed.is_active)
        else:
            self.assertEqual(changed.name, "Amended native name")
        row = Link.objects.get(pk=self.row.pk)
        service.verify(row)
        with self.assertRaises(ValidationError):
            service.current(row, self.checker)
