"""Dated capacity for a correction that must preserve later posted withholding."""
from decimal import Decimal

from django.db.models import Sum

from accounting.models import JournalEntry, JournalSubsidiaryLine


KEYS = ('fund_code', 'account_code', 'reference_key', 'deduction_code')


def correction_balances(*, department_id, transaction_type, as_of_date):
    """Caller holds the Accounting-owner reservation lock.

    Keep today's outstanding reservations deducted once at every later ledger
    boundary. A subsequent credit cannot repair an earlier shortfall.
    """
    from .remittances import withholding_availability
    rows = withholding_availability(finance_department_id=department_id,
        transaction_type=transaction_type, as_of_date=as_of_date, include_nonpositive=True)
    running = {tuple(row[k] for k in KEYS): row['available'] for row in rows}
    minimum = running.copy()
    movements = JournalSubsidiaryLine.objects.filter(entry__department_id=department_id,
        entry__status=JournalEntry.POSTED, entry__entry_date__gt=as_of_date,
        category=JournalSubsidiaryLine.WITHHOLDING,
        source_snapshot__transaction_type=transaction_type).values(
            'entry__entry_date', 'entry__fund__code', 'journal_line__account__code',
            'reference_key', 'source_code').annotate(
                debits=Sum('debit'), credits=Sum('credit')).order_by('entry__entry_date')
    for row in movements:
        key = (row['entry__fund__code'], row['journal_line__account__code'],
            row['reference_key'], row['source_code'])
        if key not in running:
            continue  # Later first recognition cannot fund this earlier correction.
        running[key] += (row['credits'] or Decimal('0')) - (row['debits'] or Decimal('0'))
        minimum[key] = min(minimum[key], running[key])
    return minimum
