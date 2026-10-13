"""Human-readable allocation choices over an authenticated preparation context."""
from decimal import Decimal

from django import forms
from django.forms import formset_factory

from . import budget_attributions as service
from .budget_claim_components import BASES


def choices(values):
    return [(value, value.replace('_', ' ').capitalize()) for value in sorted(values)]


class Basis(forms.Form):
    reason = forms.CharField(label='Preparation explanation', widget=forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}))
    evidence_reference = forms.CharField(max_length=255, label='Supporting evidence reference',
                                         widget=forms.TextInput(attrs={'class': 'form-control'}))


class Treatment(forms.Form):
    mode = forms.ChoiceField(label='How to prepare this journal', choices=[('manual', 'Enter explicit allocations')],
                            widget=forms.Select(attrs={'class': 'form-control'}))

    def __init__(self, *args, entry, context, **kwargs):
        super().__init__(*args, **kwargs)
        parent_id = entry['reversal_of_id']
        parent = next((row for row in context['entries'] if row['id'] == parent_id), None)
        if parent:
            self.fields['mode'].choices += [('parent', f"Inherit the {parent['reference']} proposal in this batch")]
        elif entry.get('reviewed_reversal') or entry.get('reviewed_predecessor'):
            self.fields['mode'].choices += [('reviewed', 'Mirror the independently reviewed predecessor')]


class Pairing(forms.Form):
    def __init__(self, *args, entry, **kwargs):
        super().__init__(*args, **kwargs)
        for pair in entry.get('pairing_choices', []):
            matches = pair['choices']
            self.fields[str(pair['line_id'])] = forms.TypedChoiceField(coerce=int,
                label=f"Original for reversal line {pair['sequence']}",
                choices=[('', 'Choose the original financial line'), *matches],
                initial=matches[0][0] if len(matches) == 1 else None,
                widget=forms.Select(attrs={'class': 'form-control'}))

    def clean(self):
        values = super().clean()
        if len(values.values()) != len(set(values.values())):
            raise forms.ValidationError('Each original line must be paired exactly once.')
        return values


class Allocation(forms.Form):
    line_id = forms.TypedChoiceField(coerce=int, label='Financial line')
    amount = forms.DecimalField(min_value=Decimal('0.01'), max_digits=18, decimal_places=2)
    disposition = forms.ChoiceField(choices=choices({'include', 'exclude', 'unresolved'}))
    purpose = forms.ChoiceField(choices=choices({*service.INCLUDED_PURPOSES, *service.EXCLUDED_PURPOSES, 'unresolved'}))
    center_id = forms.TypedChoiceField(coerce=int, empty_value=None, required=False, label='Office')
    expense_class = forms.CharField(max_length=40, required=False, label='Expenditure object class')
    basis = forms.CharField(max_length=1000, label='Evidence basis', widget=forms.Textarea(attrs={'rows': 2}))
    claim_component_basis = forms.ChoiceField(required=False, label='Original liability component basis',
                                             choices=[('', 'Not an original component'), *choices(BASES)])
    component = forms.ChoiceField(required=False, label='Reviewed original component')

    def __init__(self, *args, entry, context, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['line_id'].choices = [(line['id'],
            f"{line['sequence']} · {line['account']['code']} · {line['account']['title']} · debit {line['debit']} / credit {line['credit']}")
            for line in entry['lines']]
        self.fields['center_id'].choices = [('', 'No expenditure office'), *[
            (key, f"{row['code']} · {row['name']}") for key, row in context['centers'].items() if row['office_id']]]
        self.references = {}
        self.fields['component'].choices = [('', 'Not an application / unresolved')]
        for line in entry['lines']:
            for item in context['components'].get(str(line['id']), []):
                key = f"{line['id']}:{item['component_key']}"
                self.references[key] = item
                self.fields['component'].choices.append((key,
                    f"Line {line['sequence']} · {item['source_reference']} · {item['basis'].replace('_', ' ')} · source {item['source_amount']} · application share {item['application_share']}"))
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')

    def allocation(self):
        data = dict(self.cleaned_data)
        data.pop('DELETE', None)
        reference = data.pop('component', '')
        if reference:
            data['claim_component'] = {key: self.references[reference][key]
                for key in ('source_line_id', 'attribution_id', 'component_key')}
        if not data.get('claim_component_basis'):
            data.pop('claim_component_basis', None)
        return data


Rows = formset_factory(Allocation, extra=0, can_delete=True, max_num=1000, validate_max=True, absolute_max=1000)


def journal_forms(context, data=None):
    result = []
    for entry in context['entries']:
        prefix = f"journal-{entry['id']}"
        initial = [dict(line_id=line['id'], amount=str(Decimal(line['debit']) + Decimal(line['credit'])),
                        disposition='unresolved', purpose='unresolved') for line in entry['lines']]
        result.append({'entry': entry,
            'treatment': Treatment(data, prefix=prefix, entry=entry, context=context),
            'pairing': Pairing(data, prefix=prefix + '-pair', entry=entry) if entry.get('pairing_choices') else None,
            'rows': Rows(data, prefix=prefix + '-rows', initial=initial,
                         form_kwargs={'entry': entry, 'context': context})})
    return result


def proposals(groups):
    result, valid = [], True
    for group in groups:
        if not group['treatment'].is_valid():
            valid = False
            continue
        entry = group['entry']
        pairs = None
        if group['treatment'].cleaned_data['mode'] != 'manual' and group['pairing'] is not None:
            if not group['pairing'].is_valid():
                valid = False
                continue
            pairs = {int(key): value for key, value in group['pairing'].cleaned_data.items()}
        if group['treatment'].cleaned_data['mode'] == 'parent':
            result.append(dict(entry_id=entry['id'], inherit_from=entry['reversal_of_id']))
        elif group['treatment'].cleaned_data['mode'] == 'reviewed':
            result.append(dict(entry_id=entry['id'], use_reviewed_reversal=True))
        elif group['rows'].is_valid():
            result.append(dict(entry_id=entry['id'], allocations=[form.allocation()
                for form in group['rows'] if form.cleaned_data and not form.cleaned_data.get('DELETE')]))
        else:
            valid = False
        if pairs is not None:
            result[-1]['line_pairs'] = pairs
    return result if valid else None
