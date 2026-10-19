from uuid import uuid4

from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connections
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from inventory import hr_custody_reviews as workflow
from inventory.models import EmployeeCustodyReview as Review, EmployeeCustodyReviewEvent as Event
from . import test_grand_employee_custody


class GrandHRCustodyReviewTests(TestCase):
    databases = {"default", "finance"}

    def search_people(self, *, inactive=False):
        from django.contrib.auth import get_user_model
        from profiles.models import EmployeeProfile
        from inventory.models import Asset
        people = []
        for number in range(28):
            person = get_user_model().objects.create_user(username=f'hr-page-{number:03}',
                email=f'hr-page-{number:03}@example.test', first_name='Repeated', last_name=f'Custodian{number:03}',
                is_active=not inactive)
            EmployeeProfile.objects.filter(user=person).update(assigned_department=self.other)
            if inactive:
                Asset.objects.create(department_id=self.gso.pk, asset_name=f'Historical custody {number}',
                    custodian_user=person)
            people.append(person)
        return people

    def test_employee_search_active_pages_are_separate_from_retained_review_pages(self):
        from django.urls import reverse
        people = self.search_people()
        self.client.force_login(self.clerk)
        response = self.client.get(reverse('inventory:hr-custody-review-list'),
            {'q': 'hr-page', 'employee_page': 2, 'page': 1})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([person.pk for person in response.context['employees']], [person.pk for person in people[25:]])
        self.assertEqual(response.context['page'].number, 1)
        self.assertContains(response, reverse('inventory:hr-custody-review-create', args=[people[-1].pk]))

    def test_employee_search_inactive_pages_keep_explicit_office_custody_links(self):
        from django.contrib.auth import get_user_model
        from django.urls import reverse
        people = self.search_people(inactive=True)
        unlinked = get_user_model().objects.create_user(username='hr-page-unlinked', email='hr-page-unlinked@example.test', is_active=False)
        self.client.force_login(self.clerk)
        url = reverse('inventory:hr-custody-review-list')
        first = self.client.get(url, {'q': 'hr-page', 'employee_page': 1})
        second = self.client.get(url, {'q': 'hr-page', 'employee_page': 2})
        ids = [person.pk for response in (first, second) for person in response.context['employees']]
        self.assertEqual(ids, [person.pk for person in people])
        self.assertNotIn(unlinked.pk, ids)
        self.assertContains(second, 'Inactive account with custody history')
        self.assertContains(second, 'inactivity does not prove termination')
        self.assertEqual(self.client.get(reverse('inventory:hr-custody-review-create', args=[people[-1].pk])).status_code, 200)

    def test_employee_search_empty_and_uat_reads_do_not_offer_new_case_authority(self):
        from django.db import connections
        from django.test.utils import CaptureQueriesContext
        from django.urls import reverse
        self.search_people()
        self.client.force_login(self.clerk)
        url = reverse('inventory:hr-custody-review-list')
        before = list(Review.objects.values())
        with CaptureQueriesContext(connections['finance']) as finance:
            response = self.client.get(url, {'employee_page': 2})
        self.assertEqual(response.context['employees'], [])
        self.assertEqual(len(finance), 0)
        self.client.force_login(self.viewer)
        response = self.client.get(url, {'q': 'hr-page', 'employee_page': 2})
        self.assertFalse(response.context['can_record'])
        self.assertEqual(response.context['employees'], [])
        self.assertEqual(list(Review.objects.values()), before)

    def setUp(self):
        from tempfile import TemporaryDirectory
        from unittest.mock import patch
        from django.core.files.storage import FileSystemStorage
        storage = TemporaryDirectory()
        self.addCleanup(storage.cleanup)
        storage_patch = patch.object(Review._meta.get_field("file"), "storage", FileSystemStorage(location=storage.name))
        storage_patch.start()
        self.addCleanup(storage_patch.stop)

    @classmethod
    def setUpTestData(cls):
        test_grand_employee_custody.GrandEmployeeCustodyTests.setUpTestData.__func__(cls)
        from profiles.models import EmployeeProfile
        EmployeeProfile.objects.filter(user=cls.no_grant).update(assigned_department=cls.gso)
        cls.no_grant.refresh_from_db()
        permissions = Permission.objects.filter(content_type__app_label="inventory", codename__in=(
            "record_employeecustodyreview", "review_employeecustodyreview"))
        for actor in (cls.clerk, cls.no_grant, cls.outsider, cls.viewer):
            actor.user_permissions.add(*permissions)

    def start(self, actor=None, request_id=None):
        return workflow.create_review(actor=actor or self.clerk, employee=self.outsider,
            reference="HR supplied request 01", request_date=timezone.localdate(), request_kind="movement",
            upload=SimpleUploadedFile("request.pdf", b"%PDF-synthetic request evidence"), request_id=request_id or uuid4())

    def submit(self, review):
        review = workflow.edit_findings(actor=self.clerk, review=review, expected_version=review.state_version,
            findings="Reviewed named custody", coverage_note="This office only. Legacy paper records checked separately.")
        return workflow.submit_review(actor=self.clerk, review=review, expected_version=review.state_version,
            expected_source=workflow.capture(review))

    def decide(self, review, actor=None, action="review"):
        return workflow.decide_review(actor=actor or self.no_grant, review=review,
            expected_version=review.state_version, action=action, note="Reviewed supplied request and office coverage.")

    def test_review_is_qualified_as_of_and_does_not_write_finance_or_custody(self):
        before = list(self.asset.__class__.objects.values())
        with CaptureQueriesContext(connections["finance"]) as finance:
            review = self.decide(self.submit(self.start()))
        self.assertEqual(len(finance), 0)
        self.assertEqual(review.status, Review.REVIEWED)
        self.assertEqual(review.outcome, "no_current_named_items")
        self.assertEqual(list(self.asset.__class__.objects.values()), before)
        workflow.verify_history(review)
        workflow.verify_source(review)
        self.assertEqual(review.events.count(), 4)

    def test_explicit_permission_owner_and_uat_restrictions(self):
        for actor in (self.super_no_grant, self.viewer):
            with self.subTest(actor=actor.pk), self.assertRaises(PermissionDenied):
                self.start(actor)
        review = self.start()
        self.assertFalse(workflow.visible_reviews(self.outsider).exists())
        with self.assertRaises(PermissionDenied):
            workflow.edit_findings(actor=self.outsider, review=review, expected_version=1,
                findings="Wrong owner", coverage_note="Wrong owner")

    def test_independence_stale_snapshot_and_retained_return(self):
        self.accept()
        review = self.submit(self.start())
        self.assertEqual(review.outcome, "outstanding")
        with self.assertRaises(PermissionDenied):
            self.decide(review, self.clerk)
        self.asset.__class__.objects.filter(pk=self.asset.pk).update(assigned_office="Changed physical record")
        with self.assertRaises(ValidationError):
            self.decide(review)
        review = self.decide(review, action="return")
        self.assertEqual(review.status, Review.DRAFT)
        self.assertEqual(review.events.filter(action="submitted").count(), 1)
        review = self.submit(review)
        review = self.decide(review)
        self.assertEqual(review.outcome, "outstanding")
        self.assertEqual(review.events.filter(action="submitted").count(), 2)

    def test_duplicate_identity_and_open_case_are_rejected(self):
        identity = uuid4()
        review = self.start(request_id=identity)
        self.assertEqual(self.start(request_id=identity).pk, review.pk)
        with self.assertRaises(ValidationError):
            self.start()
        self.decide(review, actor=self.clerk, action="cancel")
        self.assertNotEqual(self.start().pk, review.pk)

    def test_source_and_event_corruption_fail_closed(self):
        review = self.submit(self.start())
        from pathlib import Path
        original = Path(review.file.path).read_bytes()
        Path(review.file.path).unlink()
        for _ in range(2):
            with self.assertRaises(ValidationError):
                workflow.verify_source(review)
        Path(review.file.path).write_bytes(b"changed document")
        with self.assertRaises(ValidationError):
            self.decide(review)
        Path(review.file.path).write_bytes(original)
        Event.objects.filter(review=review, action="submitted").update(checksum="0" * 64)
        with self.assertRaises(ValidationError):
            self.decide(review)

    def test_inactive_historical_identity_is_not_treated_as_cleared(self):
        self.accept()
        type(self.outsider).objects.filter(pk=self.outsider.pk).update(is_active=False)
        self.outsider.refresh_from_db()
        review = self.decide(self.submit(self.start()))
        self.assertEqual(review.outcome, "outstanding")

    def test_http_tokens_scope_private_evidence_and_independent_actions(self):
        from django.test import Client
        from django.urls import reverse
        self.client.force_login(self.clerk)
        create_url = reverse("inventory:hr-custody-review-create", args=(self.outsider.pk,))
        response = self.client.get(create_url)
        self.assertEqual(response.status_code, 200)
        token = response.context["form"].initial["token"]
        data = {"token": token, "reference": "HR HTTP test", "request_date": str(timezone.localdate()),
            "request_kind": "exit", "upload": SimpleUploadedFile("hr.pdf", b"%PDF-test source")}
        response = self.client.post(create_url, data)
        self.assertEqual(response.status_code, 302)
        review = Review.objects.get(reference="HR HTTP test")
        detail_url = reverse("inventory:hr-custody-review-detail", args=(review.pk,))
        evidence_url = reverse("inventory:hr-custody-review-evidence", args=(review.pk,))
        response = self.client.get(detail_url)
        self.assertContains(response, "not an employee clearance certificate")
        self.assertIn("no-store", response["Cache-Control"])
        response = self.client.get(evidence_url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertTrue(b"".join(response.streaming_content).startswith(b"%PDF"))
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.clerk)
        self.assertEqual(protected.post(detail_url, {"operation": "cancel"}).status_code, 403)
        self.client.post(detail_url, {"operation": "edit", "expected_version": 1,
            "findings": "Office documents checked", "coverage_note": "Other offices excluded"})
        response = self.client.get(detail_url)
        source_token = response.context["source_token"]
        self.assertContains(self.client.post(detail_url, {"operation": "submit", "source_token": source_token + "x"}),
            "preview expired or changed")
        self.client.force_login(self.no_grant)
        self.assertEqual(self.client.post(detail_url, {"operation": "submit", "source_token": source_token}).status_code, 403)
        self.client.force_login(self.clerk)
        self.assertEqual(self.client.post(detail_url, {"operation": "submit", "source_token": source_token}).status_code, 302)
        self.assertNotContains(self.client.get(detail_url), "Record independent review")
        self.client.force_login(self.no_grant)
        self.assertContains(self.client.get(detail_url), "Record independent review")
        self.assertEqual(self.client.post(detail_url, {"operation": "review", "decision-expected_version": 3,
            "decision-note": "Independently reviewed"}).status_code, 302)
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(detail_url).status_code, 404)
        self.assertEqual(self.client.get(evidence_url).status_code, 404)

    def test_missing_tracked_asset_cannot_be_read_as_an_empty_review(self):
        self.accept()
        review = self.start()
        self.asset.__class__.objects.filter(pk=self.asset.pk).update(department_id=self.other.pk)
        with self.assertRaises(ValidationError):
            workflow.capture(review)

    def test_read_only_file_checker_detects_damage(self):
        from io import StringIO
        from pathlib import Path
        from django.core.management import call_command, CommandError
        review = self.start()
        output = StringIO()
        call_command("check_custody_review_evidence", stdout=output)
        self.assertIn('"checked": 1', output.getvalue())
        Path(review.file.path).write_bytes(b"damaged")
        with self.assertRaises(CommandError):
            call_command("check_custody_review_evidence", stdout=StringIO())

    def test_actual_witnessed_return_retains_asset_in_review_and_resolves_named_custody(self):
        from inventory.custody_returns import record_return, attach_return_evidence, confirm_return
        from inventory.services import custody_source
        permissions = Permission.objects.filter(content_type__app_label="inventory", codename__in=(
            "record_asset_return", "verify_asset_return"))
        for actor in (self.clerk, self.no_grant):
            actor.user_permissions.add(*permissions)
        self.accept()
        review = self.submit(self.start())
        self.asset.refresh_from_db()
        movement = record_return(actor=self.clerk, asset=self.asset, expected_custody=custody_source(self.asset),
            request_id=uuid4(), data={"transfer_date": timezone.localdate(), "reference": "Return for HR review",
                "reason": "Witnessed physical receipt", "return_condition": "damaged", "destination_custodian": "GSO storage"})
        attach_return_evidence(actor=self.clerk, transfer=movement, expected_version=movement.state_version,
            upload=SimpleUploadedFile("return.pdf", b"%PDF-test return"), note="Signed witnessed return")
        movement.refresh_from_db()
        confirm_return(actor=self.no_grant, transfer=movement, expected_version=movement.state_version,
            note="Independently checked return")
        with self.assertRaises(ValidationError):
            self.decide(review)
        review = self.decide(review, action="return")
        review = self.decide(self.submit(review))
        self.assertEqual(review.outcome, "no_current_named_items")
        self.assertEqual(len(review.source_snapshot["assets"]), 1)
        self.assertEqual(review.source_snapshot["assets"][0]["last_return_id"], movement.pk)

    # Reuse actions without importing another TestCase into this module's discovery.
    def accept(self):
        from inventory.services import acknowledge_asset_transfer
        return acknowledge_asset_transfer(actor=self.outsider, transfer=self.custody_start())

    custody_start = test_grand_employee_custody.GrandEmployeeCustodyTests.start


from django.test import TransactionTestCase, skipUnlessDBFeature


@skipUnlessDBFeature("has_select_for_update")
class GrandHRCustodyReviewRaceTests(TransactionTestCase):
    databases = {"default", "finance"}

    def setUp(self):
        GrandHRCustodyReviewTests.setUpTestData.__func__(self)
        GrandHRCustodyReviewTests.setUp(self)

    start = GrandHRCustodyReviewTests.start
    submit = GrandHRCustodyReviewTests.submit
    decide = GrandHRCustodyReviewTests.decide
    custody_start = test_grand_employee_custody.GrandEmployeeCustodyTests.start

    def test_waiting_empty_review_detects_new_pending_asset_after_employee_lock(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event
        from time import monotonic, sleep
        from django.contrib.auth import get_user_model
        from django.db import transaction
        review = self.submit(self.start())
        started, reader = Event(), []

        def decide():
            connections.close_all()
            try:
                actor = get_user_model().objects.get(pk=self.no_grant.pk)
                with connections["default"].cursor() as cursor:
                    cursor.execute("SET SESSION innodb_lock_wait_timeout = 8")
                    cursor.execute("SELECT CONNECTION_ID()")
                    reader.append(cursor.fetchone()[0])
                started.set()
                try:
                    workflow.decide_review(actor=actor, review=review, expected_version=review.state_version,
                        action="review", note="Concurrent empty review")
                    return "unexpected review"
                except ValidationError as error:
                    return str(error)
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=1) as executor:
            with transaction.atomic(using="default"):
                self.custody_start()
                future = executor.submit(decide)
                self.assertTrue(started.wait(3))
                deadline, blocked = monotonic() + 3, False
                while monotonic() < deadline:
                    with connections["default"].cursor() as cursor:
                        cursor.execute("""SELECT 1 FROM performance_schema.data_lock_waits w
                            JOIN performance_schema.threads t ON t.THREAD_ID=w.REQUESTING_THREAD_ID
                            WHERE t.PROCESSLIST_ID=%s""", [reader[0]])
                        blocked = cursor.fetchone() is not None
                    if blocked or future.done():
                        break
                    sleep(0.02)
                self.assertTrue(blocked, "Review did not wait on the incoming handoff's employee lock")
            self.assertIn("asset set changed", future.result(timeout=12))
        review.refresh_from_db()
        self.assertEqual(review.status, Review.SUBMITTED)

    def test_competing_decisions_retain_only_one_final_outcome(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.contrib.auth import get_user_model
        review = self.submit(self.start())
        barrier = Barrier(2)

        def decide(action):
            connections.close_all()
            try:
                actor = get_user_model().objects.get(pk=self.no_grant.pk)
                barrier.wait(timeout=10)
                try:
                    return workflow.decide_review(actor=actor, review=review, expected_version=review.state_version,
                        action=action, note="Competing documented decision").status
                except ValidationError:
                    return "conflict"
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(decide, ("review", "cancel")))
        self.assertEqual(results.count("conflict"), 1)
        review.refresh_from_db()
        self.assertIn(review.status, (Review.REVIEWED, Review.CANCELLED))
        workflow.verify_history(review)
