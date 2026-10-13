"""Retained approved source origins, separate from the new proposal's choice."""
from copy import deepcopy

from django.core.exceptions import ValidationError

from accounting.cash_classifications import checksum
from .models import BudgetAuditEvent


def capture_origins(sources):
    """Sources are approved and locked by consolidation; never reread live actuals."""
    origins = {}
    for source in sources:
        context = source.planning_context_snapshot
        if context:
            submitted = BudgetAuditEvent.objects.filter(target_id=str(source.public_id),
                action='submit').order_by('-pk').first()
            if not submitted or submitted.snapshot.get('planning_context') != context:
                raise ValidationError('A consolidation source no longer reproduces its submitted planning evidence.')
        scopes = {}
        for key, choice in source.actuals_source_selection.items():
            scopes[key] = {'fund_id': choice['fund_id'], 'center_id': choice['center_id'],
                'prefix': choice['prefix'], 'explicit_choice': deepcopy(choice), 'evidence': []}
        for row in (context or {}).get('rows', []):
            for prefix in ('prior', 'half'):
                evidence = row.get(prefix + '_certified_evidence') or row.get(prefix + '_certified')
                if not evidence:
                    continue
                scope = evidence['scope']
                key = f"{scope['fund_id']}:{scope['center_id']}:{prefix}"
                item = scopes.setdefault(key, {'fund_id': scope['fund_id'], 'center_id': scope['center_id'],
                    'prefix': prefix, 'explicit_choice': None, 'evidence': []})
                item['evidence'].append(deepcopy(evidence))
        for key, item in scopes.items():
            group = origins.setdefault(key, {name: item[name] for name in ('fund_id', 'center_id', 'prefix')})
            group.setdefault('sources', []).append({'proposal': str(source.public_id),
                'title': source.title, 'version': source.version, 'context_checksum': checksum(context),
                'explicit_choice': item['explicit_choice'], 'evidence': item['evidence']})
    return origins


def unresolved_origins(version):
    """Historical complete-scope choices remain material without proposed amounts."""
    event = BudgetAuditEvent.objects.filter(target_id=str(version.public_id), action='consolidated').order_by('pk').first()
    if event and 'actuals_source_origins' in event.snapshot:
        if event.snapshot['actuals_source_origins'] != version.actuals_source_origins:
            raise ValidationError('Consolidated source origins differ from the retained creation evidence.')
    elif version.actuals_source_origins:
        raise ValidationError('Consolidated source origins lack their retained creation evidence.')
    scopes = set(version.lines.values_list('fund_id', 'responsibility_center_id'))
    return [key for key, value in version.actuals_source_origins.items()
            if ((value['fund_id'], value['center_id']) in scopes or any(
                (source.get('explicit_choice') or {}).get('coverage_mode') == 'complete_scope'
                for source in value.get('sources', []))) and key not in version.actuals_source_selection]


def require_source_choices(version):
    if unresolved_origins(version):
        raise ValidationError('Inspect the retained consolidation sources and explicitly select certified actuals for each affected office and period before submission.')
