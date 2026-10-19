"""Keep an officer advance's principal distinct from whole replacement instruments."""
from decimal import Decimal

from django.core.exceptions import ValidationError
from finance.models import FinanceTransactionVariant
from .collections import amount, context
from .models import TreasuryCollectionSource as Source
from .remittances import _digest


KEY = 'officer_components'


def officer_data(source):
    values = [source.proposal[key] for key in ('advance_refund', 'advance_refund_correction',
        'advance_cheque_return', 'advance_cheque_return_correction') if source.proposal.get(key)]
    if len(values) != 1 or not isinstance(values[0], dict):
        raise ValidationError('Retain one exact original officer refund identity.')
    return values[0]


def basis(returned):
    """Read retained officer evidence; never infer principal from the bank total."""
    if returned.kind != Source.CHEQUE_RETURN or _digest(returned.proposal) != returned.proposal_checksum:
        raise ValidationError('Retain the original officer bank return and its unchanged evidence.')
    value = amount(officer_data(returned).get('amount'))
    original = returned.proposal.get('original_cheque', {})
    supplied = original.get(KEY)
    if supplied:
        result = {'amount':str(value), 'cash_flow_purpose':supplied.get('cash_flow_purpose')}
        if (supplied != result or value > returned.amount
                or supplied != returned.return_receipt.proposal.get(KEY)):
            raise ValidationError('Retain the original officer principal and cash purpose through the combined return.')
    else:
        purposes = original.get('collection_purposes', [])
        if len(purposes) != 1 or returned.amount != value:
            raise ValidationError('A combined officer return needs explicit original principal and purpose evidence.')
        result = {'amount':str(value), 'cash_flow_purpose':purposes[0]}
    from finance.cash_flows import CASH_FLOW_CHOICES
    if result['cash_flow_purpose'] not in set(dict(CASH_FLOW_CHOICES)) - {'', 'internal'}:
        raise ValidationError('Retain an explicit external officer refund cash purpose.')
    return result


def principal(source):
    """Exact amount applied to the advance, including whole-source corrections."""
    if _digest(source.proposal) != source.proposal_checksum:
        raise ValidationError('The retained officer source changed.')
    reference = source.correction_of if source.kind == Source.CORRECTION else source
    if (reference is None or reference.kind not in (Source.RECEIPT, Source.CHEQUE_RETURN)
            or source.amount != reference.amount or _digest(reference.proposal) != reference.proposal_checksum
            or officer_data(source) != officer_data(reference)):
        raise ValidationError('Retain the exact whole original officer source for its correction.')
    data = officer_data(reference)
    value = amount(data.get('amount'))
    if value > reference.amount:
        raise ValidationError('Officer principal cannot exceed the actual receipt or bank amount.')
    if reference.kind == Source.CHEQUE_RETURN:
        if value != Decimal(basis(reference)['amount']):
            raise ValidationError('Retain the original officer return principal.')
    elif value != reference.amount or reference.proposal.get(KEY):
        if not reference.redemption_return_id:
            raise ValidationError('Only a source-linked officer redemption may include separately assessed charges.')
        expected = basis(reference.redemption_return)
        original = officer_data(reference.redemption_return)
        if (reference.proposal.get(KEY) != expected or value != Decimal(expected['amount'])
                or {k:v for k,v in data.items() if k != 'disbursement'}
                != {k:v for k,v in original.items() if k != 'disbursement'}):
            raise ValidationError('Retain the original officer identity, principal and purpose on the replacement receipt.')
    return value


def receipt_parts(receipt):
    """Return the known officer component and every other exact cash-purpose amount."""
    from .cheque_components import capture
    components = capture(receipt)
    value = principal(receipt)
    supplied = receipt.proposal.get(KEY)
    if supplied:
        officer = dict(supplied)
    elif len(components) == 1 and receipt.amount == value:
        officer = {'amount':str(value), 'cash_flow_purpose':components[0]['purpose']}
    else:
        raise ValidationError('Retain an explicit officer component before returning a combined instrument.')
    if amount(officer.get('amount')) != value:
        raise ValidationError('The officer cash component must equal the original refund principal.')
    remaining = {row['purpose']:amount(row['amount']) for row in components}
    purpose = officer.get('cash_flow_purpose')
    if remaining.get(purpose, Decimal('0')) < value:
        raise ValidationError('Retain the original officer amount within its actual cash purpose.')
    remaining[purpose] -= value
    return officer, {key:value for key,value in remaining.items() if value > 0}


def returned_debits(source, entry):
    """Retain every exact non-cash counterpart of a combined officer dishonour."""
    if not source.proposal.get('advance_cheque_return') or not source.proposal.get('officer_charge_returns'):
        raise ValidationError('Multiple return counterparts require retained officer and assessed-charge evidence.')
    from accounting.models import JournalSubsidiaryLine
    from .advance_cheque_returns import validate_journal
    validate_journal(entry)
    officer = entry.subsidiary_lines.get(category=JournalSubsidiaryLine.ADVANCE)
    rows = list(entry.lines.filter(debit__gt=0).select_related('account').order_by('sequence','pk'))
    cash = set(source.proposal['original_cheque']['collection_cash_accounts'])
    cash.add(source.proposal['receiving_bank']['ledger_account_id'])
    if (len(rows) < 2 or officer.debit != principal(source) or officer.credit
            or officer.journal_line_id not in {row.pk for row in rows}
            or sum((row.debit for row in rows),Decimal('0')) != source.amount
            or any(row.credit or row.cash_flow_category or row.account.account_type != 'asset'
                or row.account_id in cash
                or row.pk != officer.journal_line_id and row.account_id == officer.journal_line.account_id for row in rows)):
        raise ValidationError('Retain separate exact officer and charge receivables on the posted return.')
    return [next(row for row in rows if row.pk == officer.journal_line_id),
        *(row for row in rows if row.pk != officer.journal_line_id)]


def redemption_rows(owner, financial, total, proof):
    """Settle original return debit lines; never recognize old charges again."""
    components = proof.get('return_debits')
    if not components:
        return financial
    from .collections import account, financial_row
    from finance.models import FinancePostingRuleLine as Line
    cash = [row for row in financial if Decimal(row['debit']) > 0]
    credits, seen, subtotal = [], set(), Decimal('0')
    for component in components:
        value = amount(component['amount'])
        ledger = account(owner,component['account_code'])
        if (component['line'] in seen or ledger.pk != component['account_id'] or ledger.account_type != 'asset'
                or ledger.pk in {row['account_id'] for row in cash}):
            raise ValidationError('Retain each original returned receivable once, separate from collection cash.')
        seen.add(component['line']);subtotal += value
        credits.append(financial_row(ledger,value,Line.CREDIT))
    if len(credits) < 2 or subtotal != total:
        raise ValidationError('Original returned counterparts must reproduce the whole cheque amount.')
    return [*cash,*credits]


def return_rows(*, receipt, owner, release_id, fund_id, day, fund_code, snapshot, bank,
                cash_accounts, treatments, current=False):
    """Compose existing reviewed recipes without charging fees to the advance."""
    from .advance_cheque_returns import return_rows as officer_rows
    from .cheque_returns import rows as collection_rows
    officer, other = receipt_parts(receipt)
    financial = officer_rows(owner, snapshot, amount(officer['amount']), bank,
        [officer['cash_flow_purpose']], officer_data(receipt))
    debits, cash = [financial[0]], {financial[1]['cash_flow_category']:dict(financial[1])}
    if not isinstance(treatments, (list, tuple)):
        raise ValidationError('Choose one reviewed return treatment for each non-officer cash purpose.')
    selected = {}
    for supplied in treatments:
        if not isinstance(supplied, dict) or supplied.get('purpose') not in other or supplied['purpose'] in selected:
            raise ValidationError('Retain each original non-officer cash purpose once, with no missing or extra component.')
        selected[supplied['purpose']] = supplied
    if set(selected) != set(other):
        raise ValidationError('Choose a separate reviewed return treatment for every assessed-charge cash purpose.')
    retained = []
    for purpose, value in sorted(other.items()):
        supplied = selected[purpose]
        if 'amount' in supplied and amount(supplied['amount']) != value:
            raise ValidationError('Use the exact original non-officer component amount, without a residual allocation.')
        if current:
            try:
                variant = FinanceTransactionVariant.objects.get(public_id=supplied.get('variant'))
            except (FinanceTransactionVariant.DoesNotExist, ValueError, TypeError, ValidationError):
                raise ValidationError('Choose a reviewed collection-return type for each non-officer component.')
            if variant.department_id != owner or variant.release_id != release_id:
                raise ValidationError('Component return recipes must use the same approved Accounting setup.')
            variant, fund, rule, recipe, digest = context(variant, day, fund_code, Source.CHEQUE_RETURN)
            if fund.pk != fund_id:
                raise ValidationError('Retain the original officer refund fund for every return component.')
            component = {'purpose':purpose,'amount':str(value),'variant':str(variant.public_id),
                'code':variant.code,'label':variant.label,'posting_rule':str(rule.public_id),
                'posting_rule_snapshot':recipe,'posting_rule_checksum':digest}
        else:
            component = supplied
        recipe = component.get('posting_rule_snapshot')
        if (not isinstance(recipe,dict) or _digest(recipe) != component.get('posting_rule_checksum')
                or recipe.get('release_id') != release_id or recipe.get('variant_public_id') != component.get('variant')
                or recipe.get('rule_public_id') != component.get('posting_rule')
                or not recipe.get('authority_reference','').strip() or amount(component.get('amount')) != value):
            raise ValidationError('Retain each exact original charge amount and reviewed return recipe.')
        rows = collection_rows(owner,recipe,value,bank,cash_accounts,[purpose])
        debit = next(row for row in rows if Decimal(row['debit']) > 0)
        credit = next(row for row in rows if Decimal(row['credit']) > 0)
        if debit['account_id'] == financial[0]['account_id']:
            raise ValidationError('A returned charge cannot increase the original officer advance.')
        debits.append(debit)
        if purpose in cash:
            cash[purpose]['credit'] = str(Decimal(cash[purpose]['credit']) + value)
        else:
            cash[purpose] = credit
        retained.append(component)
    return [*debits,*cash.values()], retained
