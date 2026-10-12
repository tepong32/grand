import json
from django import forms
from django.core.exceptions import ValidationError
from .models import Fund
from .access import department_for_user
from .summary_actuals import RECEIPTS
from .budget_receipt_partitions import EXCLUSIONS, FIELDS, amount
from .budget_actuals_forms import style


class Scope(forms.Form):
    fund=forms.ModelChoiceField(queryset=Fund.objects.none())
    start=forms.DateField(label='Source period from',widget=forms.DateInput(attrs={'type':'date'}))
    end=forms.DateField(label='Source period through',widget=forms.DateInput(attrs={'type':'date'}))
    q=forms.CharField(required=False,max_length=255,label='Find source reference')

    def __init__(self,*args,actor,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['fund'].queryset=Fund.objects.filter(department_id=department_for_user(actor).pk).order_by('code','pk')
        style(self)

    def clean(self):
        data=super().clean()
        if data.get('start') and data.get('end') and data['start']>data['end']:
            raise ValidationError('Source period through must not precede source period from.')
        return data


class Component(forms.Form):
    line_id=forms.ChoiceField(label='Original financial line')
    amount=forms.CharField(label='Positive component amount',max_length=40)
    disposition=forms.ChoiceField(choices=(('unresolved','Unresolved'),('include','Include as receipt'),('exclude','Exclude from receipts')))
    purpose=forms.ChoiceField(choices=(('unresolved','Unresolved'),('receipt','Receipt'),
        *[(key,key.replace('_',' ').title()) for key in sorted(EXCLUSIONS)]))
    category=forms.ChoiceField(required=False,choices=(('','No receipt category'),*RECEIPTS.items()))
    basis=forms.CharField(max_length=1000,widget=forms.Textarea(attrs={'rows':2}),label='Component evidence / basis')

    def __init__(self,*args,lines,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['line_id'].choices=[('','Select source line')]+[(str(row['id']),
            f"Line {row['sequence']}: {row['account']['code']} {row['account']['title']} · debit {row['debit']} / credit {row['credit']}") for row in lines]
        style(self)
        for key,field in self.fields.items(): field.widget.attrs['data-component-field']=key

    def clean_amount(self): return str(amount(self.cleaned_data['amount']))
    def clean_line_id(self): return int(self.cleaned_data['line_id'])


class Proposal(forms.Form):
    expected_source_checksum=forms.CharField(max_length=64,widget=forms.HiddenInput)
    expected_latest=forms.IntegerField(min_value=0,widget=forms.HiddenInput)
    evidence_reference=forms.CharField(max_length=255,label='Classification evidence reference')
    reason=forms.CharField(max_length=4000,widget=forms.Textarea(attrs={'rows':3}),label='Classification explanation')
    confirmed=forms.BooleanField(label='I checked every financial line and component, including exclusions and unresolved amounts.')
    rows=forms.CharField(required=False,max_length=2000000,widget=forms.HiddenInput)

    def __init__(self,*args,lines,inherit=False,**kwargs):
        super().__init__(*args,**kwargs); self.lines=lines; self.inherit=inherit; style(self)

    def clean_rows(self):
        if self.inherit: return []
        try:
            rows=json.loads(self.cleaned_data['rows'])
            if not isinstance(rows,list) or not rows or len(rows)>10000: raise ValueError
            result=[]
            for index,row in enumerate(rows,1):
                if not isinstance(row,dict) or set(row)!=FIELDS: raise ValueError
                component=Component(row,lines=self.lines)
                if not component.is_valid():
                    raise ValidationError(f'Component {index}: '+ '; '.join(
                        f'{key}: {", ".join(errors)}' for key,errors in component.errors.items()))
                result.append(component.cleaned_data)
            return result
        except (ValueError,TypeError):
            raise ValidationError('Submit complete component rows using the guided editor.')


class Pairing(forms.Form):
    def __init__(self,*args,lines,originals,**kwargs):
        super().__init__(*args,**kwargs)
        for line in lines:
            candidates=[row for row in originals if all(row[key]==line[key] for key in
                ('account_id','responsibility_center_id','cash_flow_category')) and
                (row['debit'],row['credit'])==(line['credit'],line['debit'])]
            self.fields['pair_'+str(line['id'])]=forms.ChoiceField(label=f"Original for reversal line {line['sequence']} ({line['account']['code']})",
                choices=[('','Select exact original line')]+[(str(row['id']),f"Line {row['sequence']}: debit {row['debit']} / credit {row['credit']}") for row in candidates])
        style(self)

    def pairs(self): return {key[5:]:int(value) for key,value in self.cleaned_data.items()}


class Review(forms.Form):
    outcome=forms.ChoiceField(choices=(('approve','Record independent classification review'),('return','Return classification batch')))
    note=forms.CharField(max_length=4000,widget=forms.Textarea(attrs={'rows':3}),label='Review evidence or required correction')
    confirmed=forms.BooleanField(required=False,label='I reviewed every member, original line, component, exclusion and predecessor in this complete batch.')

    def __init__(self,*args,**kwargs): super().__init__(*args,**kwargs); style(self)
    def clean(self):
        data=super().clean()
        if data.get('outcome')=='approve' and not data.get('confirmed'):
            self.add_error('confirmed','Review the complete retained batch before approving.')
        return data
