"""Pure complete signing-copy output; no signature, approval, final issuance or cash grant."""
from copy import deepcopy
from datetime import datetime
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID
from xml.sax.saxutils import escape

from django.core.exceptions import ValidationError
from django.utils import timezone
from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether

from accounting.budget_actuals import money
from accounting.cash_classifications import checksum
from accounting.summary_actuals import text
from . import form1_package_print as originals, form1_signing as signing
from .form1_flows import COLUMNS
from .form1_integrity import operation

CERTIFICATION = ('We hereby certify that the information presented are true and correct. '
    'We further certify that the foregoing estimated receipts are reasonably projected as collectible for the Budget Year.')
FALSE_FLAGS = ('statutorily_certified', 'chief_executive_approved', 'form_issued', 'cash_available')


@operation
def verify(envelope):
    """Reproduce retained values; actual source/actor authorization belongs to the service."""
    try:
        data = envelope['payload']; identity = data['identity']
        if (set(envelope) != {'payload', 'checksum'} or checksum(data) != envelope['checksum']
                or set(data) != {'schema', 'kind', 'identity', 'original_package', 'designation', 'reference',
                                 'source_current_observed', 'unsigned_copy_issued', *FALSE_FLAGS}
                or type(data['schema']) is not int or data['schema'] != 1 or data['kind'] != 'form1_unsigned_signing_copy'
                or data['source_current_observed'] is not True or data['unsigned_copy_issued'] is not True
                or any(data[key] is not False for key in FALSE_FLAGS)
                or text(data['reference'], 'signing-copy release reference') != data['reference']):
            raise ValidationError('Retain an unsigned copy without inferring actual signatures or final issuance.')
        source, body = originals.verify(data['original_package'])
        if not body['calculation_coverage_complete'] or source['internal_review']['payload']['status'] != 'reviewed':
            raise ValidationError('Release only complete internally reviewed financial sources.')
        root = source['original_package']; root_identity = root['payload']['identity']
        designation = data['designation']; preparation = designation['payload']; person_identity = preparation['identity']
        review = designation['review']; decision = review['payload']; actor = decision['identity']
        day = signing._day(person_identity['document_date'])
        expected_source = dict(package=root_identity['public_id'], package_checksum=root['checksum'],
            assembly_checksum=root['payload']['assembly']['checksum'],
            internal_review=source['internal_review']['payload'], internal_review_checksum=source['internal_review']['checksum'])
        if (checksum(preparation) != designation['payload_checksum'] or checksum(decision) != review['payload_checksum']
                or designation['status'] != 'reviewed_preparation'
                or preparation['source'] != expected_source
                or preparation['lgu'] != signing._lgu(SimpleNamespace(payload=root['payload']))
                or preparation['kind'] != 'form1_signing_preparation' or preparation['schema'] != 1
                or signing._signatories(preparation['signatories'], day) != preparation['signatories']
                or any(preparation[key] is not False or designation[key] is not False for key in signing.FLAGS)
                or decision['source_current_observed'] is not True or actor['approve'] is not True
                or actor['preparation'] != person_identity['public_id']
                or actor['preparation_checksum'] != designation['payload_checksum']
                or actor['actor_id'] in (person_identity['prepared_by'], root_identity['prepared_by'])
                or actor['actor_department_id'] != person_identity['department_id']
                or person_identity['department_id'] != root_identity['department_id']
                or person_identity['package'] != root_identity['public_id']
                or signing._checks(decision['checks']) != decision['checks']
                or not all(row['verified'] for row in decision['checks'].values())):
            raise ValidationError('Retain the exact complete source and independently reviewed designation version.')
        if (set(identity) != {'public_id', 'preparation', 'package', 'department_id', 'department_label',
                             'released_by', 'released_by_label', 'released_at'}
                or str(UUID(identity['public_id'])) != identity['public_id']
                or identity['preparation'] != person_identity['public_id'] or identity['package'] != root_identity['public_id']
                or identity['department_id'] != root_identity['department_id']
                or type(identity['released_by']) is not int or identity['released_by'] <= 0
                or identity['released_by'] in (person_identity['prepared_by'], root_identity['prepared_by'])
                or text(identity['department_label'], 'original Budget department', 160) != identity['department_label']
                or text(identity['released_by_label'], 'release actor label', 160) != identity['released_by_label']):
            raise ValidationError('Retain the original independent copy-release identity.')
        released_at = datetime.fromisoformat(identity['released_at'])
        reviewed_at = datetime.fromisoformat(actor['decided_at'])
        prepared_at = datetime.fromisoformat(person_identity['prepared_at'])
        source_reviewed_at = max(datetime.fromisoformat(row['payload']['identity']['decided_at'])
            for row in source['internal_review']['payload']['decisions'])
        if (not timezone.is_aware(released_at) or not timezone.is_aware(reviewed_at)
                or not timezone.is_aware(prepared_at) or released_at < reviewed_at or reviewed_at < prepared_at
                or prepared_at < source_reviewed_at or day < timezone.localtime(source_reviewed_at).date()):
            raise ValidationError('Retain actual preparation, review and release chronology.')
        return deepcopy(data), body
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        raise ValidationError('Invalid complete Form 1 signing-copy evidence.') from error


@operation
def render_pdf(envelope):
    data, body = verify(envelope)
    people = data['designation']['payload']['signatories']
    identity = data['identity']
    font = 'GRANDForm1SigningNotoSans'
    if font not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(font, str(Path(__file__).parent / 'assets/NotoSans-Regular.ttf')))
    glyphs = pdfmetrics.getFont(font).face.charWidths
    style = ParagraphStyle('SigningText', fontName=font, fontSize=8, leading=11, splitLongWords=True)

    def p(value):
        value = str(value)
        if any(not char.isspace() and ord(char) not in glyphs for char in value):
            raise ValidationError('The signing-copy font cannot render original source characters.')
        return Paragraph(escape(value).replace('\n', '<br/>'), style)

    target = BytesIO()
    doc = SimpleDocTemplate(target, pagesize=landscape(A4), leftMargin=28, rightMargin=28,
        topMargin=30, bottomMargin=36, title='LBP Form No. 1 - unsigned signing copy', invariant=1)
    widths = [doc.width * .29, doc.width * .13, *[doc.width * .116] * 5]

    def amount(value):
        if value is None:
            raise ValidationError('Unknown financial controls cannot be released for signing.')
        rendered = f'{money(value):,.2f}'
        size = 8 if pdfmetrics.stringWidth(rendered, font, 8) <= widths[2]-10 else 6
        if pdfmetrics.stringWidth(rendered, font, size) > widths[2]-10:
            raise ValidationError('Review the layout before releasing an amount that exceeds its column width.')
        return Paragraph(rendered, ParagraphStyle('SigningAmount', parent=style, fontSize=size, alignment=2))

    def row(label, code, values):
        return [p(label), p(code), *[amount(values[column]) for column in COLUMNS]]

    def table(cells, scope):
        result = Table([[p(scope), *['']*6], *cells], colWidths=widths, repeatRows=2, hAlign='LEFT')
        result.setStyle(TableStyle([('GRID', (0,0), (-1,-1), .35, colors.HexColor('#949da6')),
            ('SPAN', (0,0), (-1,0)), ('BACKGROUND', (0,0), (-1,1), colors.HexColor('#e7eef5')), ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('TOPPADDING', (0,0), (-1,-1), 4), ('BOTTOMPADDING', (0,0), (-1,-1), 4)]))
        return result

    story = []
    for index, member in enumerate(body['members']):
        if index:
            story.append(PageBreak())
        year = member['scope']['budget_year']
        heading = [p(value) for value in ('Particulars', 'Account code', f'{year-2}\nPast year (Actual)',
            f'{year-1}\nFirst semester (Actual)', f'{year-1}\nSecond semester (Estimate)',
            f'{year-1}\nCurrent year total', f'{year}\nBudget year (Proposed)')]
        scope = f"{member['entity_label']} / Fund {member['scope']['fund_code']} / Budget year {year}"
        story.extend([p('LBP FORM NO. 1 - BUDGET OF EXPENDITURES AND SOURCES OF FINANCING'),
            p('LGU: '+data['designation']['payload']['lgu']), p(scope),
            p('UNSIGNED COPY FOR PHYSICAL CERTIFICATION AND APPROVAL'),
            p('Intended document date: '+data['designation']['payload']['identity']['document_date']),
            p('No signature, Chief Executive approval, final issuance or cash authority is established by this copy.'),
            p('Copy ID: '+identity['public_id']), Spacer(1,8)])
        story.append(table([heading, row('I. Beginning cash balance - net of retained restrictions', '',
            {column: member['opening'][column]['net'] for column in COLUMNS})], scope))
        story.extend([Spacer(1,8), p('II. RECEIPTS')])
        nodes = {leaf['category']: leaf for leaf in member['receipt']['rows']}
        groups = {group['key']: group for group in member['receipt']['hierarchy']}
        receipt_rows = [heading]

        def receipt(key, depth=0):
            if key in nodes:
                leaf = nodes[key]
                receipt_rows.append(row('  '*depth+leaf['label']+' - source control', '', leaf['amounts']))
                for account_row in leaf['accounts']:
                    account = account_row['account']
                    receipt_rows.append(row(('  '*(depth+1))+(account['title'] if account else 'Explicit zero without account'),
                        account['government_account_code'] if account else '', account_row['amounts']))
                return
            group = groups[key]
            if key != 'total':
                receipt_rows.append([p('  '*depth+group['label'].replace('Total ', '', 1)), *['']*6])
            for child in group['children']:
                receipt(child, depth+1)
            receipt_rows.append(row('  '*depth+group['label'], '', group['amounts']))

        receipt('total')
        story.extend([table(receipt_rows, scope), Spacer(1,8), p('III. EXPENDITURES')])
        cells = [heading]
        for leaf in member['expenditure']['rows']:
            cells.append(row(leaf['label']+' - source control', '', leaf['amounts']))
            for account_row in leaf['accounts']:
                account = account_row['account']
                cells.append(row('  '+(account['title'] if account else 'Explicit zero without account'),
                    account['government_account_code'] if account else '', account_row['amounts']))
            if leaf['category'] == 'spa':
                for subdivision in member['spa']['rows']:
                    cells.append(row('  '+subdivision['label']+' - subdivision control', '', subdivision['amounts']))
                    for account_row in subdivision['accounts']:
                        account = account_row['account']
                        cells.append(row('    '+(account['title'] if account else 'Explicit zero without account'),
                            account['government_account_code'] if account else '', account_row['amounts']))
        cells.extend([row('Total Expenditures', '', member['expenditure']['totals']),
            row('IV. Ending Balance', '', member['resource_ending']),
            row('Less: PhilHealth Payments for Automatic Appropriation for the Expenditures under Special Health Fund', '', member['philhealth']['deduction']),
            row('V. Net Ending Balance', '', member['net_ending'])])
        story.extend([table(cells, scope), Spacer(1,8), p('Category, account and subdivision controls describe the same money; do not add them together.')])
        # A separate signing page keeps every signature with its complete entity/
        # fund scope and exact issued-copy identity even for long financial tables.
        blocks = [p('CERTIFICATION AND APPROVAL - UNSIGNED'), p(scope),
            p('LGU: '+data['designation']['payload']['lgu']), p('Copy ID: '+identity['public_id']),
            Spacer(1,8), p(CERTIFICATION), Spacer(1,14)]
        signatures = []
        for role in list(signing.ROLES)[:4]:
            person = people[role]
            signatures.append(p('Signature: ____________________\nDate signed: ____________________\n'
                +person['name']+'\n'+person['position']+'\n'+signing.ROLES[role]))
        signature_table = Table([signatures], colWidths=[doc.width/4]*4, hAlign='LEFT')
        signature_table.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),0),
            ('RIGHTPADDING',(0,0),(-1,-1),12)]))
        person = people['chief_executive']
        blocks.extend([signature_table, Spacer(1,24), p('Approved by:'), Spacer(1,12),
            p('Signature: ____________________\nDate approved: ____________________\n'+person['name']+'\n'
              +person['position']+'\n'+signing.ROLES['chief_executive']), Spacer(1,14),
            p('Unsigned copy only. Actual physical certification and approval must be received and independently verified.'),
            p('Original package SHA-256: '+data['original_package']['payload']['original_package']['checksum']),
            p('Designation preparation SHA-256: '+data['designation']['payload_checksum']),
            p('Copy evidence SHA-256: '+envelope['checksum'])])
        story.extend([PageBreak(), KeepTogether(blocks)])

    def footer(canvas, document):
        canvas.setFont('Helvetica', 7)
        canvas.drawString(28, 18, 'UNSIGNED | '+identity['public_id']+' | '+envelope['checksum'][:16])

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    reader = PdfReader(BytesIO(target.getvalue())); writer = PdfWriter()
    for index, page in enumerate(reader.pages, 1):
        stamp = BytesIO(); canvas = pdf_canvas.Canvas(stamp, pagesize=landscape(A4), invariant=1)
        canvas.setFont('Helvetica', 7); canvas.drawRightString(landscape(A4)[0]-28,18,f'Page {index} of {len(reader.pages)}')
        canvas.save(); page.merge_page(PdfReader(BytesIO(stamp.getvalue())).pages[0]); writer.add_page(page)
    writer.add_metadata({'/Title':'LBP Form No. 1 - unsigned signing copy','/Subject':envelope['checksum']})
    result = BytesIO(); writer.write(result)
    return result.getvalue()
