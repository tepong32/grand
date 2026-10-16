"""Complete source-authorized whole-package drafts, never issued Form 1 copies."""
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
import json
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

from django.core.exceptions import ValidationError
from django.db import transaction
from accounting.cash_classifications import checksum
from accounting.models import Fund
from .models import BudgetVersion, Form1Package
from . import form1_packages as packages, form1_package_reviews as reviews


def json_bytes(envelope):
    return json.dumps(envelope, ensure_ascii=False, sort_keys=True, indent=2).encode('utf-8')


def _extension(data):
    # Archive paths never contain original filenames or caller-supplied paths.
    return '.pdf' if data.startswith(b'%PDF-') else '.png' if data.startswith(b'\x89PNG') else '.jpg' if data.startswith(b'\xff\xd8') else '.bin'


@transaction.atomic(using='finance')
def capture(record, actor):
    """Capture one complete decision set under the existing owning lock order.

    Source currentness is not asserted by a historical draft export. Original
    model/byte and export authority checks remain mandatory even for stale roots.
    """
    proposal = BudgetVersion.objects.select_for_update().get(pk=record.proposal_id)
    fund = Fund.objects.select_for_update().get(pk=record.fund_id)
    record = Form1Package.objects.select_for_update().get(pk=record.pk, proposal=proposal, fund=fund)
    record = packages._read(record, actor, export=True)
    state = reviews._state(record, record.payload['assembly']['payload'], list(record.decisions.all()))
    return _retained(record, state)


def _retained(record, state):
    """Original evidence only; caller must authorize actual source read/export first."""
    originals = [(row.key, record.payload['attachments'][row.key], bytes(row.data))
        for row in record.attachments.all()]
    # These source documents are already authenticated by packages._sources.
    spa = record.spa_review
    originals.extend((('source:spa', spa.payload['evidence'], bytes(spa.evidence)),
        ('source:account', spa.account_review.payload['evidence'], bytes(spa.account_review.evidence))))
    files = {}; index = []
    for number, (key, metadata, data) in enumerate(sorted(originals, key=lambda row: row[0]), 1):
        if sha256(data).hexdigest() != metadata['sha256']:
            raise ValidationError('Export the exact original source document bytes.')
        path = f'attachments/{number:04d}{_extension(data)}'
        files[path] = data
        index.append(dict(key=key, path=path, original=deepcopy(metadata), size=len(data), sha256=sha256(data).hexdigest()))
    body = dict(schema=1, kind='form1_whole_package_draft_export',
        original_package=dict(payload=deepcopy(record.payload), checksum=record.payload_checksum),
        internal_review=dict(payload=state, checksum=checksum(state)), documents=index,
        source_freshness_certified=False, statutorily_certified=False,
        chief_executive_approved=False, form_issued=False, cash_available=False)
    return dict(payload=body, checksum=checksum(body)), files


def _zip(envelope, files):
    target = BytesIO()
    contents = {'package.json': json_bytes(envelope), **files}
    with ZipFile(target, 'w') as archive:
        for path, data in sorted(contents.items()):
            info = ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            archive.writestr(info, data)
    return target.getvalue()


def export(record, actor, *, kind):
    if kind not in ('json', 'zip', 'pdf'):
        raise ValidationError('Choose complete draft JSON, original-document ZIP or printable PDF.')
    envelope, files = capture(record, actor)
    if kind == 'pdf':
        from .form1_package_print import render_pdf
        return render_pdf(envelope), envelope
    return (json_bytes(envelope) if kind == 'json' else _zip(envelope, files)), envelope
