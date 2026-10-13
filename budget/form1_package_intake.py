"""Guided first-package intake over the existing source and retention services."""
from datetime import date

from django import forms
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Max
from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpResponse
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from accounting import budget_cash, budget_cash_preparations
from .access import department_for_user, has_budget_permission
from .models import Form1SPAReview, Form1Package
from . import form1_spa_reviews as spa, form1_flows as flows
from . import form1_stock_sources as sources, form1_stocks as stocks
from . import form1_cash_forecasts as forecasts, form1_philhealth as philhealth
from . import form1_assembly as assembly, form1_packages as packages
from .form1_account_views import COLUMNS, components

SALT = 'form1-whole-preparation-preview-v1'
COVERAGE = (('', 'Choose coverage'), ('missing', 'Missing evidence'), ('complete', 'Complete with evidence'))
BOOLEAN = (('', 'Choose explicitly'), ('false', 'No'), ('true', 'Yes, supported by the declaration below'))


def paragraph(label, *, required=True):
    return forms.CharField(label=label, required=required, max_length=2000,
        widget=forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}))


class Boundary(forms.Form):
    boundary_basis = paragraph('Annual / semester opening boundary reconciliation')


class Opening(forms.Form):
    kind = forms.ChoiceField(label='Opening source treatment', choices=(('', 'Choose a source treatment'),
        ('missing', 'Missing evidence — retain unknown'), ('actual', 'Exact adopted / certified actual'),
        ('forecast', 'Evidenced forecast from an actual cash anchor')))
    source = forms.ChoiceField(label='Original actual cash source / forecast anchor', required=False)
    missing_basis = paragraph('Reason opening evidence is missing', required=False)
    worksheet = forms.FileField(label='Original cash timing / restriction worksheet (PDF, PNG or JPEG, up to 8 MiB)', required=False)
    cash_changes = forms.JSONField(required=False, initial=list, widget=forms.HiddenInput)
    proposed_restrictions = forms.JSONField(required=False, initial=list, widget=forms.HiddenInput)
    restriction_changes = forms.JSONField(required=False, initial=list, widget=forms.HiddenInput)
    cash_coverage = forms.ChoiceField(label='Whole cash movement coverage', choices=COVERAGE, required=False)
    cash_basis = paragraph('Cash timing and coverage basis', required=False)
    no_cash_changes = forms.TypedChoiceField(label='Evidenced no cash changes?', choices=BOOLEAN,
        coerce=lambda value: value == 'true', required=False, empty_value=None)
    cash_declaration = paragraph('Explicit no cash change declaration', required=False)
    restriction_coverage = forms.ChoiceField(label='Whole target restriction coverage', choices=COVERAGE, required=False)
    restriction_basis = paragraph('Restriction coverage and overlap basis', required=False)
    no_restrictions = forms.TypedChoiceField(label='Evidenced no target restrictions?', choices=BOOLEAN,
        coerce=lambda value: value == 'true', required=False, empty_value=None)
    restriction_declaration = paragraph('Explicit no target restriction declaration', required=False)

    def __init__(self, *args, choices, column, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['source'].choices = [('', 'Choose the original source'), *choices]
        permitted = {'missing', 'forecast'} if column == 'proposed' else {'missing', 'actual'} if column in (
            'prior_amount', 'half_amount') else {'missing', 'actual', 'forecast'}
        self.fields['kind'].choices = [row for row in self.fields['kind'].choices if not row[0] or row[0] in permitted]
        for field in self.fields.values():
            if not isinstance(field.widget, forms.HiddenInput):
                field.widget.attrs.setdefault('class', 'form-control')

    def clean(self):
        data = super().clean(); kind = data.get('kind')
        required = ('missing_basis',) if kind == 'missing' else ('source',) if kind == 'actual' else (
            'source', 'worksheet', 'cash_coverage', 'cash_basis', 'restriction_coverage', 'restriction_basis') if kind == 'forecast' else ()
        for name in required:
            if not data.get(name): self.add_error(name, 'Supply explicit original evidence for this treatment.')
        if kind == 'forecast':
            for name in ('no_cash_changes', 'no_restrictions'):
                if data.get(name) is None: self.add_error(name, 'Choose explicitly; missing is not zero.')
        return data


class Treatment(forms.Form):
    preview = forms.CharField(required=False, widget=forms.HiddenInput)
    parts = forms.JSONField(required=False, widget=forms.HiddenInput)
    coverage = forms.JSONField(required=False, widget=forms.HiddenInput)
    coverage_reference = paragraph('Whole PhilHealth policy / coverage reconciliation', required=False)
    reference = paragraph('Whole package preparation reference', required=False)
    authority = forms.FileField(label='Original PhilHealth policy authority (PDF, PNG or JPEG, up to 8 MiB)', required=False)
    reconciliation = forms.FileField(label='Original PhilHealth overlap reconciliation (PDF, PNG or JPEG, up to 8 MiB)', required=False)


def cells(flow, actor, data=None, files=None):
    result = []
    for member_index, member in enumerate(flow['payload']['members']):
        scope = member['scope']; year = scope['budget_year']
        for column in stocks.OPENINGS:
            day = {'prior_amount': date(year-2, 1, 1), 'half_amount': date(year-1, 1, 1),
                'estimate': date(year-1, 7, 1), 'proposed': date(year, 1, 1)}[column]
            expected = dict(department_id=scope['accounting_department_id'], budget_department_id=scope['budget_department_id'],
                treasury_department_id=scope['treasury_department_id'], fund_id=scope['fund_id'],
                entity_key=member['entity_key'], balance_date=day.isoformat(), boundary='start_of_day')
            anchors = {}; choices = []; original_links = []
            filters = {key: value for key, value in expected.items() if key not in ('balance_date', 'boundary')}
            for route, service in (('historical', budget_cash), ('native', budget_cash_preparations)):
                try: query = service.visible(actor).filter(**filters, balance_date__lte=day)
                except PermissionDenied: continue
                if route == 'historical': query = query.filter(status='adopted')
                for record in query.order_by('-balance_date', '-version'):
                    identity = route+':'+str(record.public_id)
                    anchors[identity] = dict(expected, balance_date=record.balance_date.isoformat(), boundary=record.boundary)
                    choices.append((identity, f'{route.title()} · {record.balance_date} / {record.boundary} · v{record.version} · {record.public_id}'))
                    original_links.append(dict(label=choices[-1][1], url=reverse('accounting:'+
                        ('budget_cash_detail' if route=='historical' else 'native_cash_detail'), args=[record.public_id])))
            form = Opening(data, files, choices=choices, column=column, prefix=f'opening-{member_index}-{column}')
            result.append(dict(entity=member['entity_key'], entity_label=member['entity_label'], column=column,
                label=COLUMNS[column], scope=expected, anchors=anchors, original_links=original_links, form=form))
    return result


def capture_stock(source, actor, openings, boundary):
    selections = {}; evidence = {}
    for cell in openings:
        data = cell['form'].cleaned_data; kind = data['kind']
        if kind == 'missing': choice = dict(kind=kind, basis=data['missing_basis'])
        else:
            route, identity = data['source'].split(':', 1)
            actual = sources.capture(route=route, identity=identity, actor=actor,
                expected_scope=cell['scope'] if kind == 'actual' else cell['anchors'][data['source']])
            if kind == 'forecast':
                inputs = {name: data[name] for name in forecasts.INPUTS if name not in ('target_date', 'target_boundary')}
                for name in ('cash_changes', 'proposed_restrictions', 'restriction_changes'):
                    inputs[name] = inputs[name] if inputs[name] is not None else []
                inputs.update(target_date=cell['scope']['balance_date'], target_boundary=cell['scope']['boundary'])
                actual, original = forecasts.propose(source=actual, actor=actor, evidence=data['worksheet'], **inputs)
                evidence[actual['checksum']] = original
            choice = dict(kind=kind, source=actual)
        selections.setdefault(cell['entity'], {})[cell['column']] = choice
    stock = stocks.capture(forecast=source.account_review.forecast, actor=actor,
        selections=[dict(entity_key=entity, opening=opening) for entity, opening in selections.items()], evidence=evidence,
        stock_convention=stocks.CONVENTION, boundary_basis=boundary.cleaned_data['boundary_basis'])
    return stock, evidence


def editor(source, form):
    body = source['payload']; stock = body['stock']['payload']
    entities = {row['entity_key']: row['scope']['entity_label'] for row in stock['members']}
    labels = {row['key']: row for row in components(body['flow_inventory'])}
    catalog = []
    for row in body['catalog']:
        if row['kind'] == 'restriction':
            original = row['original_restriction']['original']
            label = original['reference']+' · '+original['purpose']
        else:
            component = labels[row['key']]
            label = component['category_label']+' · '+component['source_label']+' · '+component['source_account_label']
        catalog.append({key: row[key] for key in ('key','kind','entity','column','amount')} | dict(
            entity_label=entities[row['entity']], column_label=COLUMNS[row['column']], label=label))
    matrix = [dict(entity=entity, entity_label=label, column=column, column_label=COLUMNS[column], kind=kind)
        for entity,label in entities.items() for column in stocks.OPENINGS for kind in philhealth.KINDS]
    return dict(catalog=catalog, matrix=matrix, treatments=philhealth.TREATMENTS,
        parts=form.cleaned_data.get('parts'), coverage=form.cleaned_data.get('coverage'))


@login_required
@require_http_methods(['GET', 'POST'])
def prepare(request, public_id):
    from vouchers.roles import is_finance_uat_viewer
    actor = request.user; owner = department_for_user(actor)
    if not owner or not actor.is_active or is_finance_uat_viewer(actor) or not has_budget_permission(actor, 'prepare_form1_packages'):
        raise PermissionDenied('Use the designated Budget package preparer.')
    source = get_object_or_404(Form1SPAReview.objects.select_related('proposal__fiscal_year','fund','account_review__forecast'),
        public_id=public_id, department_id=owner.pk)
    try:
        retained = spa.snapshot(source, actor)
        if retained['status'] != 'approved' or not spa.is_current(source, actor):
            raise ValidationError('Select a current independently approved SPA source.')
        flow = flows.capture(forecast=source.account_review.forecast, actor=actor)
        packages._access(source.proposal, source.fund, flow['payload'], actor, 'prepare')
    except ValidationError as error: return HttpResponse(' '.join(error.messages), status=409)
    data = request.POST if request.method == 'POST' else None
    files = request.FILES if request.method == 'POST' else None
    boundary = Boundary(data); openings = cells(flow, actor, data, files); treatment = Treatment(data, files)
    current = dict(actor=actor.pk, spa=str(source.public_id), source=retained['payload_checksum'],
        decisions=retained['decisions'], latest=Form1Package.objects.filter(proposal=source.proposal,
            fund=source.fund).aggregate(n=Max('version'))['n'] or 0)
    ph_source = None; editor_data = None; status = 200
    if data is not None:
        if data.get('action') not in ('preview', 'retain'): return HttpResponse('Choose source preview or draft retention.', status=400)
        valid = boundary.is_valid()
        for cell in openings: valid = cell['form'].is_valid() and valid
        valid = treatment.is_valid() and valid
        if valid:
            try:
                stock, evidence = capture_stock(source, actor, openings, boundary)
                ph_source = philhealth.capture(stock=stock, actor=actor, evidence=evidence)
                expected = dict(current, inventory=ph_source['checksum'])
                if data['action'] == 'retain':
                    signed = signing.loads(treatment.cleaned_data['preview'], salt=SALT, max_age=3600)
                    if signed != expected: raise ValidationError('Sources, worksheet bytes, actor or package version changed. Preview the original sources again.')
                    ph, documents = philhealth.prepare(source=ph_source, actor=actor, evidence=evidence,
                        **{key:treatment.cleaned_data[key] for key in ('parts','coverage','coverage_reference','authority','reconciliation')})
                    envelope = assembly.capture(spa_review=source, philhealth_source=ph, actor=actor, evidence=evidence, documents=documents)
                    record = packages.prepare(spa_review=source, envelope=envelope, actor=actor, evidence=evidence,
                        documents=documents, reference=treatment.cleaned_data['reference'], expected_latest=signed['latest'])
                    return redirect('budget:form1_package_detail', public_id=record.public_id)
                # Preview is read-only. Retention requires the original uploads again;
                # no provisional records or attachment cache become financial evidence.
                treatment.data = treatment.data.copy()
                treatment.data['preview'] = signing.dumps(expected, salt=SALT, compress=True)
                try: previous = signing.loads(treatment.cleaned_data['preview'], salt=SALT, max_age=3600)
                except signing.BadSignature: previous = None
                if previous != expected:
                    # A new source inventory cannot inherit hidden partitions of
                    # a different inventory. Choices restart unresolved/missing.
                    treatment.cleaned_data['parts'] = None
                    treatment.cleaned_data['coverage'] = None
                editor_data = editor(ph_source, treatment)
            except (ValidationError, signing.BadSignature) as error:
                treatment.add_error(None, error if isinstance(error, ValidationError) else 'The original source preview is invalid or expired.')
                status = 409
                if ph_source is not None: editor_data = editor(ph_source, treatment)
        else: status = 409
    return render(request, 'budget/form1_package_prepare.html', dict(source=source, boundary=boundary,
        openings=openings, treatment=treatment, editor=editor_data), status=status)
