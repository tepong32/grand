from copy import deepcopy
from io import BytesIO
from pathlib import Path
import os

from django.core.exceptions import ValidationError
from django.urls import reverse
from pypdf import PdfReader
from accounting.cash_classifications import checksum
from . import test_form1_package_reviews as fixtures
from . import form1_package_exports as exports, form1_package_print as output


class Form1PackagePrintTests(fixtures.Form1PackageReviewFixture):
    def test_whole_controls_original_evidence_pure_deterministic_http_pdf_and_unknowns(self):
        record = self.retain()
        for role in self.reviewers: self.decide_package(record, role)
        envelope, files = exports.capture(record, self.treasurer)
        original_envelope = deepcopy(envelope)
        with self.assertNumQueries(0, using='default'), self.assertNumQueries(0, using='finance'):
            content = output.render_pdf(envelope)
            self.assertEqual(output.render_pdf(envelope), content)
        self.assertEqual(envelope, original_envelope)
        pages = PdfReader(BytesIO(content)).pages
        for page in pages: self.assertIn('INCOMPLETE DRAFT', page.extract_text())
        text = '\n'.join(page.extract_text() for page in pages)
        flow = record.payload['assembly']['payload']['philhealth_source']['payload']['inventory']['payload']['stock']['payload']['flow']['payload']
        lgu = flow['sources']['reconciliations'][0]['payload']['forms'][0]['payload']['lgu']
        self.assertIn('LGU: ' + lgu, text)
        # Identification must remain source-scoped and honest for older/mixed evidence.
        from .form1_package_print import _source_lgu_text
        def identity_flow(names, entity='general'):
            return {'sources': {'reconciliations': [{'payload': {'entity_key': entity,
                'forms': [{'payload': {'lgu': name}} for name in names]}}]}}
        self.assertIn('Unknown', _source_lgu_text(identity_flow([]), 'general'))
        self.assertIn('Unknown', _source_lgu_text(identity_flow([lgu, '']), 'general'))
        self.assertIn('Unknown', _source_lgu_text(identity_flow([lgu], entity='another'), 'general'))
        self.assertIn('conflicting', _source_lgu_text(identity_flow([lgu, lgu.lower()]), 'general'))
        mixed = identity_flow([lgu])
        mixed['sources']['reconciliations'] += identity_flow([lgu.lower()], entity='enterprise')['sources']['reconciliations']
        self.assertIn('conflicting', _source_lgu_text(mixed, 'general'))
        self.assertIn('LGU: ' + lgu, _source_lgu_text(identity_flow([lgu, lgu]), 'general'))
        for index, page in enumerate(pages, 1):
            self.assertIn(f'Page {index} of {len(pages)}', page.extract_text())
        self.assertNotIn('Whole controls page', text)
        for serialized in ("{'department_id':", "{'verified':", "{'key':", "{'role':"):
            self.assertNotIn(serialized, text)
        for phrase in ('Current year H1 actual', 'Budget department ID:', 'Restriction lineage:',
                       'Verified: Yes', 'SHA256:'):
            self.assertIn(phrase, text)
        for phrase in ('Beginning balance', 'Ending balance', 'Net ending balance', 'PHILHEALTH SIGNED PARTS',
            'OPENING STOCK CALENDAR', 'ORIGINAL SOURCE SHARES', 'SPA SUBDIVISIONS', 'NOT STATUTORY SIGNATURES'):
            self.assertIn(phrase, text)
        for member in record.payload['assembly']['payload']['members']:
            for part in member['philhealth']['source_parts']: self.assertIn(part['key'], text)
            for cell in member['opening'].values(): self.assertIn(cell['source']['checksum'], text)
        for row in envelope['payload']['internal_review']['payload']['decisions']:
            self.assertIn(row['checksum'], text)
        for row in envelope['payload']['documents']: self.assertIn(row['sha256'], text)
        self.client.force_login(self.treasurer)
        response = self.client.get(reverse('budget:form1_package_export', args=(record.public_id, 'pdf')))
        self.assertEqual(response.status_code, 200); self.assertEqual(response.content, content)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.ph_source, self.documents = self.ph_draft(attach=False)
        self.envelope = self.assembled(); unknown = self.retain(expected_latest=1)
        unknown_envelope, _ = exports.capture(unknown, self.checker)
        unknown_content = output.render_pdf(unknown_envelope)
        unknown_pages = PdfReader(BytesIO(unknown_content)).pages
        self.assertIn('Unknown', '\n'.join(page.extract_text() for page in unknown_pages))
        for index, page in enumerate(unknown_pages, 1):
            self.assertIn(f'Page {index} of {len(unknown_pages)}', page.extract_text())
        changed = deepcopy(envelope)
        changed['payload']['original_package']['payload']['assembly']['payload']['members'][0]['net_ending']['proposed'] = '999.00'
        original = changed['payload']['original_package']; root = original['payload']
        root['assembly']['checksum'] = checksum(root['assembly']['payload']); original['checksum'] = checksum(root)
        changed['checksum'] = checksum(changed['payload'])
        with self.assertRaises(ValidationError): output.render_pdf(changed)
        # Private isolated fixture artifacts for actual visual review, not operator output.
        configured = os.environ.get('GRAND_PRINT_VERIFICATION_ROOT')
        if configured:
            target = Path(configured).resolve()
            target.relative_to((Path(__file__).resolve().parents[1]/'.tmp').resolve())
            target.mkdir(parents=True, exist_ok=True)
            (target/'whole-reviewed.pdf').write_bytes(content)
            (target/'whole-unknown.pdf').write_bytes(unknown_content)
