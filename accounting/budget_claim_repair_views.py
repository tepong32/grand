"""Read-only navigation from Budget coverage gaps to existing claim review."""
from django import forms
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from .access import accounting_access_required, department_for_user
from .models import JournalEntry, JournalLine


class Search(forms.Form):
    q = forms.CharField(required=False, max_length=255, label='Original journal or claim reference')


@require_GET
@accounting_access_required
def sources(request, line_id):
    owner_id = department_for_user(request.user).pk
    line = get_object_or_404(JournalLine.objects.select_related('entry__fund', 'account'),
        pk=line_id, entry__department_id=owner_id, entry__status=JournalEntry.POSTED,
        account__account_type='liability')
    query = JournalLine.objects.filter(entry__department_id=owner_id,
        entry__fund_id=line.entry.fund_id, entry__status=JournalEntry.POSTED,
        entry__posted_by_id__isnull=False, entry__reversal_of__isnull=True,
        entry__entry_date__lte=line.entry.entry_date, account_id=line.account_id,
        credit__gt=0, debit=0, payable_origin__isnull=True, payable_allocation={}
    ).exclude(entry__source_type__in=('voucher', 'remittance')).exclude(entry__posted_by_id=0)
    original = query.filter(pk=line.pk).exists()
    blocked_reason = 'This line already has linked or generated-workflow evidence. Resolve it through its original financial workflow; this finder cannot reassign it as historical activity.'
    try:
        blocked = bool(line.payable_origin_id or line.payable_allocation or line.payable_reservation_id
                       or line.entry.statement_origin.source_type in ('voucher', 'remittance'))
    except ValidationError:
        blocked = True
        blocked_reason = 'Reconcile the retained reversal lineage before selecting historical claim evidence.'
    if not original and (line.payable_party_key or line.payable_claim_reference):
        blocked = True
    form = Search(request.GET)
    if blocked:
        query = query.none()
    elif original:
        query = query.filter(pk=line.pk)
    elif form.is_valid():
        if form.cleaned_data['q']:
            query = query.filter(Q(entry__reference__icontains=form.cleaned_data['q'])
                                 | Q(payable_claim_reference__icontains=form.cleaned_data['q']))
    else:
        query = query.none()
    page = Paginator(query.select_related('entry', 'account').order_by('entry__entry_date', 'pk'), 50).get_page(request.GET.get('page'))
    params = request.GET.copy(); params.pop('page', None)
    return render(request, 'accounting/budget_claim_repair.html',
        {'line': line, 'original': original, 'blocked': blocked, 'blocked_reason': blocked_reason, 'form': form,
         'page': page, 'querystring': params.urlencode()})
