"""Printable seven-column unsigned office Form 2, with retained evidence annex."""
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from django.core.exceptions import ValidationError
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from .office_forms import AMOUNTS, CLASSES, ROLES


def render_document(data):
    font = 'GRANDOfficeNotoSans'
    if font not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(font, str(Path(__file__).parent / 'assets/NotoSans-Regular.ttf')))
    glyphs = pdfmetrics.getFont(font).face.charWidths
    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=landscape(A4), rightMargin=28, leftMargin=28,
        topMargin=45, bottomMargin=32, title='LBP Form No. 2 - unsigned copy')
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='FormCell', fontName=font, fontSize=8, leading=10))
    def p(text):
        text = str(text)
        missing = sorted({ord(char) for char in text if not char.isspace() and ord(char) not in glyphs})
        if missing:
            raise ValidationError('The bundled print font cannot render ' + ', '.join(f'U+{code:04X}' for code in missing) + '. Add reviewed font coverage before issuance.')
        return Paragraph(escape(text), styles['FormCell'])
    def amount(value):
        text = f'{Decimal(value):,.2f}'
        style = ParagraphStyle(name='Amount', fontName=font, fontSize=6 if len(text) > 20 else 8,
            leading=10, alignment=2)
        return Paragraph(text, style)
    schedule = data['schedule']
    story = [p('LBP Form No. 2 - UNSIGNED COPY FOR PHYSICAL SIGNING'), Spacer(1, 8),
        Paragraph('PROGRAMMED APPROPRIATION AND OBLIGATION BY OBJECT OF EXPENDITURE', styles['Heading2']),
        p(f"LGU: {data['lgu']}"), p(f"Office: {schedule['office_label']}"),
        p(f"Fund: {schedule['fund_code']} - {data['fund_scope']}"), Spacer(1, 10)]
    headings = ['Object of Expenditure', 'Account Code', f"{schedule['prior_year']} Past Year (Actual)",
        f"{schedule['current_year']} First Semester (Actual)", f"{schedule['current_year']} Second Semester (Estimates)",
        f"{schedule['current_year']} Total", f"{schedule['budget_year']} Budget Year (Proposed)"]
    cells = [[p(value) for value in headings]]
    category_indices = []
    for category, title in CLASSES.items():
        rows = [row for row in schedule['rows'] if row['category'] == category]
        if not rows:
            continue
        category_indices.append(len(cells))
        cells.append([p(title), '', *['' for _ in AMOUNTS]])
        for row in rows:
            cells.append([p(row['account_title']), p(row['account_code']), *[amount(row[name]) for name in AMOUNTS]])
        cells.append([p('Subtotal - ' + title), '',
            *[amount(sum((Decimal(row[name]) for row in rows), Decimal('0.00'))) for name in AMOUNTS]])
    cells.append([p('TOTAL'), '', *[amount(schedule['totals'][name]) for name in AMOUNTS]])
    width = doc.width
    table = Table(cells, colWidths=[width * .24, width * .115, *[width * .129 for _ in AMOUNTS]], repeatRows=1)
    rules = [('GRID', (0, 0), (-1, -1), .4, colors.HexColor('#9ba5b0')),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e7eef5')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 8), ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),
        ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6)]
    for index in category_indices:
        rules.extend([('SPAN', (0, index), (-1, index)), ('BACKGROUND', (0, index), (-1, index), colors.HexColor('#f3f5f7')),
            ('NOSPLIT', (0, index), (-1, index + 1))])
    table.setStyle(TableStyle(rules))
    story.extend([table, Spacer(1, 24)])
    signatures = []
    for heading, (role, label) in zip(('Prepared by:', 'Reviewed by:', 'Approved by:'), ROLES.items()):
        signatures.append([p(heading), Spacer(1, 24), p(data['signatories'][role]['name']), p(label), p('Signature / date: __________________')])
    story.append(Table([signatures], colWidths=[width / 3] * 3, style=TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP')])))
    story.extend([Spacer(1, 12), p('Unsigned: system issuance is not a physical signature, signed-form receipt, spending authority or Form 1 certification.'),
        PageBreak(), Paragraph('Retained preparation evidence', styles['Heading2']),
        p(f"Proposal: {data['proposal_title']} / v{data['proposal_version']} / {data['proposal']}"),
        p(f"Office form version: {data['form_version']}"), p(f"Source context SHA-256: {data['context_checksum']}"),
        Spacer(1, 10), p('Coverage declaration: ' + data['coverage'])])
    for role, label in ROLES.items():
        story.extend([Spacer(1, 8), p(label + ' designation evidence: ' + data['signatories'][role]['authority'])])
    story.extend([Spacer(1, 12), p('Actuals and forecast evidence is retained with this output. The listed actual certifications remain distinct from these signature blocks.')])
    seen = set()
    for row in schedule['rows']:
        for source in row['sources']:
            for prefix in ('prior', 'half'):
                for evidence in source[prefix + '_rows']:
                    key = (evidence['certificate'], source['center_id'], prefix)
                    if key in seen:
                        continue
                    seen.add(key)
                    story.extend([Spacer(1, 6), p(f"{source['center_code']} / {prefix}: {evidence['reference']} / certificate {evidence['certificate']} / v{evidence['version']}"),
                        p(f"Accountant: {evidence['accountant_name']} / Authority: {evidence['certification_authority']}")])
    def footer(canvas, document):
        canvas.saveState()
        if document.page > 1:
            heading = p(f"Form 2 v{data['form_version']} | {schedule['office_label']} / {schedule['fund_code']} | Budget year {schedule['budget_year']}")
            _, height = heading.wrap(doc.width, 30)
            heading.drawOn(canvas, 28, landscape(A4)[1] - 12 - height)
        canvas.setFont('Helvetica', 7)
        canvas.drawString(28, 18, f"UNSIGNED | Form 2 v{data['form_version']} | {data['context_checksum'][:16]}")
        canvas.drawRightString(landscape(A4)[0] - 28, 18, f'Page {document.page}')
        canvas.restoreState()
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
