from uuid import UUID
from django import forms
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.http import Http404
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods
from accounting import summary_actuals
from accounting.models import BudgetSummaryActual
from .access import budget_access_required, department_for_user
from .models import BudgetOfficeForm
from .office_form_views import owned_version
from .office_forms import verify
from .summary_comparison import compare, compare_cohort


class CohortForm(forms.Form):
    office_forms = forms.ModelMultipleChoiceField(queryset=BudgetOfficeForm.objects.none(), label='Exact issued office versions')
    expected_offices = forms.MultipleChoiceField(label='Complete expected offices for this reporting entity')
    entity_key = forms.CharField(widget=forms.HiddenInput)
    coverage_reference = forms.CharField(label='Office/entity coverage designation reference', max_length=2000,
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}))
    complete = forms.BooleanField(label='I checked the complete expected office inventory and reporting entity designation.')

    def __init__(self, *args, item, entity_key, **kwargs):
        super().__init__(*args, **kwargs)
        from departments.models import Department
        self.fields['office_forms'].queryset = BudgetOfficeForm.objects.filter(proposal_id=item.proposal_id,
            department_id=item.department_id, fund_id=item.fund_id, status=BudgetOfficeForm.ISSUED)
        self.fields['office_forms'].label_from_instance = lambda obj: (
            f"{obj.payload['schedule']['office_label']} / {obj.payload['schedule']['fund_code']} · version {obj.version} · "
            f"{timezone.localtime(obj.decided_at).strftime('%Y-%m-%d %H:%M')}")
        self.fields['expected_offices'].choices = [(str(obj.pk), obj.name) for obj in Department.objects.order_by('name')]
        self.initial['entity_key'] = entity_key
        for field in self.fields.values():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs.update({'class':'form-control','style':'max-width:100%'})


@require_http_methods(['GET', 'POST'])
@budget_access_required
def diagnostic(request, public_id):
    item = get_object_or_404(BudgetOfficeForm.objects.select_related('proposal'),
        public_id=public_id, department_id=department_for_user(request.user).pk, status=BudgetOfficeForm.ISSUED)
    owned_version(request, item.proposal.public_id)
    sources = summary_actuals.visible(request.user).filter(status=BudgetSummaryActual.APPROVED,
        scope__budget_department_id=item.department_id, scope__fund_id=item.fund_id)
    errors, result, chosen, cohort_form, cohort = [], None, None, None, None
    try:
        data = verify(item)
        if request.GET.get('summary'):
            try:
                identity = UUID(request.GET['summary'])
            except ValueError:
                raise Http404('Unknown joint source.')
            chosen = get_object_or_404(sources, public_id=identity)
            actual = summary_actuals.verify(chosen)
            result = compare(actual, data['schedule'])
            cohort_form = CohortForm(request.POST if request.method == 'POST' else None,
                item=item, entity_key=actual['scope']['entity_key'])
            if request.method == 'POST' and cohort_form.is_valid():
                values = cohort_form.cleaned_data
                cohort = compare_cohort(actual, [verify(member) for member in values['office_forms']],
                    expected_offices=[int(value) for value in values['expected_offices']],
                    entity_key=values['entity_key'], coverage_reference=values['coverage_reference'])
    except ValidationError as exc:
        errors = exc.messages
    return render(request, 'budget/summary_comparison.html', {'item': item, 'chosen': chosen,
        'sources': Paginator(sources, 50).get_page(request.GET.get('page')), 'result': result, 'errors': errors,
        'cohort_form': cohort_form, 'cohort': cohort})
