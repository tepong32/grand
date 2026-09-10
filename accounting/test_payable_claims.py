import csv
import io
import shutil
import tempfile
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from departments.models import Department
from .models import AccountingPeriod, Fund, JournalEntry, JournalLine, LedgerAccount, JournalSubsidiaryLine
from .payables import claim_rows
from .services import submit_entry, post_entry, create_reversal, subsidiary_schedule_rows


class PayableClaimTests(TestCase):
    databases = {"default", "finance"}

    def setUp(self):
        self.temp = tempfile.mkdtemp(prefix="grand-claim-test-")
        override = override_settings(MEDIA_ROOT=self.temp, GRAND_EXPORT_ROOT=self.temp)
        override.enable()
        self.addCleanup(override.disable)
        self.addCleanup(shutil.rmtree, self.temp, True)
        self.department = Department.objects.create(name="Municipal Accounting Office", slug="claim-accounting")
        self.owner = {"department_id": self.department.pk, "department_label": self.department.name}
        self.actors = []
        for name in ("maker", "poster"):
            user = get_user_model().objects.create_user(username="claim." + name, email=name + "@example.test")
            user.employeeprofile.assigned_department = self.department
            user.employeeprofile.save(update_fields=("assigned_department",))
            user.user_permissions.add(*Permission.objects.filter(content_type__app_label="accounting",
                codename__in=("prepare_journal_entries", "post_journal_entries", "view_general_ledger", "view_accounting_workspace")))
            self.actors.append(user)
        self.maker, self.poster = self.actors
        self.period = AccountingPeriod.objects.create(**self.owner, fiscal_year=2026, period_number=9,
            label="September", starts_on=date(2026, 9, 1), ends_on=date(2026, 9, 30))
        self.fund = Fund.objects.create(**self.owner, code="GF", name="General Fund")
        self.accounts = {}
        for code, kind in (("cash", "asset"), ("expense", "expense"), ("payable", "liability")):
            self.accounts[code] = LedgerAccount.objects.create(**self.owner, code=code, title=code,
                account_type=kind, normal_balance="credit" if kind == "liability" else "debit")

    def entry(self, reference, amount, *, source=None, day=2, claim="INV-001"):
        entry = JournalEntry.objects.create(**self.owner, reference=reference, entry_date=date(2026, 9, day),
            fund=self.fund, period=self.period, description="Synthetic payable claim", created_by_id=self.maker.pk,
            created_by_label=self.maker.username)
        if source is None:
            JournalLine.objects.create(entry=entry, sequence=1, account=self.accounts["expense"], debit=amount)
            JournalLine.objects.create(entry=entry, sequence=2, account=self.accounts["payable"], credit=amount,
                payable_party_key="supplier-001", payable_claim_reference=claim)
        else:
            JournalLine.objects.create(entry=entry, sequence=1, account=self.accounts["payable"], debit=amount, payable_origin=source)
            JournalLine.objects.create(entry=entry, sequence=2, account=self.accounts["cash"], credit=amount, cash_flow_category="op_suppliers")
        return entry

    def post(self, entry):
        submit_entry(entry, self.maker)
        return post_entry(entry, self.poster)

    def test_earlier_expense_partial_settlement_reversal_and_claim_export(self):
        first = self.post(self.entry("ACCRUAL-1", Decimal("1000")))
        source = first.lines.get(sequence=2)
        self.post(self.entry("ACCRUAL-2", Decimal("200"), claim="INV-002"))
        payment = self.post(self.entry("PAYMENT-1", Decimal("400"), source=source, day=4))
        rows = claim_rows(self.department.pk, date(2026, 9, 5))
        self.assertEqual([(row["line"].payable_claim_reference, row["outstanding"]) for row in rows],
            [("INV-001", Decimal("600")), ("INV-002", Decimal("200"))])
        schedule = subsidiary_schedule_rows(self.department.pk, JournalSubsidiaryLine.PAYABLE, date(2026, 9, 5))
        self.assertEqual(sum(row["balance"] for row in schedule), Decimal("800"))
        self.assertFalse(payment.lines.filter(account=self.accounts["expense"]).exists())
        self.client.force_login(self.poster)
        response = self.client.get(reverse("accounting:payable_claim_export"), {"as_of": "2026-09-05"})
        self.assertEqual(response.status_code, 200)
        exported = list(csv.DictReader(io.StringIO(response.content.decode())))
        self.assertEqual([(row["claim"], row["outstanding"]) for row in exported], [("INV-001", "600.00"), ("INV-002", "200.00")])
        page = self.client.get(reverse("accounting:subsidiary_controls"), {"as_of": "2026-09-05"})
        self.assertContains(page, "INV-001")
        undo = create_reversal(payment, self.maker, reference="PAYMENT-UNDO", entry_date=date(2026, 9, 6), period=self.period, reason="Payment reversed")
        self.post(undo)
        self.assertEqual(claim_rows(self.department.pk, date(2026, 9, 6))[0]["outstanding"], Decimal("1000"))
        self.post(self.entry("PAYMENT-FINAL", Decimal("1000"), source=source, day=7))
        self.assertEqual(claim_rows(self.department.pk, date(2026, 9, 7))[0]["outstanding"], 0)
        self.assertEqual(claim_rows(self.department.pk, date(2026, 9, 5))[0]["outstanding"], Decimal("600"))

    def test_overpayment_source_reversal_and_backdated_overpayment_fail_at_posting(self):
        original = self.post(self.entry("ACCRUAL", Decimal("1000")))
        source = original.lines.get(sequence=2)
        payment = self.post(self.entry("PAY", Decimal("800"), source=source, day=4))
        excess = self.entry("EXCESS", Decimal("300"), source=source, day=5)
        submit_entry(excess, self.maker)
        with self.assertRaisesMessage(ValidationError, "would use"):
            post_entry(excess, self.poster)
        excess.refresh_from_db()
        self.assertEqual(excess.status, JournalEntry.SUBMITTED)
        self.assertFalse(excess.subsidiary_lines.exists())
        cancellation = create_reversal(original, self.maker, reference="CANCEL-ACCRUAL", entry_date=date(2026, 9, 5), period=self.period, reason="Cancel original")
        submit_entry(cancellation, self.maker)
        with self.assertRaisesMessage(ValidationError, "would use"):
            post_entry(cancellation, self.poster)
        undo = create_reversal(payment, self.maker, reference="UNDO", entry_date=date(2026, 9, 8), period=self.period, reason="Restore claim")
        self.post(undo)
        # Today's available amount is 1,000, but on September 5 only 200 remained.
        with self.assertRaisesMessage(ValidationError, "2026-09-05"):
            post_entry(excess, self.poster)

    def test_wrong_fund_and_unlinked_credit_cannot_restore_capacity(self):
        original = self.post(self.entry("ACCRUAL", Decimal("1000")))
        source = original.lines.get(sequence=2)
        draft = self.entry("WRONG-FUND", Decimal("100"), source=source)
        draft.fund = Fund.objects.create(**self.owner, code="SEF", name="Special Education Fund")
        draft.save(update_fields=("fund",))
        with self.assertRaisesMessage(ValidationError, "office, fund and liability account"):
            submit_entry(draft, self.maker)
        credit = JournalLine(entry=original, sequence=3, account=self.accounts["payable"], credit=100, payable_origin=source)
        with self.assertRaisesMessage(ValidationError, "exact reversal"):
            credit.full_clean()

    def test_line_form_exposes_claim_and_scopes_original_choices(self):
        from .forms import JournalLineForm
        original = self.post(self.entry("ACCRUAL", Decimal("1000")))
        source = original.lines.get(sequence=2)
        draft = self.entry("PAY", Decimal("100"), source=source)
        form = JournalLineForm({"sequence": 3, "account": self.accounts["payable"].pk, "debit": "50",
            "credit": "0", "payable_origin": source.pk}, department=self.department, entry=draft)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().payable_origin_id, source.pk)
        self.assertIn("payable_claim_reference", form.fields)

    def test_same_invoice_cannot_be_recognized_twice(self):
        self.post(self.entry("FIRST", Decimal("1000")))
        duplicate = self.entry("SECOND", Decimal("1000"), claim="inv-001")
        submit_entry(duplicate, self.maker)
        with self.assertRaisesMessage(ValidationError, "already recognized"):
            post_entry(duplicate, self.poster)
        duplicate.refresh_from_db()
        self.assertEqual(duplicate.status, JournalEntry.SUBMITTED)
