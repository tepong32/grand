"""Complete, bounded row transcription from CSV; original certifications stay separate."""
import csv
import io

from django.core.exceptions import ValidationError

from .models import LedgerAccount

COLUMNS = ('kind', 'category', 'account_code', 'amount', 'source_row')
MAX_BYTES = 2 * 1024 * 1024
MAX_ROWS = 10000


def parse(upload, owner_id):
    raw = upload.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValidationError('The row CSV exceeds 2 MiB; no rows were imported.')
    try:
        content = raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        raise ValidationError('Save the row file as UTF-8 CSV; no rows were imported.')
    if '\x00' in content:
        raise ValidationError('The CSV contains invalid text; no rows were imported.')
    accounts = {}
    for account in LedgerAccount.objects.filter(department_id=owner_id):
        accounts.setdefault(account.code.casefold(), []).append(account.pk)
    try:
        reader = csv.DictReader(io.StringIO(content, newline=''), strict=True)
        if tuple(reader.fieldnames or ()) != COLUMNS:
            raise ValidationError('Use exactly these CSV columns, in order: ' + ', '.join(COLUMNS))
        result = []
        for number, row in enumerate(reader, 2):
            if len(result) >= MAX_ROWS:
                raise ValidationError('The CSV exceeds 10,000 rows; no rows were imported.')
            if None in row or any(value is None for value in row.values()):
                raise ValidationError(f'CSV row {number}: use exactly five columns; quote values containing commas.')
            values = {key: value.strip() for key, value in row.items()}
            if any(not values[key] for key in ('kind', 'category', 'amount', 'source_row')):
                raise ValidationError(f'CSV row {number}: kind, category, amount and source row are required.')
            if any(len(values[key]) > limit for key, limit in
                (('kind', 12), ('category', 40), ('account_code', 40), ('amount', 32), ('source_row', 255))):
                raise ValidationError(f'CSV row {number}: a value exceeds its field length; no rows were imported.')
            matching = accounts.get(values['account_code'].casefold(), []) if values['account_code'] else []
            if values['account_code'] and len(matching) != 1:
                raise ValidationError(f'CSV row {number}: account code must identify exactly one account in this ledger.')
            result.append({key: values[key] for key in ('kind', 'category', 'amount', 'source_row')} |
                {'account_id': matching[0] if matching else None, '_csv_account_code': values['account_code']})
    except csv.Error:
        raise ValidationError('The CSV is malformed; check quoting and field lengths. No rows were imported.')
    if not result:
        raise ValidationError('The CSV has no source rows. Missing is not certified zero.')
    return result
