"""Detached mapping/opening decision checks; no permission or certification grant."""
from collections import Counter
from decimal import Decimal
from django.core.exceptions import ValidationError
from .cash_classifications import checksum


def event_body(event):
    body = {'id': event.pk, 'action': event.action, 'actor': event.actor_id,
        'reason': event.reason, 'snapshot': event.snapshot, 'created_at': event.created_at.isoformat()}
    if hasattr(event, 'actor_label'):
        body['actor_label'] = event.actor_label
    return body


def latest(events, action):
    matches = [event for event in events if event['action'] == action]
    if not matches:
        raise ValidationError('Retain the original source decision: ' + action)
    return matches[-1]


def validate_mapping(mapping):
    from reporting.statement_services import snapshot_checksum
    activation = mapping['activation']
    if (mapping['checksum'] != snapshot_checksum(mapping['payload'])
        or activation != latest(mapping['events'], 'activated')
        or activation['snapshot'] != mapping['payload']
        or activation['actor'] != mapping['reviewed_by']
        or mapping['reviewed_by'] in (None, mapping['created_by'], mapping['submitted_by'])):
        raise ValidationError('Retained cash mapping does not reproduce its independent activation.')
    codes = [code for line in mapping['payload']['lines'] for code in line['account_codes']]
    if (not codes or len(codes) != len(set(codes))
        or any(line['selector_type'] != 'account_codes' for line in mapping['payload']['lines'])
        or sorted(codes) != sorted(row['code'] for row in mapping['accounts'])
        or any(row['account_type'] != 'asset' for row in mapping['accounts'])):
        raise ValidationError('Retained cash account identities do not reproduce the explicit reviewed scope.')


def validate(mapping, opening):
    validate_mapping(mapping)
    approval = latest(opening['events'], 'approved')
    reconciliation = latest(opening['events'], 'reconciled')
    if (opening['checksum'] != checksum(opening['source'])
        or opening['public_id'] != opening['source']['batch']
        or opening['period']['id'] != opening['source']['period']
        or opening['period']['department_id'] != opening['source']['department']
        or opening['baseline_date'] != opening['period']['starts_on']
        or opening['validation'].get('evidence_checksum') != opening['checksum']
        or not opening['validation'].get('valid')
        or approval['snapshot'] != opening['validation']
        or approval['actor'] != opening['approved_by']
        or opening['approved_by'] in (None, opening['created_by'], opening['submitted_by'])
        or reconciliation['actor'] != opening['reconciled_by']):
        raise ValidationError('Retained opening does not reproduce its independent approval and reconciliation.')
    controls = opening['source']['controls']
    rows = opening['source']['rows']
    debit = sum((Decimal(row['resolved'][3]) for row in rows), Decimal('0.00'))
    credit = sum((Decimal(row['resolved'][4]) for row in rows), Decimal('0.00'))
    result = reconciliation['snapshot']
    posted = latest(opening['events'], 'posted')['snapshot']
    details = result['postings']
    if (len(rows) != controls[0] or debit != Decimal(controls[1]) or credit != Decimal(controls[2])
        or debit != credit or opening['zero'] != controls[3]
        or (opening['zero'] and (rows or debit or credit))
        or result['expected_row_count'] != len(rows) or result['posted_row_count'] != len(rows)
        or result['row_difference'] != 0
        or any(Decimal(result[key]) != amount for key, amount in (
            ('expected_debit', debit), ('posted_debit', debit), ('expected_credit', credit), ('posted_credit', credit),
            ('debit_difference', Decimal('0')), ('credit_difference', Decimal('0'))))):
        raise ValidationError('Retained opening row and reconciliation controls must reproduce exactly.')
    if (posted['zero_balance_declaration'] != opening['zero']
        or posted['posting_count'] != len(details)
        or len(posted['journal_entries']) != len(set(posted['journal_entries']))
        or sorted(posted['journal_entries']) != sorted(row['entry'] for row in details)
        or sum(row['row_count'] for row in details) != len(rows)
        or sum((Decimal(row['debit']) for row in details), Decimal('0')) != debit
        or sum((Decimal(row['credit']) for row in details), Decimal('0')) != credit):
        raise ValidationError('Retained opening posting decisions do not reproduce reconciliation detail.')


def validate_opening_lines(ledger, opening):
    fund_id = ledger['scope']['fund']['id']
    rows = [row for row in opening['source']['rows'] if row['resolved'][0] == fund_id]
    entries = {entry['id']: entry for entry in ledger['journals']}
    if not opening['zero'] and len(opening['postings']) != 1:
        raise ValidationError('Retain the exact opening posting for this fund.')
    for posting in opening['postings']:
        entry = entries.get(posting['entry_id'])
        detail = [row for row in latest(opening['events'], 'reconciled')['snapshot']['postings']
            if entry and row['entry'] == entry['public_id']]
        expected = Counter((row['resolved'][1], row['resolved'][2], Decimal(row['resolved'][3]), Decimal(row['resolved'][4])) for row in rows)
        actual = Counter((line['account_id'], line['responsibility_center_id'], Decimal(line['debit']), Decimal(line['credit'])) for line in entry['lines']) if entry else Counter()
        if (not entry or posting['fund_id'] != fund_id or posting['row_count'] != len(rows)
            or len(detail) != 1 or detail[0]['reference'] != entry['reference']
            or detail[0]['row_count'] != posting['row_count']
            or Decimal(detail[0]['debit']) != Decimal(posting['debit'])
            or Decimal(detail[0]['credit']) != Decimal(posting['credit'])
            or actual != expected
            or Decimal(posting['debit']) != sum((Decimal(row['resolved'][3]) for row in rows), Decimal('0'))
            or Decimal(posting['credit']) != sum((Decimal(row['resolved'][4]) for row in rows), Decimal('0'))):
            raise ValidationError('Retained opening financial lines do not match their approved source rows.')
