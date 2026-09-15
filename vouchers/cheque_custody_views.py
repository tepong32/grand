from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST
from tracepoint.access import packet_is_visible
from tracepoint.models import PacketItem
from .collections import require
from .collection_views import visible_sources
from .models import TreasuryCollectionSource as Source, CollectionChequeCustodyLink as Link
from . import cheque_custody


class CustodyForm(forms.Form):
    item = forms.ModelChoiceField(queryset=PacketItem.objects.none(),label='Actual TracePoint cheque item')
    evidence_reference = forms.CharField(max_length=4000,widget=forms.Textarea,
        label='Evidence identifying this cheque as the tracked item')

    def __init__(self,*args,actor,**kwargs):
        super().__init__(*args,**kwargs)
        items = PacketItem.objects.filter(Q(current_packet__prepared_by=actor,current_packet__status='draft')
            |Q(current_packet__current_holder=actor,current_packet__status__in=('active','on_hold'))
        ).filter(voucher_case__isnull=True).exclude(pk__in=Link.objects.filter(withdrawn_at__isnull=True).values('item_id')
        ).select_related('current_packet')
        ids = [item.pk for item in items if packet_is_visible(actor,item.current_packet)]
        self.fields['item'].queryset = items.filter(pk__in=ids)
        self.fields['item'].label_from_instance = lambda item: f'{item.reference_number} · {item.current_packet.tracking_number}'
        for field in self.fields.values(): field.widget.attrs['class'] = 'form-control'


@login_required
@require_http_methods(['GET','POST'])
def create(request,public_id):
    source = get_object_or_404(visible_sources(request.user),public_id=public_id,kind=Source.CHEQUE_RETURN)
    if require(request.user,'vouchers.link_collection_custody').pk != source.treasury_department_id:
        raise PermissionDenied
    form = CustodyForm(request.POST or None,actor=request.user)
    if request.method == 'POST' and form.is_valid():
        try:
            cheque_custody.link(source=source,actor=request.user,**form.cleaned_data)
        except ValidationError as exc:
            form.add_error(None,exc)
        else:
            return redirect('vouchers:collection_detail',public_id=source.public_id)
    return render(request,'vouchers/collections/form.html',{'form':form,'title':'Link returned-cheque custody','custody_form':True})


@login_required
@require_POST
def withdraw(request,public_id,link_id):
    source = get_object_or_404(visible_sources(request.user),public_id=public_id)
    link = get_object_or_404(source.custody_links,pk=link_id)
    form = forms.Form(request.POST)
    form.fields['reason'] = forms.CharField(max_length=4000,widget=forms.Textarea)
    if form.is_valid():
        try:
            cheque_custody.withdraw(link=link,actor=request.user,reason=form.cleaned_data['reason'])
        except ValidationError as exc:
            form.add_error(None,exc)
        else:
            return redirect('vouchers:collection_detail',public_id=source.public_id)
    return render(request,'vouchers/collections/form.html',{'form':form,'title':'Withdraw custody association'},status=400)
