"""Whole financial controls and original evidence; incomplete draft only."""
from datetime import datetime
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID
from xml.sax.saxutils import escape

from django.core.exceptions import ValidationError
from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from accounting.budget_actuals import money
from accounting.cash_classifications import checksum
from . import form1_assembly as assembly, form1_package_reviews as reviews, form1_spa_output as spa
from .form1_flows import COLUMNS


def verify(envelope):
    """Detached reproduction only; the export service authenticates actual sources."""
    try:
        data = envelope['payload']; original = data['original_package']; root = original['payload']
        state = data['internal_review']; identity = root['identity']
        if (checksum(data) != envelope['checksum'] or checksum(root) != original['checksum']
            or checksum(state['payload']) != state['checksum'] or data['kind'] != 'form1_whole_package_draft_export'
            or any(data[flag] is not False for flag in ('source_freshness_certified', 'statutorily_certified',
                'chief_executive_approved', 'form_issued', 'cash_available'))):
            raise ValidationError('Print the complete original draft without granting signatures or issuance.')
        body = assembly.verify(root['assembly'])
        record = SimpleNamespace(pk=1, public_id=UUID(identity['public_id']), payload=root,
            payload_checksum=original['checksum'], department_id=identity['department_id'],
            fund=SimpleNamespace(department_id=identity['accounting_department_id']),
            prepared_by_id=identity['prepared_by'], prepared_at=datetime.fromisoformat(identity['prepared_at']))
        rows = []
        for retained in state['payload']['decisions']:
            item = retained['payload']['identity']
            rows.append(SimpleNamespace(package_id=1, public_id=UUID(item['public_id']), role=item['role'],
                actor_id=item['actor_id'], actor_department_id=item['actor_department_id'], approve=item['approve'],
                decided_at=datetime.fromisoformat(item['decided_at']), payload=retained['payload'], payload_checksum=retained['checksum']))
        if reviews._state(record, body, rows) != state['payload']:
            raise ValidationError('Print the exact retained internal decisions and status.')
        return data, body
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        raise ValidationError('Invalid complete whole-package printable evidence.') from error


def render_pdf(envelope):
    data, body = verify(envelope)
    font = 'GRANDWholeForm1NotoSans'
    if font not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(font, str(Path(__file__).parent/'assets/NotoSans-Regular.ttf')))
    glyphs = pdfmetrics.getFont(font).face.charWidths
    style = ParagraphStyle('WholeForm1Cell', fontName=font, fontSize=8, leading=11, splitLongWords=True)
    def p(value):
        value = str(value)
        if any(not char.isspace() and ord(char) not in glyphs for char in value):
            raise ValidationError('The print font cannot render original characters; retain JSON and review font coverage.')
        return Paragraph(escape(value).replace('\n', '<br/>'), style)
    stream = BytesIO()
    doc = SimpleDocTemplate(stream, pagesize=landscape(A4), leftMargin=28, rightMargin=28,
        topMargin=38, bottomMargin=32, title='Whole Form 1 - incomplete draft', invariant=1)
    widths = [doc.width*.37, *[doc.width*.126]*5]
    def amount(value):
        text = 'Unknown' if value is None else f'{money(value):,.2f}'
        size = 8 if pdfmetrics.stringWidth(text, font, 8) <= widths[1]-12 else 6
        if pdfmetrics.stringWidth(text, font, size) > widths[1]-12:
            raise ValidationError('The complete amount exceeds the print width; review layout before printing.')
        return Paragraph(escape(text), ParagraphStyle('WholeAmount', parent=style, fontSize=size, alignment=2))
    def row(label, values):
        return [p(label), *[amount(values[column]) for column in COLUMNS]]
    def table(cells):
        result = Table(cells, colWidths=widths, repeatRows=1, hAlign='LEFT')
        result.setStyle(TableStyle([('GRID', (0,0), (-1,-1), .35, colors.HexColor('#a4afba')),
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#e7eef5')), ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('TOPPADDING', (0,0), (-1,-1), 5), ('BOTTOMPADDING', (0,0), (-1,-1), 5)]))
        return result
    story = []
    root = data['original_package']['payload']; identity = root['identity']
    ph = body['philhealth_source']['payload']; stock = ph['inventory']['payload']['stock']['payload']
    state = data['internal_review']['payload']
    for index, member in enumerate(body['members']):
        if index: story.append(PageBreak())
        year = member['scope']['budget_year']
        heading = [p(value) for value in ('Particulars', f'{year-2} Past year actual', f'{year-1} H1 actual',
            f'{year-1} H2 estimate', f'{year-1} Current total', f'{year} Proposed')]
        story.extend([p('WHOLE FORM 1 - INCOMPLETE DRAFT'), Spacer(1,8),
            p(f"{member['entity_label']} / {member['scope']['fund_code']} / Budget year {year}"),
            p('Not issued, statutorily certified or ready for signing. Internal review does not supply Chief Executive approval or cash capacity.'),
            p('Source freshness is not certified. Unknown controls remain unknown; zero is not missing evidence.'),
            p(f"Original package {identity['public_id']} / version {identity['version']} / internal state {state['status']}"),
            p('Original package checksum: '+data['original_package']['checksum']),
            p('Complete output evidence checksum: '+envelope['checksum']), Spacer(1,8)])
        cells = [heading, row('I. Beginning balance - net after original restrictions',
            {column:member['opening'][column]['net'] for column in COLUMNS})]
        cells += [row('II. Receipts - '+leaf['label'], leaf['amounts']) for leaf in member['receipt']['rows']]
        cells.append(row('Total receipts', member['receipt']['totals']))
        cells += [row('III. Expenditures - '+leaf['label'], leaf['amounts']) for leaf in member['expenditure']['rows']]
        cells.append(row('Total expenditures', member['expenditure']['totals']))
        cells.extend([row('IV. Ending balance - draft resources, not certified closing cash', member['resource_ending']),
            row('Less: PhilHealth payments for automatic appropriation under SHF', member['philhealth']['deduction']),
            row('V. Net ending balance', member['net_ending'])])
        story.extend([table(cells), Spacer(1,10), p('OPENING STOCK CALENDAR AND RECONCILIATION'),
            p('Current-total opening references H1 January stock once; it is not January plus July.'),
            p('Stock convention: '+stock['stock_convention']), p('Boundary basis: '+stock['boundary_basis'])])
        for column, cell in member['opening'].items():
            story.extend([Spacer(1,6), p(column+' / '+cell['kind']+' / scope '+str(cell['scope'])),
                p('Gross / restricted / net: '+str(cell['gross'])+' / '+str(cell['restricted'])+' / '+str(cell['net']))])
            if cell['kind'] == 'missing':
                story.append(p('Missing original stock; no cash or zero is inferred.'))
                continue
            source = cell['source']; source_body = source['payload']
            story.append(p('Original stock checksum: '+source['checksum']))
            actual = source_body if cell['kind'] == 'actual' else source_body['source']['payload']
            story.append(p('Original actual source: '+actual['route']+' / '+actual['public_id']))
            for restriction in actual['restrictions']:
                story.append(p('Original restriction: '+str(restriction)))
            if cell['kind'] == 'forecast':
                story.append(p('Forecast worksheet: '+str(source_body['evidence'])))
                for key, value in source_body['inputs'].items():
                    for item in value if isinstance(value, list) else [value]:
                        story.append(p('Forecast '+key+': '+str(item)))
        story.extend([Spacer(1,10), p('PHILHEALTH SIGNED PARTS AND COVERAGE'), p('Coverage basis: '+ph['coverage_reference'])])
        for part in member['philhealth']['source_parts']:
            source = part['original_source']
            story.extend([Spacer(1,5), p(f"Part {part['key']} / {source['column']} / {source['kind']} / signed {part['amount']} / {part['treatment']}"),
                p('Original source '+part['source']+' / capacity '+source['capacity_identity']+' / counterpart '+part['counterpart']), p('Basis: '+part['basis'])])
        for cell in ph['coverage']:
            if cell['entity'] == member['entity_key']: story.append(p('Coverage: '+str(cell)))
        story.append(p('Pending overlap or treatment: '+str(member['philhealth']['pending_overlap_or_treatment'])))
    story.extend([PageBreak(), p('INTERNAL WHOLE-PACKAGE REVIEW - NOT STATUTORY SIGNATURES'), p('Required reviews: '+str(state['required_reviews']))])
    for decision in state['decisions']:
        item = decision['payload']
        story.extend([Spacer(1,8), p('Decision: '+str(item['identity'])), p('Authority: '+item['authority']), p('Reason: '+item['note']), p('Checksum: '+decision['checksum'])])
        for key, value in item['checks'].items(): story.append(p(key+': '+str(value)))
    story.append(p('ORIGINAL DOCUMENT INDEX - use the complete ZIP for original bytes'))
    for item in data['documents']: story.append(p(str(item)))
    def footer(canvas, document):
        canvas.setFont('Helvetica', 7)
        canvas.drawString(28,18,'INCOMPLETE DRAFT | '+identity['public_id']+' | '+envelope['checksum'][:16])
        canvas.drawRightString(landscape(A4)[0]-28,18,f'Whole controls page {document.page}')
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    writer = PdfWriter()
    for content in (stream.getvalue(), spa.render_pdf(body['spa_source'])):
        writer.append(PdfReader(BytesIO(content)))
    writer.add_metadata({'/Title':'Whole Form 1 - incomplete draft', '/Subject':envelope['checksum']})
    result = BytesIO(); writer.write(result)
    return result.getvalue()
