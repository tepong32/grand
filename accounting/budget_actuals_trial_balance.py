"""Posted-account Fund trial balance from the same retained actuals observation."""
from copy import deepcopy
from decimal import Decimal
from django.core.exceptions import ValidationError
from . import budget_native_actuals as actuals
from .budget_actuals import money
from .budget_attributions import json_value
from .cash_classifications import checksum


def project(captured):
    try:
        body=actuals.verify(captured); scope=body['scope']
        ledger=body['receipts']['payload']['inventory']['payload']['ledger']
        data=ledger['payload']; groups={}; journals=set(); lines=set()
        for entry in data['journals']:
            if entry['id'] in journals or entry['department_id'] != scope['fund']['department_id']:
                raise ValidationError('Retain every posted trial-balance journal once in this exact Fund owner.')
            journals.add(entry['id']); debit=credit=Decimal('0.00')
            if entry['entry_date'] > scope['period_end']:
                raise ValidationError('Do not add later dependency activity to trial-balance amounts.')
            for line in entry['lines']:
                account=line['account']; d,c=money(line['debit']),money(line['credit'])
                if (line['id'] in lines or account['id'] != line['account_id']
                    or account['department_id'] != scope['fund']['department_id']
                    or (d>0)==(c>0) or min(d,c)<0):
                    raise ValidationError('Retain exact one-sided trial-balance lines and account ownership.')
                lines.add(line['id']); debit+=d; credit+=c
                row=groups.setdefault(account['id'],dict(account=deepcopy(account),opening=Decimal('0.00'),
                    debit=Decimal('0.00'),credit=Decimal('0.00'),sources=[]))
                if row['account'] != account:
                    raise ValidationError('Reconcile inconsistent captured trial-balance account metadata.')
                if entry['entry_date'] < scope['period_start']: row['opening']+=d-c
                else: row['debit']+=d; row['credit']+=c
                row['sources'].append(dict(entry_id=entry['id'],line_id=line['id'],date=entry['entry_date'],debit=str(d),credit=str(c)))
            events=entry['posting_evidence']
            if (not entry['lines'] or debit!=credit or len(events)!=1 or not entry['posted_by_id']
                or events[0]['actor_id']!=entry['posted_by_id']
                or money(events[0]['snapshot']['debit'])!=debit or money(events[0]['snapshot']['credit'])!=credit):
                raise ValidationError('Trial-balance history requires balanced independent posting evidence.')
        rows=[]
        for key in sorted(groups):
            row=groups[key]; closing=row['opening']+row['debit']-row['credit']
            rows.append(dict(row,closing=closing,closing_debit=max(closing,Decimal('0.00')),
                closing_credit=max(-closing,Decimal('0.00'))))
        totals={key:sum((row[key] for row in rows),Decimal('0.00'))
            for key in ('opening','debit','credit','closing','closing_debit','closing_credit')}
        if totals['opening'] or totals['closing'] or totals['debit']!=totals['credit'] or totals['closing_debit']!=totals['closing_credit']:
            raise ValidationError('Retained Fund trial-balance columns do not balance.')
        all_debit=sum((money(row['debit']) for group in groups.values() for row in group['sources']),Decimal('0.00'))
        all_credit=sum((money(row['credit']) for group in groups.values() for row in group['sources']),Decimal('0.00'))
        if (len(journals)!=data['controls']['journals'] or len(lines)!=data['controls']['lines']
            or all_debit!=money(data['controls']['debit']) or all_credit!=money(data['controls']['credit'])):
            raise ValidationError('Retain the complete captured history behind the trial-balance controls.')
        payload=json_value(dict(schema=1,kind='native_budget_actuals_fund_trial_balance',scope=deepcopy(scope),
            source_checksum=ledger['checksum'],rows=rows,totals=totals,journals=len(journals),lines=len(lines),
            basis='All posted Fund history through period end; later dependencies excluded; budget flows require explicit reviewed partitions'))
        return {'payload':payload,'checksum':checksum(payload)}
    except (KeyError,TypeError,ValueError,ArithmeticError) as error:
        raise ValidationError('Invalid retained actuals trial-balance evidence.') from error
