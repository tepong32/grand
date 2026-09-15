"""Explicit gross refund, deducted bank charge and actual net cash evidence."""
from decimal import Decimal, InvalidOperation
from django.core.exceptions import ValidationError
from accounting.models import LedgerAccount


def expense_accounts(batch):
    return LedgerAccount.objects.filter(department_id=batch.finance_department_id,
        account_type='expense', is_active=True, allow_posting=True)


def snapshot(batch, amount, account_id, reference, gross):
    try:
        value = Decimal(str(amount or '0'))
    except (InvalidOperation, ValueError, TypeError):
        raise ValidationError('Enter a valid deducted bank charge.')
    if (not value.is_finite() or value < 0 or value > Decimal('9999999999999999.99')
            or value != value.quantize(Decimal('.01'))):
        raise ValidationError('Enter a nonnegative bank charge within the supported amount limit and with at most two decimal places.')
    if not value:
        if account_id or str(reference or '').strip():
            raise ValidationError('Enter the actual bank charge when providing its account or evidence.')
        return None
    if value >= gross or not str(reference or '').strip():
        raise ValidationError('A deducted fee needs evidence and must leave a positive actual bank credit.')
    try:
        account = expense_accounts(batch).get(pk=account_id)
    except (LedgerAccount.DoesNotExist, ValueError, TypeError):
        raise ValidationError('Choose an active posting expense account in the Accounting office for independent review.')
    return {'amount':str(value.quantize(Decimal('.01'))), 'net_received':str((gross-value).quantize(Decimal('.01'))),
        'account_id':account.pk, 'account_code':account.code, 'account_title':account.title,
        'evidence_reference':str(reference).strip()}


def account(batch, retained):
    result = expense_accounts(batch).filter(pk=retained['account_id'],code=retained['account_code']).first()
    if result is None:
        raise ValidationError('The approved fee expense account is unavailable. Resolve Accounting setup before posting.')
    return result


def validate(entry):
    retained = entry.source_snapshot.get('remittance_return', {})
    fee = retained.get('deducted_fee')
    if not fee or entry.source_snapshot.get('remittance_return_correction'):
        return
    from accounting.posted_evidence import verify_source_link
    from .models import RemittancePostingRequest, RemittanceReturn
    from .remittances import _digest
    from .remittance_returns import original_payment
    from .receipt_banks import receiving_account
    request = RemittancePostingRequest.objects.select_related('batch').get(public_id=entry.source_reference)
    item = RemittanceReturn.objects.get(posting_request=request)
    verify_source_link(request,entry,source_type='remittance')
    if (retained != request.payload['remittance_return'] or _digest(item.proposal) != item.proposal_checksum
            or any(retained.get(k)!=v for k,v in item.proposal.items())
            or retained.get('proposal_checksum')!=item.proposal_checksum
            or retained.get('reviewed_by')!=item.reviewed_by_id or item.reviewed_by_id==item.prepared_by_id):
        raise ValidationError('Retain the independently approved gross refund, fee and net receipt evidence.')
    _, original, details, bank = original_payment(request.batch)
    gross = sum((Decimal(row['amount']) for row in retained['allocations']),Decimal('0'))
    value, net = Decimal(fee['amount']), Decimal(fee['net_received'])
    if gross!=Decimal(retained['amount']) or value<=0 or net<=0 or net+value!=gross or entry.fund_id!=original.fund_id:
        raise ValidationError('The gross refund must equal the fee plus actual net bank credit in the original fund.')
    cash_account=receiving_account(request.batch,retained.get('receiving_bank'),bank)
    fee_account=account(request.batch,fee)
    expected=[(cash_account.pk,net,Decimal('0'),bank.cash_flow_category)]
    originals={str(d.pk):d for d in details}
    for row in retained['allocations']:
        d=originals[row['source_detail']]
        expected.append((d.journal_line.account_id,Decimal('0'),Decimal(row['amount']),''))
    expected.append((fee_account.pk,value,Decimal('0'),''))
    actual=list(entry.lines.order_by('sequence').values_list('account_id','debit','credit','cash_flow_category'))
    if actual!=expected:
        raise ValidationError('The receipt journal must retain the approved gross allocations, fee expense and net cash.')
    expected_details=sorted((originals[r['source_detail']].category,originals[r['source_detail']].reference_key,
        originals[r['source_detail']].source_code,Decimal('0'),Decimal(r['amount']),int(r['source_detail'])) for r in retained['allocations'])
    actual_details=sorted((d.category,d.reference_key,d.source_code,d.debit,d.credit,
        d.source_snapshot.get('return_of_subsidiary_line')) for d in entry.subsidiary_lines.all())
    if actual_details!=expected_details:
        raise ValidationError('Retain the original withholding identities and gross receipt allocations.')
