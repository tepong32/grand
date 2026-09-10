from datetime import date
from pathlib import Path
from openpyxl import load_workbook

from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse

from reporting import test_cash_flows
from reporting.models import ReportRun
from reporting.services import report_run_integrity_errors
from departments.models import Department
from .cash_classifications import journal_snapshot, propose_classification, review_classification
from .models import AccountingPeriod, CashFlowClassification, JournalEntry, LedgerAccount
from .services import create_reversal, submit_entry, post_entry


class CashClassificationTests(TestCase):
    databases = {"default", "finance"}
    setUp = test_cash_flows.CashFlowReportingTests.setUp
    post = test_cash_flows.CashFlowReportingTests.post
    report = test_cash_flows.CashFlowReportingTests.report

    def proposal(self, entry, parts=None, version=0):
        line = entry.lines.get(account=self.accounts["cash"])
        return propose_classification(entry, self.maker,
            [{"line_id": line.pk, "category": category, "amount": amount}
             for category, amount in (parts or [("fin_principal", "80.00"), ("op_interest_out", "10.00")])],
            reason="Principal and interest per lender schedule", evidence_reference="Synthetic schedule 1",
            expected_version=version)

    def test_historical_split_retains_ledger_and_prior_export(self):
        entry = self.post("OLD-PAYMENT", [("loan", 80, 0, ""), ("expense", 10, 0, ""), ("cash", 0, 90, "")])
        old = self.report()
        self.assertEqual(old.control_status, ReportRun.CONTROL_EXCEPTION)
        old_bytes = Path(old.output_file.path).read_bytes()
        source = journal_snapshot(entry)
        count = JournalEntry.objects.count()
        AccountingPeriod.objects.filter(pk=entry.period_id).update(status="closed")
        LedgerAccount.objects.filter(pk=self.accounts["cash"].pk).update(is_active=False, allow_posting=False)
        proposal = self.proposal(entry)
        self.assertEqual(self.report().control_status, ReportRun.CONTROL_EXCEPTION)
        approved = review_classification(proposal, self.checker, approve=True, note="Matched lender schedule")
        self.assertEqual(approved.status, CashFlowClassification.APPROVED)
        run = self.report()
        self.assertEqual(run.control_status, ReportRun.CONTROL_RECONCILED)
        self.assertEqual(run.control_totals["funds"]["GF"]["current"]["closing_cash"], "310.00")
        evidence = run.source_records.get(source_model="CashFlowClassification")
        self.assertEqual(evidence.snapshot["version"], 1)
        self.assertEqual(evidence.snapshot["allocations"], approved.allocations)
        self.assertEqual(report_run_integrity_errors(run), [])
        workbook = load_workbook(run.output_file.path, data_only=True)
        rows = list(workbook.active.values)
        workbook.close()
        self.assertTrue(any("fin_principal" in row and 80 in row for row in rows))
        self.assertTrue(any("op_interest_out" in row and 10 in row for row in rows))
        self.assertEqual(journal_snapshot(entry), source)
        self.assertEqual(JournalEntry.objects.count(), count)
        self.assertEqual(Path(old.output_file.path).read_bytes(), old_bytes)
        self.client.force_login(self.maker)
        self.assertContains(self.client.get(reverse("accounting:cash_classification", args=[entry.public_id])), "Matched lender schedule")
        retained_bytes = Path(run.output_file.path).read_bytes()
        replacement = self.proposal(entry, [("fin_principal", "70.00"), ("op_interest_out", "20.00")], version=1)
        review_classification(replacement, self.checker, approve=True, note="Corrected lender schedule")
        successor = self.report()
        self.assertEqual(successor.source_records.get(source_model="CashFlowClassification").snapshot["version"], 2)
        self.assertEqual(run.source_records.get(source_model="CashFlowClassification").snapshot["version"], 1)
        self.assertEqual(Path(run.output_file.path).read_bytes(), retained_bytes)
        self.assertEqual(report_run_integrity_errors(run), [])

    def test_same_maker_and_uat_cannot_approve(self):
        entry = self.post("AUTHORITY", [("expense", 90, 0, ""), ("cash", 0, 90, "")])
        self.maker.user_permissions.add(Permission.objects.get(content_type__app_label="reporting", codename="approve_reports"))
        for attr in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
            self.maker.__dict__.pop(attr, None)
        proposal = self.proposal(entry)
        with self.assertRaisesMessage(ValidationError, "different authorized reviewer"):
            review_classification(proposal, self.maker, approve=True, note="Self review")
        self.checker.groups.add(Group.objects.get_or_create(name="Finance UAT Viewer")[0])
        with self.assertRaises(PermissionDenied):
            review_classification(proposal, self.checker, approve=True, note="Viewer review")

    def test_http_proposal_review_and_current_office_boundary(self):
        entry = self.post("HTTP-CASH", [("expense", 90, 0, ""), ("cash", 0, 90, "")])
        line = entry.lines.get(account=self.accounts["cash"])
        url = reverse("accounting:cash_classification", args=[entry.public_id])
        self.client.force_login(self.maker)
        invalid = self.client.post(url, {"expected_version": "0", "reason": "Operating payment",
            "evidence_reference": "Synthetic source", "form-TOTAL_FORMS": "1", "form-INITIAL_FORMS": "1",
            "form-0-journal_line": str(line.pk), "form-0-category": "", "form-0-amount": "90.00"})
        self.assertEqual(invalid.status_code, 200)
        self.assertEqual(entry.cash_classifications.count(), 0)
        self.assertIn("category", invalid.context["formset"].forms[0].errors)
        response = self.client.post(url, {"expected_version": "0", "reason": "Operating payment",
            "evidence_reference": "Synthetic source", "form-TOTAL_FORMS": "1", "form-INITIAL_FORMS": "1",
            "form-0-journal_line": str(line.pk), "form-0-category": "op_suppliers", "form-0-amount": "90.00"})
        self.assertEqual(response.status_code, 302)
        record = entry.cash_classifications.get()
        self.client.force_login(self.checker)
        self.assertContains(self.client.get(url), "Approve")
        response = self.client.post(reverse("accounting:cash_classification_review",
            args=[entry.public_id, record.public_id, "approve"]), {"note": "Schedule matched"})
        self.assertEqual(response.status_code, 302)
        record.refresh_from_db()
        self.assertEqual(record.status, CashFlowClassification.APPROVED)
        foreign = Department.objects.create(name="Other Accounting", slug="cash-other")
        self.maker.employeeprofile.assigned_department = foreign
        self.maker.employeeprofile.save(update_fields=("assigned_department",))
        with self.assertRaises(PermissionDenied):
            self.proposal(entry, version=1)
        self.client.force_login(self.maker)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_report_rejects_altered_approved_evidence(self):
        entry = self.post("EVIDENCE", [("expense", 90, 0, ""), ("cash", 0, 90, "")])
        record = review_classification(self.proposal(entry), self.checker, approve=True, note="Checked")
        # Simulate storage corruption outside the immutable model/service path.
        CashFlowClassification.objects.filter(pk=record.pk).update(review_note="Altered after approval")
        with self.assertRaisesMessage(ValidationError, "no longer reproduces"):
            self.report()

    def test_split_inherits_actual_reversal(self):
        entry = self.post("MIXED", [("loan", 80, 0, ""), ("expense", 10, 0, ""), ("cash", 0, 90, "")])
        review_classification(self.proposal(entry), self.checker, approve=True, note="Schedule checked")
        reversal = create_reversal(entry, self.maker, reference="RETURN-MIXED", entry_date=date(2027, 3, 20),
            period=self.periods[2027], reason="Bank returned payment")
        submit_entry(reversal, self.maker)
        post_entry(reversal, self.checker)
        run = self.report()
        self.assertEqual(run.control_status, ReportRun.CONTROL_RECONCILED)
        self.assertEqual(run.control_totals["funds"]["GF"]["current"]["net_cash_flows"], "0.00")

    def test_exact_allocations_independent_review_and_stale_proposal(self):
        entry = self.post("MIXED-CONTROLS", [("expense", 90, 0, ""), ("cash", 0, 90, "")])
        for amount in ("89.99", "90.001", "NaN", "-90", "Infinity"):
            with self.assertRaises(ValidationError):
                self.proposal(entry, [("op_interest_out", amount)])
        first = self.proposal(entry)
        second = self.proposal(entry)
        # Use a reviewer who is also the proposer to exercise maker/checker separation.
        first.proposed_by_id = self.checker.pk
        # Caller-side changes must be ignored; the stored maker remains authoritative.
        review_classification(first, self.checker, approve=True, note="Source checked")
        with self.assertRaisesMessage(ValidationError, "approved first"):
            review_classification(second, self.checker, approve=True, note="Stale review")
        returned = review_classification(second, self.checker, approve=False, note="Use current approved version")
        self.assertEqual(returned.status, CashFlowClassification.RETURNED)
        with self.assertRaises(ValidationError):
            self.proposal(entry)
        replacement = self.proposal(entry, [("op_interest_out", "90.00")], version=1)
        review_classification(replacement, self.checker, approve=True, note="Corrected schedule")
        with self.assertRaises(ValidationError):
            returned.reason = "rewrite"
            returned.save()
