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
        with self.assertNumQueries(0, using='default'), self.assertNumQueries(0, using='finance'):
            content = output.render_pdf(envelope)
            self.assertEqual(output.render_pdf(envelope), content)
        pages = PdfReader(BytesIO(content)).pages
        for page in pages: self.assertIn('INCOMPLETE DRAFT', page.extract_text())
        text = '\n'.join(page.extract_text() for page in pages)
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
        self.assertIn('Unknown', '\n'.join(page.extract_text() for page in PdfReader(BytesIO(unknown_content)).pages))
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
