import csv
import io
import tempfile
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from budget import test_planning_context as fixtures
from budget.planning_context import build_context, displayed_context
from budget.services import transition_version
from vouchers.roles import FINANCE_UAT_VIEWER_GROUP
from . import budget_actuals as services
from .models import BudgetActualScope, BudgetActualVersion, JournalEntry, LedgerAccount


class BudgetActualAdoptionTests(TestCase):
    databases = {"default", "finance"}
    setUpTestData = classmethod(fixtures.PlanningContextTests.setUpTestData.__func__)
    employee = classmethod(fixtures.PlanningContextTests.employee.__func__)
    make_call = fixtures.PlanningContextTests.make_call
    make_version = fixtures.PlanningContextTests.make_version
    add_line = fixtures.PlanningContextTests.add_line
    add_ceiling = fixtures.PlanningContextTests.add_ceiling
    make_authorized_appropriation = fixtures.PlanningContextTests.make_authorized_appropriation
    journal = fixtures.PlanningContextTests.journal
    estimate = fixtures.PlanningContextTests.estimate

    def setUp(self):
        fixtures.PlanningContextTests.setUp(self)
        self.grant(self.maker, "view", "prepare", "export")
        self.grant(self.checker, "view", "review", "export")
        self.exports = tempfile.TemporaryDirectory()
        self.addCleanup(self.exports.cleanup)
        override = override_settings(GRAND_EXPORT_ROOT=self.exports.name)
        override.enable()
        self.addCleanup(override.disable)

    def grant(self, actor, *actions):
        actor.user_permissions.add(*Permission.objects.filter(content_type__app_label="accounting",
            codename__in=[f"{action}_budget_actuals" for action in actions]))

    def document(self, amount="140"):
        from reportlab.pdfgen import canvas
        data = io.BytesIO()
        page = canvas.Canvas(data)
        page.drawString(40, 790, "SYNTHETIC TEST ONLY - External office expenditure certificate")
        page.drawString(40, 765, f"GSO / GF / Jan-Jun 2026 / Office supplies: {amount}")
        page.drawString(40, 740, "Original Accountant: Synthetic Officer; certified July 1, 2026")
        page.save()
        return SimpleUploadedFile("synthetic-certificate.pdf", data.getvalue(), content_type="application/pdf")

    def arguments(self, amount="140", **changes):
        values = dict(actor=self.maker, fund_id=self.fund.pk, center_id=self.center.pk,
            budget_department_id=self.budget_office.pk, period_start=date(2026, 1, 1), period_end=date(2026, 6, 30),
            document=self.document(amount), rows=[{"account_id": self.account.pk,
                "expense_class": self.line.expense_class, "amount": amount, "source_row": "Page 1, office supplies"}],
            reference="SYN-CERT-2026", issuer="Synthetic municipal Accounting office",
            accountant_name="Synthetic original Accountant", certified_on=date(2026, 7, 1),
            certification_authority="Retained original Accountant designation", coverage="Complete GF/GSO covered objects; explicit signed rows",
            signed_total=amount, reason="Adopt retained historical evidence", expected_latest=0)
        values.update(changes)
        return values

    def adopt(self, amount="140", **changes):
        record = services.propose(**self.arguments(amount, **changes))
        return services.review(record, self.checker, approve=True, note="Checked the retained signed rows and coverage",
            authority="Synthetic independent adoption-review designation")

    def test_adoption_connects_actuals_without_adding_native_activity(self):
        self.journal("NATIVE-60", date(2026, 6, 30), Decimal("60"))
        self.estimate("40")
        record = services.propose(**self.arguments())
        self.assertIsNone(build_context(self.version, self.preparer)["rows"][0]["half_certified"])
        original_count = JournalEntry.objects.count()
        services.review(record, self.checker, approve=True, note="Verified original certification", authority="Independent reviewer")
        row = build_context(self.version, self.preparer)["rows"][0]
        self.assertEqual(row["half_amount"], "60.00")
        self.assertEqual(row["half_certified"]["amount"], "140.00")
        self.assertEqual(row["certified_indicative_total"], "180.00")
        self.assertEqual(row["indicative_total"], "100.00")
        self.assertEqual(row["half_certified"]["certificate"], str(record.public_id))
        self.assertEqual(row["half_certified"]["coverage"], record.payload["coverage"])
        self.assertEqual(row["half_certified"]["signed_total"], "140.00")
        self.assertEqual(JournalEntry.objects.count(), original_count)
        self.client.force_login(self.preparer)
        response = self.client.get(reverse("budget:version_detail", args=(self.version.public_id,)))
        self.assertContains(response, "Certified external actuals")
        self.assertContains(response, "140.00")
        self.assertEqual(self.client.get(reverse("accounting:budget_actual_detail", args=(record.public_id,))).status_code, 200)
        self.assertEqual(self.client.get(reverse("accounting:budget_actual_evidence", args=(record.public_id,))).status_code, 403)

    def test_zero_capital_and_missing_classification_are_distinct(self):
        self.account.account_type = "asset"
        self.account.save(update_fields=("account_type",))
        self.line.expense_class = "CO"
        self.line.save(update_fields=("expense_class",))
        self.adopt("0")
        row = build_context(self.version, self.preparer)["rows"][0]
        self.assertFalse(row["supports_expense_activity"])
        self.assertIsNone(row["half_amount"])
        self.assertEqual(row["half_certified"]["amount"], "0.00")
        self.assertIsNone(row["prior_certified"])
        self.line.expense_class = "MOOE"
        self.line.save(update_fields=("expense_class",))
        row = build_context(self.version, self.preparer)["rows"][0]
        self.assertIsNone(row["half_certified"])
        self.assertIn("differs", row["half_certification_state"])

    def test_successor_preserves_submitted_context_exports_and_original_file(self):
        first = self.adopt()
        self.estimate()
        version = transition_version(self.version, "submit", self.preparer)
        frozen = version.planning_context_snapshot
        self.client.force_login(self.preparer)
        before = self.client.get(reverse("budget:planning_context_export", args=(version.public_id,)))
        self.assertEqual(before.status_code, 200)
        second = self.adopt("180", expected_latest=1, reference="SYN-CORRECTED")
        self.assertEqual(displayed_context(version, self.reviewer), frozen)
        after = self.client.get(reverse("budget:planning_context_export", args=(version.public_id,)))
        self.assertEqual(before.content, after.content)
        self.assertNotContains(after, "SYN-CORRECTED")
        self.assertEqual(first.scope.versions.count(), 2)
        scope = BudgetActualScope.objects.get(pk=first.scope_id)
        self.assertEqual(scope.current_version_id, second.pk)
        self.client.force_login(self.maker)
        source = self.client.get(reverse("accounting:budget_actual_evidence", args=(first.public_id,)))
        self.assertEqual(source.content, bytes(first.evidence))
        first.refresh_from_db()
        self.assertEqual(first.status, first.APPROVED)

    def test_permissions_independence_uat_and_foreign_office(self):
        record = services.propose(**self.arguments())
        self.grant(self.maker, "review")
        with self.assertRaisesMessage(ValidationError, "independent"):
            services.review(record, self.maker, approve=True, note="Self", authority="No bypass")
        self.grant(self.outsider, "review", "prepare")
        with self.assertRaises(PermissionDenied):
            services.review(record, self.outsider, approve=True, note="Foreign", authority="Foreign")
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(reverse("accounting:budget_actual_detail", args=(record.public_id,))).status_code, 404)
        self.maker.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        with self.assertRaises(PermissionDenied):
            services.propose(**self.arguments(expected_latest=1))
        self.client.force_login(self.maker)
        self.assertEqual(self.client.get(reverse("accounting:budget_actual_detail", args=(record.public_id,))).status_code, 200)
        self.assertEqual(self.client.get(reverse("accounting:budget_actual_create")).status_code, 403)

    def test_stale_versions_return_and_scope_reuse(self):
        first = services.propose(**self.arguments())
        second = services.propose(**self.arguments("150", expected_latest=1))
        with self.assertRaisesMessage(ValidationError, "newer"):
            services.review(first, self.checker, approve=True, note="Old", authority="Reviewer")
        services.review(second, self.checker, approve=False, note="Fix source", authority="Reviewer")
        self.assertIsNone(BudgetActualScope.objects.get().current_version_id)
        with self.assertRaisesMessage(ValidationError, "newer version"):
            services.propose(**self.arguments(expected_latest=1))
        third = self.adopt("160", expected_latest=2)
        self.assertEqual(BudgetActualScope.objects.count(), 1)
        self.assertEqual(third.version, 3)

    def test_amount_scope_document_and_row_validation_rolls_back_new_parent(self):
        cases = [dict(signed_total="141"), dict(period_end=date(2026, 9, 30)),
            dict(certified_on=date(2026, 6, 29)), dict(budget_department_id=self.other_office.pk),
            dict(document=SimpleUploadedFile("bad.pdf", b"<html>not a certificate</html>")),
            dict(rows=[{"account_id": self.account.pk, "expense_class": "MOOE", "amount": "NaN", "source_row": "p1"}])]
        for change in cases:
            with self.subTest(change=tuple(change)), self.assertRaises(ValidationError):
                services.propose(**self.arguments(**change))
        self.assertEqual(BudgetActualScope.objects.count(), 0)
        rows = self.arguments()["rows"] * 2
        with self.assertRaisesMessage(ValidationError, "one explicit"):
            services.propose(**self.arguments(rows=rows, signed_total="280"))

    def test_tampering_and_model_edits_do_not_rewrite_evidence(self):
        record = self.adopt()
        record.payload = {**record.payload, "reference": "REWRITE"}
        with self.assertRaises(ValidationError):
            record.save()
        with self.assertRaises(ValidationError):
            record.delete()
        BudgetActualVersion.objects.filter(pk=record.pk).update(evidence=b"changed")
        self.client.force_login(self.checker)
        self.assertEqual(self.client.get(reverse("accounting:budget_actual_detail", args=(record.public_id,))).status_code, 409)
        self.assertEqual(self.client.get(reverse("accounting:budget_actual_evidence", args=(record.public_id,))).status_code, 409)
        with self.assertRaisesMessage(ValidationError, "checksum"):
            build_context(self.version, self.preparer)

    def test_large_document_round_trip_and_full_filtered_pagination_export(self):
        data = b"%PDF-1.4\n" + b"synthetic native byte capacity\n" * 4000
        for number in range(52):
            services.propose(**self.arguments(expected_latest=number,
                reference=f"MATCH-{number:03}", document=SimpleUploadedFile("large.pdf", data)))
        self.client.force_login(self.maker)
        url = reverse("accounting:budget_actual_register")
        response = self.client.get(url, {"q": "MATCH", "page": 2})
        self.assertEqual(response.context["page"].paginator.count, 52)
        self.assertEqual(len(response.context["page"]), 2)
        self.assertContains(response, "MATCH-000")
        exported = self.client.get(reverse("accounting:budget_actual_export"), {"q": "MATCH"})
        self.assertEqual(exported.status_code, 200)
        self.assertEqual(len(list(csv.reader(io.StringIO(exported.content.decode("utf-8-sig"))))), 53)
        first = BudgetActualVersion.objects.get(version=1)
        self.assertEqual(bytes(first.evidence), data)

    def test_form_capture_review_and_successor_reuses_retained_document(self):
        self.client.force_login(self.maker)
        form_page = self.client.get(reverse("accounting:budget_actual_create"))
        self.assertEqual(form_page.status_code, 200)
        values = self.arguments()
        post = {key: value for key, value in values.items() if key not in ("actor", "rows", "document", "fund_id", "center_id", "budget_department_id")}
        post.update(fund=self.fund.pk, center=self.center.pk, budget_department=self.budget_office.pk,
            evidence=values["document"], **{"form-TOTAL_FORMS": "1", "form-INITIAL_FORMS": "0",
                "form-0-account": self.account.pk, "form-0-expense_class": self.line.expense_class,
                "form-0-amount": "140", "form-0-source_row": "Page 1"})
        result = self.client.post(reverse("accounting:budget_actual_create"), post)
        self.assertEqual(result.status_code, 302, getattr(result, "context", None))
        record = BudgetActualVersion.objects.get()
        self.client.force_login(self.checker)
        result = self.client.post(reverse("accounting:budget_actual_decide", args=(record.public_id,)),
            {"decision": "approve", "note": "Checked original source", "authority": "Independent adoption reviewer"})
        self.assertEqual(result.status_code, 302)
        record.refresh_from_db()
        self.assertEqual(record.status, record.APPROVED)
        self.client.force_login(self.maker)
        post.pop("evidence")
        post.update(expected_latest=1, reason="Correct transcription", **{"form-INITIAL_FORMS": "1"})
        result = self.client.post(reverse("accounting:budget_actual_successor", args=(record.public_id,)), post)
        self.assertEqual(result.status_code, 302)
        successor = BudgetActualVersion.objects.get(version=2)
        self.assertEqual(successor.evidence_sha256, record.evidence_sha256)
        self.assertEqual(successor.status, successor.SUBMITTED)

    def test_changed_classifications_block_adoption_without_erasing_history(self):
        record = services.propose(**self.arguments())
        self.account.title = "Renamed source classification"
        self.account.save(update_fields=("title",))
        with self.assertRaisesMessage(ValidationError, "classifications changed"):
            services.review(record, self.checker, approve=True, note="Pending source changed", authority="Reviewer")
        self.assertIsNone(BudgetActualScope.objects.get().current_version_id)
        services.review(record, self.checker, approve=False, note="Recapture classification", authority="Reviewer")
        current = self.adopt(expected_latest=1)
        self.center.office_id = self.other_office.pk
        self.center.save(update_fields=("office_id",))
        with self.assertRaisesMessage(ValidationError, "office identity"):
            build_context(self.version, self.preparer)
        self.client.force_login(self.maker)
        self.assertEqual(self.client.get(reverse("accounting:budget_actual_evidence", args=(current.public_id,))).status_code, 200)

    def test_legacy_context_and_changed_preparer_evidence(self):
        from django.template.loader import render_to_string
        legacy = {"schema": 1, "rows": [{"fund": "GF", "office": "GSO", "account": "OLD"}]}
        rendered = render_to_string("budget/certified_actuals.html", {"planning": legacy})
        self.assertIn("Incomplete certified context", rendered)
        self.assertIn("No retained certification", rendered)
        record = services.propose(**self.arguments())
        BudgetActualVersion.objects.filter(pk=record.pk).update(prepared_by_label="Altered")
        record.refresh_from_db()
        with self.assertRaisesMessage(ValidationError, "identity"):
            services.verify(record)
