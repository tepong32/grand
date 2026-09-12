"""Explicit receiving bank evidence retained with an actual remittance receipt."""
from django.core.exceptions import ValidationError
from django.db.models import Q

from accounting.models import LedgerAccount, PostingMapping
from finance.models import FinanceConfigurationItem


def available_banks(batch, day):
    return FinanceConfigurationItem.objects.filter(department_id=batch.finance_department_id,
        release__department_id=batch.finance_department_id, release__status='active', status='active',
        category='bank_account', effective_from__lte=day, release__effective_from__lte=day).filter(
            Q(effective_to__isnull=True) | Q(effective_to__gte=day)).filter(
            Q(release__effective_to__isnull=True) | Q(release__effective_to__gte=day)).select_related('release')


def bank_snapshot(batch, bank_id, day):
    try:
        item = available_banks(batch, day).get(public_id=bank_id)
    except (FinanceConfigurationItem.DoesNotExist, ValueError, ValidationError):
        raise ValidationError('Choose a receiving bank active for this receipt date in the Accounting office’s approved Finance setup.')
    mappings = list(PostingMapping.objects.filter(department_id=batch.finance_department_id,
        category=PostingMapping.BANK, source_code__iexact=item.code, is_active=True).select_related('account'))
    if len(mappings) != 1:
        raise ValidationError('The receiving bank needs one explicit active Accounting bank mapping.')
    mapping = mappings[0]
    account = mapping.account
    if account.department_id != batch.finance_department_id or not account.is_active or not account.allow_posting or account.account_type != 'asset':
        raise ValidationError('The receiving bank must map to an active posting asset account in this Accounting office.')
    return {'configuration_item': str(item.public_id), 'configuration_version': item.version,
        'release_id': item.release_id, 'release_code': item.release.code, 'bank_code': item.code, 'bank_label': item.label,
        'mapping_id': mapping.pk, 'ledger_account_id': account.pk, 'ledger_account_code': account.code,
        'ledger_account_title': account.title}


def receiving_account(batch, retained, original_bank):
    """Approved routing is pinned; a later mapping edit cannot silently reroute it."""
    if not retained:
        return original_bank.account
    account = LedgerAccount.objects.filter(pk=retained['ledger_account_id'],
        department_id=batch.finance_department_id, code=retained['ledger_account_code'],
        account_type='asset', is_active=True, allow_posting=True).first()
    if account is None:
        raise ValidationError('The approved receiving ledger account is unavailable. Resolve its Accounting setup before posting.')
    return account
