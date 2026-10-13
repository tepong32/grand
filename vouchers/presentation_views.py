from django import forms
import json
from django.contrib import messages
from django.core.exceptions import ValidationError, PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpResponse
from django.views.decorators.http import require_GET
from src.export_archive import archive_export

from .access import voucher_access_required, has_explicit_permission, department_for_user
from .models import PaymentInstrument, PaymentPresentationDecision as Decision
from . import payment_presentations as service


class CaptureForm(forms.Form):
    observed_on = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    reason = forms.CharField(max_length=4000, widget=forms.Textarea(attrs={'rows': 3}))
    evidence_reference = forms.CharField(max_length=4000, widget=forms.Textarea(attrs={'rows': 2}))


class DecisionForm(forms.Form):
    expected_version = forms.IntegerField(widget=forms.HiddenInput)
    outcome = forms.ChoiceField(choices=Decision.OUTCOMES)
    effective_on = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    evidence_reference = forms.CharField(max_length=4000, widget=forms.Textarea(attrs={'rows': 2}))
    reason = forms.CharField(max_length=4000, widget=forms.Textarea(attrs={'rows': 3}))
    next_action = forms.CharField(required=False, max_length=4000, widget=forms.Textarea(attrs={'rows': 2}),
                                 help_text='Required while awaiting evidence or financial reconciliation.')
    source_reference = forms.ChoiceField(required=False, label='Completed Accounting source',
        help_text='Required to close a verified payment or return. Pending financial work cannot close the finding.')

    def __init__(self, *args, report, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import ReturnedInstrumentReview
        from .presentation_resolution import payment_sources
        choices = [('', 'Select when linking a completed disposition')]
        instrument = report.instrument
        for source in payment_sources(instrument).filter(status__in=('posted', 'not_required')):
            choices.append((str(source.public_id), f'Payment: {source.jev_number or "reviewed no-entry decision"}'))
        for source in instrument.returned_accounting_reviews.filter(status__in=(ReturnedInstrumentReview.READY_FOR_TREASURY, ReturnedInstrumentReview.CLOSED)):
            choices.append((str(source.public_id), f'Returned item: review v{source.version} · {source.get_outcome_display()}'))
        self.fields['source_reference'].choices = choices


@voucher_access_required
def create(request, instrument_id):
    if not service.can_act(request.user, 'record_payment_presentations'):
        raise PermissionDenied
    from .views import _case
    instrument = get_object_or_404(PaymentInstrument, public_id=instrument_id)
    _case(instrument.case.public_id, request.user)
    form = CaptureForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            report = service.capture(instrument=instrument, actor=request.user, **form.cleaned_data)
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            return redirect('vouchers:presentation_detail', public_id=report.public_id)
    return render(request, 'vouchers/advice/form.html', {'form': form,
        'title': f'Record presentation report — cheque {instrument.check_number}', 'button_label': 'Record report',
        'guidance': 'Record what was reported and where its evidence is held. Accounting records the bank finding independently.'})


@voucher_access_required
def detail(request, public_id):
    report = get_object_or_404(service.visible_reports(request.user), public_id=public_id)
    service.verify(report)
    allowed = (service.can_act(request.user, 'review_payment_presentations') and report.is_open
        and department_for_user(request.user).pk == report.accounting_department_id
        and request.user.pk != report.reported_by_id)
    form = DecisionForm(request.POST or None, report=report, initial={'expected_version': report.state_version})
    if request.method == 'POST':
        if not allowed:
            raise PermissionDenied
        if form.is_valid():
            try:
                service.decide(report=report, actor=request.user, **form.cleaned_data)
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                messages.success(request, 'Independent bank finding retained.')
                return redirect('vouchers:presentation_detail', public_id=report.public_id)
    return render(request, 'vouchers/advice/presentation.html', {'report': report, 'form': form, 'can_review': allowed,
        'can_export': has_explicit_permission(request.user, 'vouchers.export_bank_advice')})


@voucher_access_required
@require_GET
def export(request, public_id):
    if not has_explicit_permission(request.user, 'vouchers.export_bank_advice'):
        raise PermissionDenied
    report = get_object_or_404(service.visible_reports(request.user), public_id=public_id)
    data = service.export_evidence(report)
    content = json.dumps(data, indent=2, sort_keys=True).encode('utf-8')
    filename = f'presentation-{report.public_id}-v{data["version"]}.json'
    archive_export(content=content, department=department_for_user(request.user), user=request.user,
        category='finance-payment-presentations', filename=filename, metadata={'report':str(report.public_id)})
    response = HttpResponse(content, content_type='application/json')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
