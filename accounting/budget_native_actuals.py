"""Same-observation receipt/expenditure preparation; not joint certification."""
from copy import deepcopy
from datetime import date

from django.core.exceptions import PermissionDenied, ValidationError

from . import budget_receipt_cohorts as receipts
from . import budget_receipt_attributions as receipt_reviews
from . import budget_native_certifications as native_access
from . import budget_native_periods as periods
from . import budget_native_statements as expenditures
from .cash_classifications import checksum


def project(receipt_cohort):
    """Use trusted retained server evidence only; never fetch newer expense heads."""
    body = receipts.verify(receipt_cohort)
    scope = body['scope']
    source = periods.reframe(body['inventory']['payload']['ledger'],
        period_start=date.fromisoformat(scope['period_start']),
        period_end=date.fromisoformat(scope['period_end']))
    statement = expenditures.project(source)
    if statement['payload']['scope'] != scope:
        raise ValidationError('Receipt and expenditure preparation must retain the same exact Fund and period.')
    receipt_ids = {row['entry_id'] for row in body['inventory']['payload']['journals']}
    if receipt_ids != {row['id'] for row in source['payload']['journals']}:
        raise ValidationError('Receipt and expenditure preparation must cover the same complete activity cohort.')
    payload = {'schema': 1, 'kind': 'native_budget_actuals_preparation',
        'scope': deepcopy(scope), 'receipts': deepcopy(receipt_cohort),
        'expenditure_source': source, 'expenditures': statement,
        'classification_complete': body['classification_complete'] and statement['payload']['classification_complete'],
        'receipt_total': None, 'expenditure_total': None,
        'category_coverage': 'not_declared', 'entity_coverage': 'not_declared',
        'certification_status': 'not_certified'}
    return {'payload': payload, 'checksum': checksum(payload),
        'source_checksum': checksum({'receipts': receipt_cohort['source_checksum'],
            'expenditures': source['checksum']})}


def capture(*, actor, fund_id, period_start, period_end):
    # Each side retains its existing read boundary. One capability must not
    # silently confer access to the other side's independently reviewed evidence.
    if (not any(receipt_reviews.permitted(actor, action) for action in ('view', 'prepare', 'review', 'export'))
            or not any(native_access.permitted(actor, action) for action in ('view', 'prepare', 'certify', 'export'))):
        raise PermissionDenied
    cohort = receipts.capture(actor=actor, fund_id=fund_id,
        period_start=period_start, period_end=period_end)
    return project(cohort)


def verify(captured):
    try:
        reproduced = project(captured['payload']['receipts'])
        if reproduced != captured:
            raise ValidationError('Native actuals no longer reproduce the same retained source observation.')
        return captured['payload']
    except (KeyError, TypeError, ValueError, ArithmeticError) as error:
        raise ValidationError('Invalid retained native actuals preparation.') from error


def _capture_for_owner(*, owner, fund_id, period_start, period_end):
    """Internal exact-owner read after dedicated joint role authorization."""
    return project(receipts._capture_for_owner(owner=owner, fund_id=fund_id,
        period_start=period_start, period_end=period_end))


def is_current(captured, actor):
    scope = verify(captured)['scope']
    fresh = capture(actor=actor, fund_id=scope['fund']['id'],
        period_start=date.fromisoformat(scope['period_start']), period_end=date.fromisoformat(scope['period_end']))
    return fresh['source_checksum'] == captured['source_checksum']
