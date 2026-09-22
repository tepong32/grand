from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from departments.models import Department
from vouchers.models import BankAdviceBatch, DisbursementVoucher, PaymentInstrument, VoucherCase
from .datasets import PaymentInstrumentRegisterDataset


@override_settings(TIME_ZONE="Asia/Manila", USE_TZ=True)
class TreasuryReportDateBoundaryTests(TestCase):
    databases = {"default", "finance"}

    def fixture(self, issued_at, event_at):
        # Synthetic retained states test report projection, not workflow approval.
        office = Department.objects.create(name="Synthetic Treasury", slug="treasury-date-test")
        actor = get_user_model().objects.create_user(username="treasury-date-test")
        case = VoucherCase.objects.create(
            reference_code="DATE-CASE", transaction_type="ordinary-supplier-claim",
            requesting_department=office, current_department=office, payee_name="Synthetic supplier",
            particulars="Synthetic timestamp boundary", authoritative_obligation_amount=Decimal("600"),
            current_stage=VoucherCase.TREASURY_RELEASE, created_by=actor,
        )
        DisbursementVoucher.objects.create(
            case=case, dv_number="DATE-DV", voucher_date=issued_at.date(),
            gross_amount=Decimal("600"), total_deductions=Decimal("0"), net_amount=Decimal("600"),
            prepared_by=actor, prepared_at=issued_at,
        )
        advice = BankAdviceBatch.objects.create(
            advice_number="DATE-ADVICE", advice_date=issued_at.date(), bank_account_code="DATE-BANK",
            status=BankAdviceBatch.ACKNOWLEDGED, accounting_department=office,
            preparation_note="Synthetic retained state", authority_reference="Synthetic only",
            local_applicability_note="No actual bank approval claimed", created_by=actor,
        )
        for index, (status, amount) in enumerate(((PaymentInstrument.ISSUED, "100"),
                (PaymentInstrument.RELEASED, "200"), (PaymentInstrument.CANCELLED, "300"))):
            evidence = {}
            if status == PaymentInstrument.RELEASED:
                evidence = dict(released_at=event_at, released_by=actor, released_to="Synthetic claimant",
                                receipt_reference="DATE-RECEIPT", current_advice_batch=advice)
            elif status == PaymentInstrument.CANCELLED:
                evidence = dict(cancelled_at=event_at, cancelled_by=actor, cancellation_reason="Synthetic spoilage")
            PaymentInstrument.objects.create(
                case=case, bank_account_code="DATE-BANK", fund_code="GF", check_number=f"DATE-{index}",
                amount=Decimal(amount), status=status, issued_by=actor, issued_at=issued_at, **evidence,
            )
        return office

    def test_local_first_day_activity_matches_selected_rows_and_source_dates(self):
        zone = ZoneInfo("Asia/Manila")
        office = self.fixture(datetime(2027, 3, 1, 0, 10, tzinfo=zone), datetime(2027, 3, 1, 0, 30, tzinfo=zone))
        payload = PaymentInstrumentRegisterDataset().payload(office, date(2027, 3, 1), date(2027, 3, 1), {})
        self.assertEqual(len(payload.rows), 3)
        self.assertEqual(payload.control_totals["issued_amount"], Decimal("600"))
        self.assertEqual(payload.control_totals["released_amount"], Decimal("200"))
        self.assertEqual(payload.control_totals["cancelled_amount"], Decimal("300"))
        self.assertEqual({row["source_date"] for row in payload.sources}, {date(2027, 3, 1)})

    def test_next_month_release_and_cancellation_do_not_enter_prior_month_totals(self):
        zone = ZoneInfo("Asia/Manila")
        office = self.fixture(datetime(2027, 3, 31, 10, 0, tzinfo=zone), datetime(2027, 4, 1, 0, 30, tzinfo=zone))
        dataset = PaymentInstrumentRegisterDataset()
        march = dataset.payload(office, date(2027, 3, 1), date(2027, 3, 31), {})
        self.assertEqual(len(march.rows), 3)
        self.assertEqual(march.control_totals["issued_amount"], Decimal("600"))
        self.assertEqual(march.control_totals["released_amount"], Decimal("0"))
        self.assertEqual(march.control_totals["cancelled_amount"], Decimal("0"))
        april = dataset.payload(office, date(2027, 4, 1), date(2027, 4, 30), {})
        self.assertEqual(len(april.rows), 2)
        self.assertEqual(april.control_totals["issued_amount"], Decimal("0"))
        self.assertEqual(april.control_totals["released_amount"], Decimal("200"))
        self.assertEqual(april.control_totals["cancelled_amount"], Decimal("300"))

    def test_active_timezone_west_of_utc_matches_database_date_selection(self):
        zone = ZoneInfo("America/New_York")
        with timezone.override(zone):
            office = self.fixture(datetime(2027, 3, 1, 23, 10, tzinfo=zone), datetime(2027, 3, 1, 23, 30, tzinfo=zone))
            payload = PaymentInstrumentRegisterDataset().payload(office, date(2027, 3, 1), date(2027, 3, 1), {})
        self.assertEqual(len(payload.rows), 3)
        self.assertEqual(payload.control_totals["issued_amount"], Decimal("600"))
        self.assertEqual(payload.control_totals["released_amount"], Decimal("200"))
        self.assertEqual(payload.control_totals["cancelled_amount"], Decimal("300"))
        self.assertEqual({row["source_date"] for row in payload.sources}, {date(2027, 3, 1)})

    @override_settings(USE_TZ=False)
    def test_naive_timestamp_configuration_retains_calendar_dates(self):
        office = self.fixture(datetime(2027, 3, 1, 0, 10), datetime(2027, 3, 1, 0, 30))
        payload = PaymentInstrumentRegisterDataset().payload(office, date(2027, 3, 1), date(2027, 3, 1), {})
        self.assertEqual(payload.control_totals["issued_amount"], Decimal("600"))
        self.assertEqual(payload.control_totals["released_amount"], Decimal("200"))
        self.assertEqual(payload.control_totals["cancelled_amount"], Decimal("300"))
        self.assertEqual({row["source_date"] for row in payload.sources}, {date(2027, 3, 1)})
