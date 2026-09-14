"""Dated, unchanged liquidation history retained by an original advance correction."""
from django.core.exceptions import ValidationError

from accounting.claim_attributions import _exact_reversal
from .advance_sources import posted_request


def journal_evidence(request, entry):
    from .advance_recognition_corrections import rows, subsidiaries
    return {'request': str(request.public_id), 'payload_checksum': request.payload_checksum,
        'rule_checksum': request.posting_rule_checksum, 'entry': str(entry.public_id),
        'fund': entry.fund_id, 'department': entry.department_id,
        'entry_date': entry.entry_date.isoformat(), 'source_snapshot': entry.source_snapshot,
        'lines': rows(entry), 'subsidiaries': subsidiaries(entry)}


def evidence(detail, case, day, *, retained=None):
    """Capture fully validated sources before reversal; later reproduce their exact bytes.

    Ordinary liquidation validation requires an unreversed original advance. It is
    therefore used at capture, before the original correction exists. Replay verifies
    independently posted, exact mirrored journals and the complete retained evidence
    without recursively trying to authorize a new use of the reversed original asset.
    """
    from .advance_applications import applications
    from .liquidation_corrections import corrections, validate
    result = []
    for application in applications(case, detail):
        fixes = corrections(application)
        if (application.status != application.POSTED or len(fixes) != 1
                or fixes[0].status != fixes[0].POSTED or fixes[0].jev_date > day):
            raise ValidationError('Resolve and retain linked advance liquidation/refund corrections before original recognition correction.')
        fix = fixes[0]
        original = posted_request(application, allow_reversal_reference=fix.public_id)
        reversal = posted_request(fix)
        if (not _exact_reversal(reversal, original)
                or original.entry_date > reversal.entry_date or reversal.entry_date > day
                or fix.payload['advance_application_correction']['original_request'] != str(application.public_id)):
            raise ValidationError('Retain the exact dated correction of each original advance liquidation.')
        if retained is None:
            validate(reversal)
        result.append({'application': journal_evidence(application, original),
                       'correction': journal_evidence(fix, reversal)})
    result.sort(key=lambda row: row['application']['request'])
    if retained is not None and result != retained:
        raise ValidationError('The retained corrected liquidation history changed after original advance correction preparation.')
    return result
