from datetime import date

from django.core.exceptions import ValidationError
from django.contrib.auth.models import Permission

from accounting.services import submit_entry, post_entry, create_reversal
from accounting.models import AccountingPeriod
from finance.models import FinancePostingRule as Rule, FinancePostingRuleLine as Line
from . import test_deduction_corrections as fixtures
from .remittances import (add_line, submit_batch, review_batch, release_batch,
    materialize_remittance_journal, reconcile_posted_remittance_entry)


class DatedWithholdingCorrectionTests(fixtures.DeductionCorrectionTests):
    def posted_remittance(self):
        batch = self.remittance()
        for user in (self.treasury_user, self.validator):
            user.user_permissions.add(*Permission.objects.filter(content_type__app_label='vouchers',
                codename__in=('prepare_remittances', 'approve_remittances', 'release_remittances')))
        rule = Rule.objects.create(variant=self.transaction_variant, code='dated-remittance',
            title='Synthetic remittance', event_kind=Rule.REMITTANCE, recognition_point=Rule.DEDUCTION_REMITTANCE,
            authority_reference='Synthetic reviewed policy', created_by=self.preparer)
        Line.objects.bulk_create([
            Line(rule=rule, sequence=10, label='Reduce withholding', side=Line.DEBIT,
                account_source=Line.DEDUCTION_MAPPINGS, amount_source=Line.EACH_DEDUCTION),
            Line(rule=rule, sequence=20, label='Bank payment', side=Line.CREDIT,
                account_source=Line.BANK_MAPPING, amount_source=Line.EVENT_AMOUNT)])
        add_line(batch=batch, actor=self.treasury_user, choice_key=self.availability()[0]['choice_key'],
            amount=100, reason='Actual later remittance')
        submit_batch(batch=batch, actor=self.treasury_user)
        review_batch(batch=batch, actor=self.validator, approve=True, reason='Independent remittance review')
        request = release_batch(batch=batch, actor=self.treasury_user,
            release_reference='Synthetic bank debit', acknowledgement_reference='Synthetic receipt')
        entry, _ = materialize_remittance_journal(request, self.preparer)
        submit_entry(entry, self.preparer); post_entry(entry, self.validator)
        reconcile_posted_remittance_entry(entry, self.validator)
        return entry

    def test_earlier_correction_cannot_spend_later_posted_remittance(self):
        self.posted_remittance()
        with self.assertRaisesMessage(ValidationError, 'already remitted, reserved or corrected'):
            self.request(correction_date=date(2026, 8, 26))

    def test_later_restoration_does_not_erase_intermediate_shortfall(self):
        entry = self.posted_remittance()
        reversal = create_reversal(entry, self.preparer, reference='SYNTHETIC-RESTORATION',
            entry_date=date(2026, 9, 1), period=AccountingPeriod.objects.get(department_id=self.accounting.pk,
                starts_on__lte=date(2026, 9, 1), ends_on__gte=date(2026, 9, 1)),
            reason='Synthetic restored ledger capacity')
        submit_entry(reversal, self.preparer); post_entry(reversal, self.validator)
        with self.assertRaisesMessage(ValidationError, 'already remitted, reserved or corrected'):
            self.request(correction_date=date(2026, 8, 26))
        self.request(correction_date=date(2026, 9, 2))
