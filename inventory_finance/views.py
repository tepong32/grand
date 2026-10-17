from uuid import uuid4

from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from inventory.access import department_for_user, gso_department_for_user
from inventory.finance_sources import resolve_claim_line
from vouchers.access import can_manage_owned_case_artifact, can_view_workbench, has_explicit_permission
from vouchers.case_exports import visible_cases_for_user
from vouchers.models import VoucherCase
from vouchers.roles import is_finance_uat_viewer

from .access import visible_attributions
from .forms import ProposalForm, ConfirmProposalForm, ReviewForm
from .models import ReceiptClaimAttribution
from .services import propose_attribution, approve_attribution, close_attribution
from .receipt_basis import receipt_basis, receipt_basis_current
from .journal_sources import can_inspect_journals, inspect_recognition

TOKEN_SALT = "gso-receipt-claim-proposal-v1"


def _require_access(actor):
    if not can_view_workbench(actor) or not any(has_explicit_permission(
            actor, f"inventory_finance.{action}_receiptclaimattribution") for action in ("view", "propose", "review")):
        raise PermissionDenied


def _can_propose(actor):
    department = department_for_user(actor)
    return bool(department and department == gso_department_for_user(actor)
        and not is_finance_uat_viewer(actor)
        and has_explicit_permission(actor, "inventory_finance.propose_receiptclaimattribution"))


@login_required
@never_cache
@require_http_methods(["GET"])
def workbench(request):
    _require_access(request.user)
    rows = visible_attributions(request.user).select_related("receipt_line__receipt", "case")
    cases = visible_cases_for_user(request.user, VoucherCase.objects.filter(
        disbursement_voucher__isnull=False)) if _can_propose(request.user) else VoucherCase.objects.none()
    return render(request, "inventory_finance/workbench.html", {
        "page": Paginator(rows, 30).get_page(request.GET.get("page")),
        "case_page": Paginator(cases.order_by("-pk"), 20).get_page(request.GET.get("case_page")),
        "can_propose": _can_propose(request.user),
    })


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def propose(request, case_id):
    _require_access(request.user)
    if not _can_propose(request.user):
        raise PermissionDenied
    case = get_object_or_404(visible_cases_for_user(request.user), public_id=case_id)
    form = ProposalForm(request.POST or None, department=department_for_user(request.user), case=case)
    preview = None
    confirmation = None
    if request.method == "POST" and request.POST.get("action") == "confirm":
        confirmation = ConfirmProposalForm(request.POST)
        if confirmation.is_valid():
            try:
                payload = signing.loads(confirmation.cleaned_data["proposal_token"], salt=TOKEN_SALT, max_age=1800)
                if payload["actor_id"] != request.user.pk or payload["case_id"] != str(case.public_id):
                    raise PermissionDenied
                row = propose_attribution(actor=request.user, receipt_line_id=payload["receipt_line_id"],
                    case_public_id=case.public_id, source_line_id=payload["source_line_id"],
                    source_checksum=payload["source_checksum"], amount=payload["amount"], basis=payload["basis"],
                    request_id=payload["request_id"], expected_receipt_basis=payload.get("receipt_basis"))
                return redirect("inventory_finance:detail", attribution_id=row.public_id)
            except signing.BadSignature:
                form.add_error(None, "This preview expired or changed. Preview the proposal again.")
            except ValidationError as exc:
                form.add_error(None, exc)
        else:
            form.add_error(None, "Preview the proposal before confirming it.")
    elif request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            source = resolve_claim_line(actor=request.user, case_public_id=case.public_id,
                                        line_id=data["source_line"].pk)
            payload = {"actor_id": request.user.pk, "case_id": str(case.public_id),
                "receipt_line_id": data["receipt_line"].pk, "source_line_id": data["source_line"].pk,
                "source_checksum": source["sha256"], "amount": str(data["amount"]),
                "basis": data["basis"], "request_id": str(uuid4()),
                "receipt_basis": receipt_basis(data["receipt_line"])}
            confirmation = ConfirmProposalForm(initial={"proposal_token": signing.dumps(payload, salt=TOKEN_SALT)})
            preview = {"source": source["source"], "amount": data["amount"], "basis": data["basis"],
                       "receipt_line": data["receipt_line"], "receipt_basis": payload["receipt_basis"]}
        except ValidationError as exc:
            form.add_error(None, exc)
    return render(request, "inventory_finance/propose.html", {
        "case": case, "form": form, "preview": preview, "confirmation": confirmation})


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def detail(request, attribution_id):
    _require_access(request.user)
    row = get_object_or_404(visible_attributions(request.user).select_related(
        "receipt_line__receipt", "case__configuration_release", "proposed_by", "reviewed_by"), public_id=attribution_id)
    can_review = can_manage_owned_case_artifact(request.user, row.case,
        "inventory_finance.review_receiptclaimattribution")
    source_current = False
    try:
        source_current = resolve_claim_line(actor=request.user, case_public_id=row.case.public_id,
            line_id=row.source_line_id)["sha256"] == row.source_checksum
    except ValidationError:
        pass
    receipt_current = receipt_basis_current(row)
    form = ReviewForm(request.POST or None, initial={"expected_version": row.state_version})
    actions = []
    if row.status == row.PROPOSED:
        if row.proposed_by_id != request.user.pk:
            if source_current and receipt_current:
                actions.append(("approve", "Approve support"))
            actions.append(("reject", "Reject proposal"))
        actions.append(("withdraw", "Withdraw link"))
    elif row.status == row.APPROVED:
        actions.append(("withdraw", "Withdraw link"))
    form.fields["action"].choices = actions
    can_review = can_review and bool(actions)
    if request.method == "POST":
        if not can_review:
            raise PermissionDenied
        if form.is_valid():
            try:
                data = form.cleaned_data
                if data["action"] == "approve":
                    approve_attribution(actor=request.user, attribution_id=row.public_id,
                                        expected_version=data["expected_version"], note=data["note"])
                else:
                    close_attribution(actor=request.user, attribution_id=row.public_id,
                        expected_version=data["expected_version"], action=data["action"], reason=data["note"])
                return redirect("inventory_finance:detail", attribution_id=row.public_id)
            except ValidationError as exc:
                form.add_error(None, exc)
    return render(request, "inventory_finance/detail.html", {
        "row": row, "form": form, "can_review": can_review, "source_current": source_current,
        "receipt_current": receipt_current,
        "can_inspect_journals": can_inspect_journals(request.user, row.case),
        "events": row.events.select_related("actor").all()})


@login_required
@never_cache
@require_http_methods(["GET"])
def journal_sources(request, attribution_id):
    row = get_object_or_404(visible_attributions(request.user).select_related(
        "case__configuration_release"), public_id=attribution_id)
    if not can_inspect_journals(request.user, row.case):
        raise PermissionDenied
    from vouchers.models import VoucherPostingRequest
    sources = VoucherPostingRequest.objects.filter(case=row.case, kind="recognition",
        finance_department_id=row.case.configuration_release.department_id).select_related("case").order_by("-version", "-pk")
    page = Paginator(sources, 20).get_page(request.GET.get("page"))
    observations = [{"source": source, **inspect_recognition(source, actor=request.user)} for source in page]
    return render(request, "inventory_finance/journal_sources.html", {
        "row": row, "page": page, "observations": observations})
