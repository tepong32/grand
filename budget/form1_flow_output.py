"""Complete source-linked flow drafts; never a signed or issued Form 1."""
from copy import deepcopy
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from django.core.exceptions import ValidationError
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak,KeepTogether
from accounting.budget_actuals import money
from accounting.cash_classifications import checksum
from . import form1_itemization as itemization,form1_flows


def package(snapshot):
    try:
        payload=snapshot['payload']; decision=snapshot['decision']
        status=decision['status']; reviewed=status=='approved'
        if (checksum(payload)!=snapshot['payload_checksum']
            or decision['payload_checksum']!=snapshot['payload_checksum']
            or status not in ('prepared','approved','returned')
            or snapshot['independently_reviewed'] is not reviewed
            or snapshot['code_authority_approved'] is not reviewed or snapshot['form_issued'] is not False
            or (status!='prepared' and checksum(decision)!=snapshot['decision_checksum'])
            or (status=='prepared' and snapshot['decision_checksum'])):
            raise ValidationError('Retain the original account-review decision and evidence.')
        projection=itemization.compose(payload['draft'])
        result=dict(schema=1,kind='form1_flow_output_draft',account_review=deepcopy(snapshot),
            itemization=projection,form_issued=False,source_freshness_certified=False)
        return dict(payload=result,checksum=checksum(result))
    except (KeyError,TypeError,ValueError) as error:
        raise ValidationError('Retain complete reviewed-source draft evidence.') from error


def render_pdf(envelope, *, spa_draft=None, number_pages=True):
    try:
        data=envelope['payload']
        if checksum(data)!=envelope['checksum'] or package(data['account_review'])!=envelope:
            raise ValidationError('The printable draft must reproduce its original whole source package.')
        body=itemization.verify(data['itemization']); snapshot=data['account_review']; identity=snapshot['payload']['identity']
        spa_data=None
        if spa_draft is not None:
            from . import form1_spa_output
            spa_data=form1_spa_output.verify(spa_draft)
            if spa_data['flow']!=envelope:
                raise ValidationError('The printable flow and SPA draft must retain the exact same source pair.')
        font='GRANDForm1FlowNotoSans'
        if font not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(font,str(Path(__file__).parent/'assets/NotoSans-Regular.ttf')))
        glyphs=pdfmetrics.getFont(font).face.charWidths
        style=ParagraphStyle('FlowCell',fontName=font,fontSize=8,leading=11,splitLongWords=True)
        def p(value):
            value=str(value)
            missing={ord(char) for char in value if not char.isspace() and ord(char) not in glyphs}
            if missing:raise ValidationError('The print font cannot render source characters; retain the JSON and add reviewed font coverage.')
            return Paragraph(escape(value).replace('\n','<br/>'),style)
        stream=BytesIO(); doc=SimpleDocTemplate(stream,pagesize=landscape(A4),leftMargin=28,rightMargin=28,
            topMargin=38,bottomMargin=32,title='Form 1 itemized flows - incomplete draft',invariant=1)
        widths=[doc.width*.25,doc.width*.12,*[doc.width*.126]*5]
        def amount(value):
            text='Unknown' if value is None else f'{money(value):,.2f}'
            size=8 if pdfmetrics.stringWidth(text,font,8)<=widths[2]-12 else 6
            if pdfmetrics.stringWidth(text,font,size)>widths[2]-12:
                raise ValidationError('A complete amount exceeds the reviewed print width; retain JSON and review the layout.')
            return Paragraph(escape(text),ParagraphStyle('FlowAmount',parent=style,fontSize=size,alignment=2))
        def financial_row(label,code,values):
            return [p(label),p(code),*[amount(values[column]) for column in form1_flows.COLUMNS]]
        def table(cells,scope):
            result=Table([[p(scope),*['']*6],*cells],colWidths=widths,repeatRows=2,hAlign='LEFT')
            result.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.35,colors.HexColor('#a4afba')),
                ('SPAN',(0,0),(-1,0)),('BACKGROUND',(0,0),(-1,1),colors.HexColor('#e7eef5')),
                ('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
            return result
        warning='INCOMPLETE DRAFT - not issued, certified or ready for signing. Beginning/ending cash, PhilHealth deduction, SPA subdivisions, shared-source allocation and final signatory/Chief Executive evidence remain separate requirements.'
        if spa_data is not None:
            warning='INCOMPLETE DRAFT - not issued, certified or ready for signing. SPA decisions describe retained source treatment, not statutory percentage compliance or spending authority. Beginning/ending cash, PhilHealth deduction, shared-source allocation and final signatory/Chief Executive evidence remain separate requirements.'
        story=[]
        for index,member in enumerate(body['members']):
            if index:story.append(PageBreak())
            year=member['scope']['budget_year']
            scope=f"{member['entity_label']} / {member['scope']['fund_code']} / Budget year {year} / INCOMPLETE DRAFT"
            heading=[p(value) for value in ('Particulars','Government account code',f'{year-2} Past year actual',
                f'{year-1} H1 actual',f'{year-1} H2 estimate',f'{year-1} Current total',f'{year} Proposed')]
            story.extend([p('FORM 1 ITEMIZED FLOWS - INCOMPLETE DRAFT'),Spacer(1,8),
                p(f"{member['entity_label']} | {member['scope']['fund_code']} | Budget year {year}"),
                p(f"Original account package {identity['public_id']} / version {identity['version']} / decision {snapshot['decision']['status']}"),
                p('Original selections are retained. Source freshness is not certified by this historical draft.'),p(warning),Spacer(1,10)])
            for kind,title in (('receipt','RECEIPTS'),('expenditure','EXPENDITURES')):
                story.extend([p(title),Spacer(1,5)]);cells=[heading]
                for leaf in member[kind]['rows']:
                    cells.append(financial_row(leaf['label']+' - category control','',leaf['amounts']))
                    for row in leaf['accounts']:
                        account=row['account']
                        label=account['title'] if account else ('Original explicit zero without account' if row['disposition']=='mapped' else 'Unresolved reporting selection')
                        if account:label+=f" (local {account['code']}; original ID {account['id']})"
                        cells.append(financial_row(label,account['government_account_code'] if account else '',row['amounts']))
                cells.append(financial_row('Total '+title.title(),' ',member[kind]['totals']))
                story.extend([table(cells,scope),Spacer(1,12),p('Category controls and their itemized rows describe the same money; do not add them together.')])
            if spa_data is not None:
                story.extend(form1_spa_output.print_member(spa_data,member['entity_key'],p,financial_row,table,heading,scope))
            story.extend([Spacer(1,12),KeepTogether([p('RECEIPT HIERARCHY CONTROLS - each subtotal uses unique original leaves'),Spacer(1,5),
                table([heading,*[financial_row(row['label'].replace(' — ',' - '),'',row['amounts']) for row in member['receipt']['hierarchy']]],scope)]),
                PageBreak(),p('ORIGINAL SOURCE SHARES - COMPLETE EVIDENCE INDEX'),
                p(f"{member['entity_label']} | Account package checksum {snapshot['payload_checksum']}"),
                p('Original authority attachment: '+snapshot['payload']['evidence']['name']),
                p('Code authority: '+snapshot['payload']['code_reference']),
                p('Coverage basis: '+snapshot['payload']['draft']['payload']['coverage_reference']),
                p('Download the complete draft JSON and original authority attachment for all original source bodies and decision evidence.')])
            sources={row['key']:row for row in body['source_draft']['payload']['inventory']['payload']['components']}
            for kind in ('receipt','expenditure'):
                for leaf in member[kind]['rows']:
                    for row in leaf['accounts']:
                        for share in row['source_shares']:
                            allocation=share['allocation']; source=sources[share['source_component']]; ref=source['identity']['source']; original=source['source_account']
                            story.append(KeepTogether([Spacer(1,8),p(f"{member['entity_label']} / {kind} / {leaf['label']} / {source['identity']['column']} / signed share {allocation['amount']}"),
                                p('Allocation '+allocation['key']+' | Original component '+source['key']),
                                p('Original source: '+'; '.join(f'{key}={value}' for key,value in ref.items())),
                                p('Original account: '+(original['code']+' / '+original['title'] if original else 'Original explicit zero without account')),
                                p('Reporting selection: '+(allocation['account']['government_account_code']+' / '+allocation['account']['title'] if allocation['account'] else allocation['disposition']+' without account')),
                                p('Selection basis: '+allocation['basis'])]))
        def footer(canvas,document):
            canvas.saveState();canvas.setFont('Helvetica',7)
            if spa_data is None:
                canvas.drawString(28,18,f"INCOMPLETE DRAFT | package v{identity['version']} | {envelope['checksum'][:16]}")
            else:
                spa_identity=spa_data['spa_review']['payload']['identity']
                canvas.drawString(28,18,f"INCOMPLETE DRAFT | SPA v{spa_identity['version']} {spa_data['spa_review']['status']} | {spa_draft['checksum'][:16]}")
            if number_pages:
                canvas.drawRightString(landscape(A4)[0]-28,18,f'Page {document.page}')
            canvas.restoreState()
        doc.build(story,onFirstPage=footer,onLaterPages=footer)
        return stream.getvalue()
    except (KeyError,TypeError,ValueError) as error:
        raise ValidationError('Invalid complete printable flow draft.') from error
