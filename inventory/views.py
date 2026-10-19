import csv
from urllib.parse import urlencode
from uuid import uuid4

from .employee_sources import can_manage_employee_custody
from . import property_determinations as property_service

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core import signing
from django.core.paginator import Paginator
from django.db.models import Q
from django.db.models import Sum
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from .access import (
    _is_gso_department, asset_access_required, asset_in_scope, can,
    can_acknowledge_asset_transfer, can_request_asset_disposal,
    can_review_asset_disposal, can_stock, can_transfer_asset, can_view_audit,
    can_manage_asset_verification, has_inventory_permission,
    department_for_user, department_model, gso_department_for_user,
)
from .forms import (
    AssetDisposalRequestForm, AssetDisposalResponseForm, AssetDisposalReviewForm,
    AssetForm, AssetTransferForm, ConsumableItemForm, StockAdjustmentForm,
    StockIssueForm, StockReceiptForm, TransferCancellationForm,
    StockHistoryFilterForm,
    AssetVerificationRoundForm, AssetVerificationRecordForm, AssetVerificationFollowUpForm,
    AssetVerificationFindingForm, AssetVerificationFindingReviewForm, AssetAccountingImportForm,
)
from .models import (
    Asset, AssetDisposalAttachment, AssetDisposalCase, AssetTransfer,
    AssetVerificationFinding,
    AssetVerificationRecord, AssetVerificationRound, AssetAccountingImport,
    ConsumableItem, StockMovement,
)
from .services import (
    acknowledge_asset_transfer, cancel_asset_transfer, create_asset,
    create_asset_transfer, create_consumable, record_stock_movement,
    respond_to_disposal_case, review_asset_disposal_case,
    submit_asset_disposal_request, update_asset, update_consumable,
    start_asset_verification_round, record_asset_verification, close_asset_verification_round,
    resolve_asset_verification_followup, verification_observation, record_unregistered_verification_finding,
    review_unregistered_verification_finding, import_accounting_asset_snapshot,
)


def _csv_cell(value):
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + value
    return value


def _scoped_assets(user):
    if user.is_superuser:
        return Asset.objects.all()
    department = department_for_user(user)
    if not department:
        raise PermissionDenied
    if _is_gso_department(department):
        return Asset.objects.filter(department_id=department.pk)
    return Asset.objects.filter(assigned_department_id=department.pk)


@login_required
def dashboard(request):
    from .custody_review import can_view_custody_review
    from .office_records import workspace_url
    from .maintenance_views import can_view_maintenance
    if not can(request.user, "view"):
        from .receiving import require_receiving
        require_receiving(request.user, "view")
        return redirect("inventory:receiving-list")
    assets = _scoped_assets(request.user)
    return render(request, "inventory/dashboard.html", {
        "department": department_for_user(request.user) or gso_department_for_user(request.user),
        "office_records_url": workspace_url(request.user),
        "is_gso": request.user.is_superuser or _is_gso_department(department_for_user(request.user)),
        "total_assets": assets.count(),
        "in_service_count": assets.filter(status=Asset.ACTIVE).count(),
        "maintenance_count": assets.filter(status=Asset.MAINTENANCE).count(),
        "can_view_maintenance": can_view_maintenance(request.user),
        "can_view_custody_review": can_view_custody_review(request.user),
        "retired_count": assets.filter(status=Asset.RETIRED).count(),
        "can_add": can(request.user, "add"),
        "can_view_stock": can_stock(request.user, "view"),
        "can_view_transfers": can_transfer_asset(request.user, read_only=True) or can_acknowledge_asset_transfer(request.user, read_only=True),
        "pending_transfer_count": _transfer_queryset(request.user).filter(status=AssetTransfer.PENDING).count()
        if can_transfer_asset(request.user, read_only=True) or can_acknowledge_asset_transfer(request.user, read_only=True) else 0,
        "can_view_disposals": can_review_asset_disposal(request.user, read_only=True) or can_request_asset_disposal(request.user, read_only=True),
        "open_disposal_count": _disposal_queryset(request.user).filter(status__in=(
            AssetDisposalCase.SUBMITTED, AssetDisposalCase.UNDER_REVIEW,
            AssetDisposalCase.NEEDS_INFORMATION, AssetDisposalCase.AUTHORIZED,
        )).count() if can_review_asset_disposal(request.user, read_only=True) or can_request_asset_disposal(request.user, read_only=True) else 0,
        "can_view_verifications": any(can_manage_asset_verification(request.user, action, read_only=True) for action in ("start", "record", "close", "import")),
        "open_verification_count": _verification_round_queryset(request.user).filter(closed_at__isnull=True).count()
        if any(can_manage_asset_verification(request.user, action, read_only=True) for action in ("start", "record", "close", "import")) else 0,
    })


@asset_access_required("view")
def asset_list(request):
    assets = _scoped_assets(request.user)
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    inventory_class = request.GET.get("class", "").strip()
    if query:
        class_matches = [
            value for value, label in Asset.INVENTORY_CLASS_CHOICES
            if query.casefold() in label.casefold()
        ]
        item_type_matches = [
            value for value, label in Asset.ITEM_TYPE_CHOICES
            if query.casefold() in label.casefold()
        ]
        assets = assets.filter(
            Q(asset_name__icontains=query) | Q(inventory_class__icontains=query)
            | Q(inventory_class__in=class_matches) | Q(item_type__icontains=query)
            | Q(item_type__in=item_type_matches) | Q(category__icontains=query)
            | Q(property_tag__icontains=query)
            | Q(brand__icontains=query) | Q(serial_number__icontains=query)
            | Q(obr_reference__icontains=query) | Q(assigned_office__icontains=query)
        )
    if status in dict(Asset.STATUS_CHOICES):
        assets = assets.filter(status=status)
    if inventory_class in dict(Asset.INVENTORY_CLASS_CHOICES):
        assets = assets.filter(inventory_class=inventory_class)
    page = Paginator(assets, 25).get_page(request.GET.get("page"))
    return render(request, "inventory/asset_list.html", {
        "page": page, "query": query, "selected_status": status,
        "selected_class": inventory_class,
        "inventory_classes": Asset.INVENTORY_CLASS_CHOICES,
        "statuses": Asset.STATUS_CHOICES,
        "can_add": can(request.user, "add"),
        "can_change": can(request.user, "change"),
        "can_retire": can(request.user, "delete"),
        "can_export": can(request.user, "export"),
    })


@asset_access_required("export")
def asset_export(request):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="gso-asset-register.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow((
        "Property tag", "Asset type", "Inventory class", "Item type", "Name", "Additional description", "Brand", "Model", "Serial number",
        "Plate number", "Engine number", "Chassis number", "Status", "Department", "Office / custodian",
        "Acquisition date", "Acquisition cost", "Fund", "COA account code", "COA account title",
        "Mapping reference", "OBR", "PO / contract", "Voucher", "Journal", "Asset UUID",
    ))
    for asset in _scoped_assets(request.user).order_by("asset_name", "pk"):
        writer.writerow(_csv_cell(value) for value in (
            asset.property_tag, asset.get_asset_kind_display(), asset.get_inventory_class_display(),
            asset.get_item_type_display(), asset.asset_name, asset.category, asset.brand,
            asset.model_number, asset.serial_number, asset.plate_number, asset.engine_number, asset.chassis_number,
            asset.get_status_display(), asset.assigned_department_label, asset.assigned_office,
            asset.purchase_date or "", asset.unit_cost if asset.unit_cost is not None else "", asset.fund_code, asset.coa_account_code,
            asset.coa_account_title, asset.coa_basis, asset.obr_reference, asset.purchase_order_reference,
            asset.voucher_reference, asset.journal_reference, str(asset.public_id),
        ))
    return response


@asset_access_required("view")
def asset_detail(request, pk):
    from . import property_movements as movement_service
    from .custody_returns import can_manage_return
    from .maintenance import can_manage_maintenance
    from .maintenance_views import can_view_maintenance
    asset = get_object_or_404(_scoped_assets(request.user), pk=pk)
    pending_transfer = asset.transfers.filter(status=AssetTransfer.PENDING).first()
    open_maintenance = asset.maintenance_cases.filter(status="open").exists()
    from .receipt_quantity_corrections import require_asset_available
    correction_hold = ""
    try:
        require_asset_available(asset)
    except ValidationError as exc:
        correction_hold = " ".join(exc.messages)
    correction_source = None
    if correction_hold:
        from .models import ReceivingLine
        from .receiving import can_receiving
        source = ReceivingLine.objects.select_related("receipt").filter(registered_asset=asset).first()
        if source and can_receiving(request.user, "view", source.receipt):
            correction_source = source
    open_disposal = asset.disposal_cases.filter(status__in=(
        AssetDisposalCase.SUBMITTED, AssetDisposalCase.UNDER_REVIEW,
        AssetDisposalCase.NEEDS_INFORMATION, AssetDisposalCase.AUTHORIZED)).exists()
    return render(request, "inventory/asset_detail.html", {
        "asset": asset,
        "correction_hold": correction_hold,
        "correction_source": correction_source,
        "can_record_return": can_manage_return(request.user, "record", asset) and asset.custodian_user_id
        and asset.custodian_user_id != request.user.pk and not pending_transfer and not open_disposal and asset.status != Asset.RETIRED and not correction_hold,
        "events": asset.audit_events.all() if can_view_audit(request.user) else (),
        "can_change": can(request.user, "change") and not open_maintenance and not correction_hold,
        "can_property_records": property_service.can_act(request.user, "view", asset),
        "can_property_movements": movement_service.can_act(request.user, "view", asset),
        "maintenance_history": asset.maintenance_cases.all() if can_view_maintenance(request.user) else (),
        "can_start_maintenance": can_manage_maintenance(request.user, asset) and not open_maintenance
        and not open_disposal and pending_transfer is None and asset.status != Asset.RETIRED and not correction_hold,
        "can_retire": can(request.user, "delete"),
        "can_view_audit": can_view_audit(request.user),
        "can_transfer": can_transfer_asset(request.user) and pending_transfer is None and asset.status != Asset.RETIRED and not open_maintenance and not correction_hold,
        "can_employee_handoff": can_manage_employee_custody(request.user),
        "pending_transfer": pending_transfer,
        "transfer_history": asset.transfers.all() if can_view_audit(request.user) else (),
        "can_request_disposal": can_request_asset_disposal(request.user, asset)
        and not open_maintenance
        and not asset.transfers.filter(status=AssetTransfer.PENDING).exists()
        and not asset.disposal_cases.filter(status__in=(
            AssetDisposalCase.SUBMITTED, AssetDisposalCase.UNDER_REVIEW,
            AssetDisposalCase.NEEDS_INFORMATION, AssetDisposalCase.AUTHORIZED,
        )).exists() and asset.status != Asset.RETIRED and not correction_hold,
        "disposal_case": asset.disposal_cases.exclude(status=AssetDisposalCase.REJECTED).first(),
    })


@asset_access_required("add")
def asset_create(request):
    form = AssetForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            asset = create_asset(actor=request.user, data=form.cleaned_data)
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, "Asset added to the register.")
            return redirect("inventory:asset-detail", pk=asset.pk)
    return render(request, "inventory/asset_form.html", {"form": form, "heading": "Add an asset"})


@asset_access_required("change")
def asset_edit(request, pk):
    asset = get_object_or_404(_scoped_assets(request.user), pk=pk)
    if asset.status in (Asset.RETIRED, Asset.ENTRY_VOID):
        raise PermissionDenied("Retired and corrected erroneous entries are read-only.")
    if asset.transfers.filter(status=AssetTransfer.PENDING).exists():
        messages.error(request, "This asset has a handoff waiting for acknowledgment. Cancel it before editing the record.")
        return redirect("inventory:asset-detail", pk=asset.pk)
    if asset.disposal_cases.filter(status__in=(
        AssetDisposalCase.SUBMITTED, AssetDisposalCase.UNDER_REVIEW,
        AssetDisposalCase.NEEDS_INFORMATION, AssetDisposalCase.AUTHORIZED,
    )).exists():
        messages.error(request, "This asset has an open disposal case and cannot be edited.")
        return redirect("inventory:asset-detail", pk=asset.pk)
    form = AssetForm(request.POST or None, instance=asset)
    if request.method == "POST" and form.is_valid():
        try:
            asset = update_asset(actor=request.user, asset=asset, data=form.cleaned_data)
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, "Asset record updated.")
            return redirect("inventory:asset-detail", pk=asset.pk)
    return render(request, "inventory/asset_form.html", {"form": form, "asset": asset, "heading": "Edit asset"})


@asset_access_required("delete")
@require_POST
def asset_retire(request, pk):
    asset = get_object_or_404(_scoped_assets(request.user), pk=pk)
    messages.info(request, "Assets must be retired through a reviewed disposal case.")
    if can_request_asset_disposal(request.user, asset):
        return redirect("inventory:asset-disposal-request", pk=asset.pk)
    return redirect("inventory:asset-detail", pk=asset.pk)


def _transfer_queryset(user):
    transfers = AssetTransfer.objects.select_related("asset", "requested_by", "acknowledged_by", "cancelled_by")
    if user.is_superuser:
        return transfers
    department = department_for_user(user)
    if not department:
        return transfers.none()
    if _is_gso_department(department):
        return transfers.filter(Q(asset__department_id=department.pk) | Q(destination_custodian_user=user)
            | Q(kind=AssetTransfer.RETURN, source_custodian_user=user))
    return transfers.filter(Q(destination_department_id=department.pk) | Q(destination_custodian_user=user)
        | Q(kind=AssetTransfer.RETURN, source_custodian_user=user))


@asset_access_required("view")
def asset_transfer_list(request):
    if not (can_transfer_asset(request.user, read_only=True) or can_acknowledge_asset_transfer(request.user, read_only=True)):
        raise PermissionDenied
    rows = list(_transfer_queryset(request.user))
    for transfer in rows:
        transfer.user_can_acknowledge = can_acknowledge_asset_transfer(request.user, transfer)
        transfer.user_can_view_asset = asset_in_scope(request.user, transfer.asset)
        transfer.user_can_cancel = (transfer.kind != AssetTransfer.RETURN and can_transfer_asset(request.user) and asset_in_scope(request.user, transfer.asset)
            and (not transfer.destination_custodian_user_id or can_manage_employee_custody(request.user)))
    return render(request, "inventory/asset_transfer_list.html", {
        "transfers": rows,
        "is_gso": can_transfer_asset(request.user),
        "can_cancel": can_transfer_asset(request.user),
        "can_acknowledge": can_acknowledge_asset_transfer(request.user),
    })


@asset_access_required("view")
def asset_transfer_create(request, pk):
    if not can_transfer_asset(request.user):
        raise PermissionDenied
    asset = get_object_or_404(_scoped_assets(request.user), pk=pk)
    if asset.custodian_user_id or asset.last_custody_return_id:
        return redirect("inventory:employee-handoff", pk=asset.pk)
    if asset.status == Asset.RETIRED or asset.transfers.filter(status=AssetTransfer.PENDING).exists():
        messages.error(request, "This asset cannot start another handoff right now.")
        return redirect("inventory:asset-detail", pk=asset.pk)
    form = AssetTransferForm(request.POST or None, asset=asset)
    if request.method == "POST" and form.is_valid():
        try:
            transfer = create_asset_transfer(actor=request.user, asset=asset, data=form.cleaned_data)
        except (PermissionDenied, ValidationError) as error:
            form.add_error(None, error)
        else:
            messages.success(request, "Handoff sent. The receiving department must acknowledge it before the assignment changes.")
            return redirect("inventory:asset-detail", pk=transfer.asset_id)
    return render(request, "inventory/asset_transfer_form.html", {"form": form, "asset": asset,
        "can_employee_handoff": can_manage_employee_custody(request.user)})


@asset_access_required("view")
@require_POST
def asset_transfer_acknowledge(request, pk):
    transfer = get_object_or_404(_transfer_queryset(request.user), pk=pk)
    try:
        acknowledge_asset_transfer(actor=request.user, transfer=transfer)
    except (PermissionDenied, ValidationError) as error:
        messages.error(request, str(error))
    else:
        messages.success(request, "Handoff acknowledged. The asset is now recorded in your custody."
            if transfer.destination_custodian_user_id else "Handoff acknowledged. The asset is now assigned to your department.")
    return redirect("inventory:asset-transfer-list")


@asset_access_required("view")
@require_POST
def asset_transfer_cancel(request, pk):
    transfer = get_object_or_404(_transfer_queryset(request.user), pk=pk)
    form = TransferCancellationForm(request.POST)
    if form.is_valid():
        try:
            cancel_asset_transfer(actor=request.user, transfer=transfer, reason=form.cleaned_data["reason"])
        except (PermissionDenied, ValidationError) as error:
            messages.error(request, str(error))
        else:
            messages.success(request, "Pending handoff cancelled; the current assignment is unchanged.")
    else:
        messages.error(request, "Enter a reason before cancelling the handoff.")
    return redirect("inventory:asset-transfer-list")


def _verification_round_queryset(user):
    rounds = AssetVerificationRound.objects.select_related("created_by", "closed_by")
    if user.is_superuser:
        return rounds
    department = gso_department_for_user(user)
    return rounds.filter(department_id=department.pk) if department else rounds.none()


@asset_access_required("view")
def asset_verification_list(request):
    if not any(can_manage_asset_verification(request.user, action, read_only=True) for action in ("start", "record", "close")):
        raise PermissionDenied
    form = AssetVerificationRoundForm(request.POST or None) if can_manage_asset_verification(request.user, "start") else None
    if request.method == "POST":
        if not can_manage_asset_verification(request.user, "start"):
            raise PermissionDenied
        if not form or not form.is_valid():
            return render(request, "inventory/asset_verification_list.html", {"rounds": _verification_round_queryset(request.user), "form": form, "can_start": bool(form)})
        try:
            verification_round = start_asset_verification_round(
                actor=request.user, title=form.cleaned_data["title"], as_of_date=form.cleaned_data["as_of_date"],
            )
        except (PermissionDenied, ValidationError) as error:
            form.add_error(None, error)
        else:
            messages.success(request, "Verification round created with a snapshot of all active GSO assets.")
            return redirect("inventory:asset-verification-detail", pk=verification_round.pk)
    return render(request, "inventory/asset_verification_list.html", {
        "rounds": _verification_round_queryset(request.user), "form": form,
        "can_start": can_manage_asset_verification(request.user, "start"),
    })


@asset_access_required("view")
def asset_verification_detail(request, pk):
    if not any(can_manage_asset_verification(request.user, action, read_only=True) for action in ("start", "record", "close")):
        raise PermissionDenied
    verification_round = get_object_or_404(_verification_round_queryset(request.user), pk=pk)
    records = verification_round.records.select_related("verified_by")
    counts = {key: records.filter(result=key).count() for key, _ in AssetVerificationRecord.RESULT_CHOICES}
    findings = verification_round.findings.select_related("recorded_by", "reviewed_by", "related_asset")
    pending_findings = findings.filter(status=AssetVerificationFinding.PENDING).count()
    pending_followups = records.filter(
        result__in=(AssetVerificationRecord.DISCREPANCY, AssetVerificationRecord.NOT_FOUND),
        follow_up_status=AssetVerificationRecord.FOLLOW_UP_OPEN,
    ).count()
    if request.method == "POST":
        if not can_manage_asset_verification(request.user, "close"):
            raise PermissionDenied
        try:
            close_asset_verification_round(actor=request.user, verification_round=verification_round)
        except (PermissionDenied, ValidationError) as error:
            messages.error(request, str(error))
        else:
            messages.success(request, "Verification round closed. Its recorded results remain available for review.")
        return redirect("inventory:asset-verification-detail", pk=verification_round.pk)
    return render(request, "inventory/asset_verification_detail.html", {
        "verification_round": verification_round, "records": records,
        "counts": counts, "can_record": can_manage_asset_verification(request.user, "record"),
        "can_close": can_manage_asset_verification(request.user, "close"),
        "findings": findings, "pending_findings": pending_findings,
        "pending_followups": pending_followups,
    })


@asset_access_required("view")
def asset_verification_record(request, pk):
    if not can_manage_asset_verification(request.user, "record"):
        raise PermissionDenied
    record = get_object_or_404(
        AssetVerificationRecord.objects.select_related("verification_round"),
        pk=pk, verification_round__in=_verification_round_queryset(request.user),
    )
    form = None if record.verification_round.closed_at else AssetVerificationRecordForm(request.POST or None, initial={
        "result": record.result if record.result != AssetVerificationRecord.NOT_CHECKED else "",
        "observed_department": record.observed_department,
        "observed_office": record.observed_office,
        "condition": record.condition,
        "notes": record.notes,
    })
    if request.method == "POST" and form and form.is_valid():
        try:
            record_asset_verification(actor=request.user, record=record, data=form.cleaned_data)
        except (PermissionDenied, ValidationError) as error:
            form.add_error(None, error)
        else:
            messages.success(request, "Physical check recorded in the verification history.")
            return redirect("inventory:asset-verification-detail", pk=record.verification_round_id)
    return render(request, "inventory/asset_verification_record.html", {
        "record": record, "form": form, "events": record.events.select_related("actor").all(),
    })


@asset_access_required("view")
def asset_verification_followup(request, pk):
    if not can_manage_asset_verification(request.user, "record"):
        raise PermissionDenied
    record = get_object_or_404(
        AssetVerificationRecord.objects.select_related("verification_round"),
        pk=pk, verification_round__in=_verification_round_queryset(request.user),
    )
    review_token = signing.dumps({"actor": request.user.pk, "record": record.pk,
        "observation": verification_observation(record),
        "event": record.events.order_by("-pk").values_list("pk", flat=True).first()},
        salt="inventory.verification-followup")
    form = AssetVerificationFollowUpForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            try:
                basis = signing.loads(request.POST.get("review_token", ""),
                    salt="inventory.verification-followup", max_age=1800)
            except signing.BadSignature:
                raise ValidationError("This review form expired or is invalid. Reload and review again.")
            if basis.get("actor") != request.user.pk or basis.get("record") != record.pk:
                raise PermissionDenied
            resolve_asset_verification_followup(
                expected_event_id=basis.get("event"), expected_observation=basis.get("observation"),
                actor=request.user, record=record, status=form.cleaned_data["status"],
                note=form.cleaned_data["note"],
            )
        except (PermissionDenied, ValidationError) as error:
            form.add_error(None, error)
        else:
            messages.success(request, "Follow-up decision recorded in the verification history.")
            return redirect("inventory:asset-verification-detail", pk=record.verification_round_id)
    return render(request, "inventory/asset_verification_followup.html", {"record": record, "form": form, "review_token": review_token})


@asset_access_required("view")
def asset_verification_finding_add(request, pk):
    if not can_manage_asset_verification(request.user, "record"):
        raise PermissionDenied
    verification_round = get_object_or_404(_verification_round_queryset(request.user), pk=pk)
    if verification_round.closed_at:
        raise PermissionDenied("This verification round is closed.")
    form = AssetVerificationFindingForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            finding = record_unregistered_verification_finding(
                actor=request.user, verification_round=verification_round, data=form.cleaned_data,
            )
        except (PermissionDenied, ValidationError) as error:
            form.add_error(None, error)
        else:
            messages.success(request, "Unregistered item recorded for GSO review.")
            return redirect("inventory:asset-verification-finding-review", pk=finding.pk)
    return render(request, "inventory/asset_verification_finding_form.html", {
        "verification_round": verification_round, "form": form,
    })


@asset_access_required("view")
def asset_verification_finding_review(request, pk):
    if not can_manage_asset_verification(request.user, "record"):
        raise PermissionDenied
    finding = get_object_or_404(
        AssetVerificationFinding.objects.select_related("verification_round", "recorded_by", "related_asset"),
        pk=pk, verification_round__in=_verification_round_queryset(request.user),
    )
    form = AssetVerificationFindingReviewForm(
        request.POST or None, verification_round=finding.verification_round,
        initial={"status": finding.status, "related_asset": finding.related_asset_id, "resolution_note": finding.resolution_note},
    )
    if request.method == "POST" and form.is_valid():
        try:
            review_unregistered_verification_finding(actor=request.user, finding=finding, data=form.cleaned_data)
        except (PermissionDenied, ValidationError) as error:
            form.add_error(None, error)
        else:
            messages.success(request, "Finding review recorded.")
            return redirect("inventory:asset-verification-detail", pk=finding.verification_round_id)
    return render(request, "inventory/asset_verification_finding_review.html", {
        "finding": finding, "form": form, "events": finding.events.select_related("actor").all(),
    })


def _verification_reconciliation_data(verification_round, accounting_import):
    records = list(verification_round.records.all())
    register_by_tag = {}
    for record in records:
        tag = record.property_tag_snapshot.strip().casefold()
        if tag:
            register_by_tag.setdefault(tag, []).append(record)
    matched, accounting_only, ambiguous = [], [], []
    accounting_tags = set()
    if accounting_import:
        for line in accounting_import.lines.all():
            tag = line.property_tag.strip().casefold()
            accounting_tags.add(tag)
            candidates = register_by_tag.get(tag, []) if tag else []
            if len(candidates) == 1:
                record = candidates[0]
                differences = []
                if line.serial_number and record.serial_number_snapshot and line.serial_number.casefold() != record.serial_number_snapshot.casefold():
                    differences.append("Serial number differs")
                if line.department and record.assigned_department_snapshot and line.department.casefold() != record.assigned_department_snapshot.casefold():
                    differences.append("Department differs")
                if line.account_code and record.account_code_snapshot and line.account_code != record.account_code_snapshot:
                    differences.append("Account code differs")
                if line.acquisition_cost is not None and record.acquisition_cost_snapshot is not None and line.acquisition_cost != record.acquisition_cost_snapshot:
                    differences.append("Acquisition cost differs")
                if line.purchase_date and record.purchase_date_snapshot and line.purchase_date != record.purchase_date_snapshot:
                    differences.append("Purchase date differs")
                matched.append({"line": line, "record": record, "differences": differences})
            elif len(candidates) > 1:
                ambiguous.append(line)
            else:
                accounting_only.append(line)
    matched_records = {row["record"].pk for row in matched}
    register_only = [record for record in records if record.pk not in matched_records]
    return {
        "matched": matched, "accounting_only": accounting_only,
        "register_only": register_only, "ambiguous": ambiguous,
        "findings": verification_round.findings.select_related("related_asset", "recorded_by", "reviewed_by").all(),
    }


@asset_access_required("view")
def asset_verification_reconcile(request, pk):
    if not any(can_manage_asset_verification(request.user, action, read_only=True) for action in ("start", "record", "close", "import")):
        raise PermissionDenied
    verification_round = get_object_or_404(_verification_round_queryset(request.user), pk=pk)
    can_import = can_manage_asset_verification(request.user, "import")
    form = AssetAccountingImportForm(request.POST or None, request.FILES or None) if can_import else None
    if request.method == "POST":
        if not can_import:
            raise PermissionDenied
        if form.is_valid():
            try:
                import_accounting_asset_snapshot(
                    actor=request.user, verification_round=verification_round,
                    upload=form.cleaned_data["csv_file"],
                )
            except (PermissionDenied, ValidationError) as error:
                form.add_error("csv_file", error)
            except csv.Error as error:
                form.add_error("csv_file", f"The CSV file is malformed: {error}")
            else:
                messages.success(request, "Accounting snapshot imported. No GSO or Finance records were changed.")
                return redirect("inventory:asset-verification-reconcile", pk=verification_round.pk)
    accounting_import = verification_round.accounting_imports.prefetch_related("lines").first()
    comparison = _verification_reconciliation_data(verification_round, accounting_import)
    return render(request, "inventory/asset_verification_reconcile.html", {
        "verification_round": verification_round, "accounting_import": accounting_import,
        "comparison": comparison, "form": form, "can_import": can_import,
    })


@asset_access_required("view")
def asset_accounting_template(request):
    if not can_manage_asset_verification(request.user, "import", read_only=True):
        raise PermissionDenied
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="gso-accounting-asset-snapshot-template.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(("property_tag", "asset_name", "serial_number", "department", "account_code", "account_title", "purchase_date", "acquisition_cost"))
    return response


@asset_access_required("view")
def asset_accounting_source_download(request, pk):
    from django.http import Http404
    from .private_evidence import open_checked_private_file
    if not can_manage_asset_verification(request.user, "import", read_only=True):
        raise PermissionDenied
    snapshot = get_object_or_404(
        AssetAccountingImport.objects.select_related("verification_round").exclude(source_file=""), pk=pk,
    )
    if not _verification_round_queryset(request.user).filter(pk=snapshot.verification_round_id).exists():
        raise PermissionDenied
    try:
        source = open_checked_private_file(snapshot.source_file,
            namespace=f"inventory/reconciliation/{snapshot.verification_round_id}", sha256=snapshot.source_sha256)
    except (OSError, ValueError, ValidationError):
        raise Http404("The retained Accounting source is unavailable or requires integrity review.")
    response = FileResponse(
        source, as_attachment=True,
        content_type="text/csv", filename=snapshot.source_filename,
    )
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response


@asset_access_required("view")
def asset_verification_reconciliation_export(request, pk):
    if not any(can_manage_asset_verification(request.user, action, read_only=True) for action in ("start", "record", "close", "import")):
        raise PermissionDenied
    verification_round = get_object_or_404(_verification_round_queryset(request.user), pk=pk)
    accounting_import = verification_round.accounting_imports.first()
    comparison = _verification_reconciliation_data(verification_round, accounting_import)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="gso-verification-{verification_round.pk}-working-reconciliation.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow((
        "row_type", "as_of_date", "property_tag", "asset_name", "serial_number",
        "register_department", "register_office", "accounting_department", "account_code",
        "account_title", "purchase_date", "acquisition_cost", "physical_result",
        "observed_department", "observed_office", "condition", "differences", "notes",
    ))
    def write_row(values):
        writer.writerow(_csv_cell(value) for value in values)
    for row in comparison["matched"]:
        line, record = row["line"], row["record"]
        write_row(("matched", verification_round.as_of_date, record.property_tag_snapshot,
                         record.asset_name_snapshot, line.serial_number or record.serial_number_snapshot,
                         record.assigned_department_snapshot, record.assigned_office_snapshot,
                         line.department, line.account_code, line.account_title, line.purchase_date,
                         line.acquisition_cost, record.get_result_display(), record.observed_department,
                         record.observed_office, record.get_condition_display() if record.condition else "",
                         "; ".join(row["differences"]), record.notes))
    for record in comparison["register_only"]:
        write_row(("register_only", verification_round.as_of_date, record.property_tag_snapshot,
                         record.asset_name_snapshot, record.serial_number_snapshot,
                         record.assigned_department_snapshot, record.assigned_office_snapshot, "", "", "",
                         record.purchase_date_snapshot, record.acquisition_cost_snapshot,
                         record.get_result_display(), record.observed_department, record.observed_office,
                         record.get_condition_display() if record.condition else "", "No unique accounting tag match", record.notes))
    for line in comparison["accounting_only"]:
        write_row(("accounting_only", verification_round.as_of_date, line.property_tag,
                         line.asset_name, line.serial_number, "", "", line.department,
                         line.account_code, line.account_title, line.purchase_date,
                         line.acquisition_cost, "No GSO register match", "", "", "", "", ""))
    for line in comparison["ambiguous"]:
        write_row(("ambiguous_register_tag", verification_round.as_of_date, line.property_tag,
                         line.asset_name, line.serial_number, "", "", line.department,
                         line.account_code, line.account_title, line.purchase_date,
                         line.acquisition_cost, "Multiple GSO records share this tag", "", "", "", "", ""))
    for finding in comparison["findings"]:
        write_row(("found_but_unregistered", verification_round.as_of_date, finding.property_tag,
                         finding.asset_name, finding.serial_number, "", "", finding.found_department,
                         "", "", "", "", "Not in count snapshot", finding.found_department,
                         finding.found_office, finding.get_condition_display() if finding.condition else "",
                         finding.get_status_display(), finding.notes))
    return response


@never_cache
@require_http_methods(["GET", "HEAD"])
@asset_access_required("view")
def asset_verification_reconciliation_copy(request, pk):
    if not any(can_manage_asset_verification(request.user, action, read_only=True)
               for action in ("start", "record", "close", "import")):
        raise PermissionDenied
    verification_round = get_object_or_404(_verification_round_queryset(request.user), pk=pk)
    accounting_import = verification_round.accounting_imports.first()
    response = render(request, "inventory/asset_verification_working_copy.html", {
        "verification_round": verification_round,
        "accounting_import": accounting_import,
        "comparison": _verification_reconciliation_data(verification_round, accounting_import),
        "generated_at": timezone.now(),
    })
    response["X-Content-Type-Options"] = "nosniff"
    return response


def _disposal_queryset(user):
    cases = AssetDisposalCase.objects.select_related("asset", "submitted_by", "reviewed_by", "completed_by")
    if can_review_asset_disposal(user, read_only=True):
        if user.is_superuser:
            return cases
        gso = gso_department_for_user(user)
        return cases.filter(asset__department_id=gso.pk) if gso else cases.none()
    department = department_for_user(user)
    if not department:
        return cases.none()
    return cases.filter(asset__assigned_department_id=department.pk)


@asset_access_required("view")
def asset_disposal_list(request):
    if not (can_review_asset_disposal(request.user, read_only=True) or can_request_asset_disposal(request.user, read_only=True)):
        raise PermissionDenied
    return render(request, "inventory/asset_disposal_list.html", {
        "cases": _disposal_queryset(request.user),
        "can_review": can_review_asset_disposal(request.user),
    })


@asset_access_required("view")
def asset_disposal_request(request, pk):
    asset = get_object_or_404(_scoped_assets(request.user), pk=pk)
    if not can_request_asset_disposal(request.user, asset):
        raise PermissionDenied
    open_statuses = (
        AssetDisposalCase.SUBMITTED, AssetDisposalCase.UNDER_REVIEW,
        AssetDisposalCase.NEEDS_INFORMATION, AssetDisposalCase.AUTHORIZED,
    )
    if asset.disposal_cases.filter(status__in=open_statuses).exists():
        messages.info(request, "There is already an open disposal request for this asset.")
        return redirect("inventory:asset-detail", pk=asset.pk)
    form = AssetDisposalRequestForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        try:
            case = submit_asset_disposal_request(actor=request.user, asset=asset, data=form.cleaned_data)
        except (PermissionDenied, ValidationError) as error:
            form.add_error(None, error)
        else:
            messages.success(request, "Request sent to GSO with its photo and signed form.")
            return redirect("inventory:asset-disposal-detail", pk=case.pk)
    return render(request, "inventory/asset_disposal_request.html", {"form": form, "asset": asset})


@asset_access_required("view")
def asset_disposal_detail(request, pk):
    case = get_object_or_404(_disposal_queryset(request.user), pk=pk)
    reviewer = can_review_asset_disposal(request.user) and asset_in_scope(request.user, case.asset)
    requester = case.submitted_by_id == request.user.pk and can_request_asset_disposal(request.user, case.asset)
    review_form = AssetDisposalReviewForm(request.POST or None, request.FILES or None, case=case) if reviewer else None
    response_form = AssetDisposalResponseForm(request.POST or None, request.FILES or None) if requester and case.status == AssetDisposalCase.NEEDS_INFORMATION else None
    if request.method == "POST":
        if reviewer and review_form and review_form.is_valid():
            try:
                review_asset_disposal_case(actor=request.user, case=case, data=review_form.cleaned_data)
            except (PermissionDenied, ValidationError) as error:
                review_form.add_error(None, error)
            else:
                messages.success(request, "Disposal case updated and recorded in its history.")
                return redirect("inventory:asset-disposal-detail", pk=case.pk)
        elif response_form and response_form.is_valid():
            try:
                respond_to_disposal_case(actor=request.user, case=case, data=response_form.cleaned_data)
            except (PermissionDenied, ValidationError) as error:
                response_form.add_error(None, error)
            else:
                messages.success(request, "Your response was sent to GSO.")
                return redirect("inventory:asset-disposal-detail", pk=case.pk)
        elif not reviewer and not response_form:
            raise PermissionDenied
    return render(request, "inventory/asset_disposal_detail.html", {
        "case": case, "attachments": case.attachments.all(),
        "events": case.events.select_related("actor").all(),
        "reviewer": reviewer, "requester": requester,
        "review_form": review_form, "response_form": response_form,
    })


@asset_access_required("view")
def disposal_attachment_download(request, pk):
    attachment = get_object_or_404(
        AssetDisposalAttachment.objects.select_related("disposal_case__asset"), pk=pk,
    )
    case = attachment.disposal_case
    if not (asset_in_scope(request.user, case.asset)
            or (case.submitted_by_id == request.user.pk and has_inventory_permission(request.user, "request_asset_disposal"))):
        raise PermissionDenied
    from .disposal_evidence import open_checked_evidence
    try:
        source = open_checked_evidence(attachment, allow_legacy=True)
    except ValidationError as error:
        return HttpResponse(" ".join(error.messages), status=409, content_type="text/plain")
    response = FileResponse(
        source, as_attachment=True,
        content_type=attachment.content_type,
        filename=attachment.file.name.rsplit("/", 1)[-1],
    )
    response["X-Evidence-Integrity"] = "verified" if attachment.sha256 else "unknown-legacy"
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response


def _stock_items(user):
    items = ConsumableItem.objects.all()
    department = department_for_user(user)
    if user.is_superuser:
        return items
    if _is_gso_department(department):
        return items.filter(department_id=department.pk)
    if not department:
        raise PermissionDenied
    return items.filter(movements__department_id=department.pk, movements__kind=StockMovement.ISSUE).distinct()


def stock_access_required(action="view"):
    from functools import wraps
    from django.contrib.auth.views import redirect_to_login

    def decorate(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if not can_stock(request.user, action):
                raise PermissionDenied
            return view(request, *args, **kwargs)
        return wrapped
    return decorate


@stock_access_required()
def consumable_list(request):
    from .requisitions import can_act as can_requisition
    items = _stock_items(request.user).annotate(on_hand_value=Sum("movements__signed_quantity"))
    query = request.GET.get("q", "").strip()
    if query:
        items = items.filter(Q(name__icontains=query) | Q(category__icontains=query))
    for item in items:
        item.low_stock = item.is_active and item.minimum_stock > 0 and (item.on_hand_value or 0) <= item.minimum_stock
    return render(request, "inventory/consumable_list.html", {
        "items": items, "query": query,
        "is_gso": request.user.is_superuser or _is_gso_department(department_for_user(request.user)),
        "can_add": can_stock(request.user, "add"),
        "can_receive": can_stock(request.user, "receive"),
        "can_export": can_stock(request.user, "export"),
        "can_requisition": can_requisition(request.user, "view"),
    })


def _stock_history_selection(request):
    """One scoped selection for both paged review and complete CSV retrieval."""
    form = StockHistoryFilterForm(request.GET)
    movements = StockMovement.objects.filter(item__in=_stock_items(request.user))
    department = department_for_user(request.user)
    if not (request.user.is_superuser or _is_gso_department(department)):
        movements = movements.filter(department_id=department.pk)
    if not form.is_valid():
        return form, movements.none(), ""
    data = form.cleaned_data
    if data.get("from_date"):
        movements = movements.filter(occurred_at__date__gte=data["from_date"])
    if data.get("to_date"):
        movements = movements.filter(occurred_at__date__lte=data["to_date"])
    if data.get("kind"):
        movements = movements.filter(kind=data["kind"])
    query = urlencode({key: value for key, value in data.items() if value})
    return form, movements.select_related("item", "actor"), query


@never_cache
@stock_access_required()
@require_http_methods(["GET"])
def stock_history(request):
    form, movements, query = _stock_history_selection(request)
    page = Paginator(movements.order_by("-occurred_at", "-pk"), 50).get_page(request.GET.get("page"))
    response = render(request, "inventory/stock_history.html", {
        "form": form, "page": page, "query_string": query,
        "can_export": can_stock(request.user, "export"),
    }, status=200 if form.is_valid() else 400)
    response["X-Content-Type-Options"] = "nosniff"
    return response


@never_cache
@stock_access_required("export")
@require_http_methods(["GET"])
def stock_export(request):
    form, movements, _ = _stock_history_selection(request)
    if not form.is_valid():
        return HttpResponse("Invalid movement filters. Check the dates and movement type in Movement history.",
                            status=400, content_type="text/plain")
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="gso-consumable-movements.csv"'
    response["X-Content-Type-Options"] = "nosniff"
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow((
        "Supply item", "Category", "Unit", "Movement", "Date", "Quantity", "Signed quantity",
        "Department", "Recipient", "Reference", "Reason", "Unit cost", "Recorded by", "Supply UUID", "Movement UUID",
    ))
    for movement in movements.order_by("occurred_at", "pk").iterator():
        writer.writerow(_csv_cell(value) for value in (
            movement.item.name, movement.item.category, movement.item.unit, movement.get_kind_display(),
            movement.occurred_at.isoformat(), movement.quantity, movement.signed_quantity,
            movement.department_label, movement.recipient, movement.reference, movement.reason,
            movement.unit_cost if movement.unit_cost is not None else "", movement.actor or "", str(movement.item.public_id), str(movement.public_id),
        ))
    return response


@never_cache
@stock_access_required("export")
@require_http_methods(["GET"])
def stock_working_copy(request):
    form, movements, query = _stock_history_selection(request)
    if not form.is_valid():
        return HttpResponse("Invalid movement filters. Check the dates and movement type in Movement history.",
                            status=400, content_type="text/plain")
    rows = list(movements.order_by("occurred_at", "pk"))
    response = render(request, "inventory/stock_working_copy.html", {
        "movements": rows, "selection": form.cleaned_data, "query_string": query,
        "can_view_history": can_stock(request.user, "view"),
        "generated_at": timezone.now(), "movement_label": dict(StockMovement.KIND_CHOICES).get(form.cleaned_data.get("kind"), "All movements"),
    })
    response["X-Content-Type-Options"] = "nosniff"
    return response


@stock_access_required("add")
def consumable_create(request):
    form = ConsumableItemForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        item = create_consumable(actor=request.user, data=form.cleaned_data)
        messages.success(request, "Supply item added. You can now record stock received.")
        return redirect("inventory:consumable-detail", pk=item.pk)
    return render(request, "inventory/consumable_form.html", {"form": form, "heading": "Add a supply item"})


@stock_access_required("change")
def consumable_edit(request, pk):
    item = get_object_or_404(_stock_items(request.user), pk=pk)
    form = ConsumableItemForm(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid():
        try:
            item = update_consumable(actor=request.user, item=item, data=form.cleaned_data)
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, "Supply item details updated and recorded in its history.")
            return redirect("inventory:consumable-detail", pk=item.pk)
    return render(request, "inventory/consumable_form.html", {"form": form, "item": item, "heading": "Edit supply item"})


@stock_access_required()
def consumable_detail(request, pk):
    from .stock_counts import can_manage_count
    from .supply_returns import can_act as can_return
    item = get_object_or_404(_stock_items(request.user), pk=pk)
    movements = item.movements.all()
    department = department_for_user(request.user)
    is_gso = request.user.is_superuser or _is_gso_department(department)
    if not is_gso:
        movements = movements.filter(department_id=department.pk)
    page = Paginator(movements.select_related("actor"), 50).get_page(request.GET.get("page"))
    audit_events = item.audit_events.all() if is_gso and has_inventory_permission(request.user, "view_stock_audit") else ()
    return render(request, "inventory/consumable_detail.html", {
        "item": item, "page": page, "is_gso": is_gso, "audit_events": audit_events,
        "can_record_count": can_manage_count(request.user, "record", item) and item.is_active,
        "can_record_return": can_return(request.user, "record"),
        "can_view_returns": can_return(request.user, "view"),
        "can_receive": can_stock(request.user, "receive"),
        "can_issue": can_stock(request.user, "issue"),
        "can_adjust": can_stock(request.user, "adjust"),
        "can_change": can_stock(request.user, "change"),
    })


STOCK_REQUEST_SALT = "gso-stock-movement-request-v1"


def _stock_request_form(request, item, action, form_type):
    token = signing.dumps({"actor": request.user.pk, "item": str(item.public_id),
        "action": action, "request": str(uuid4())}, salt=STOCK_REQUEST_SALT)
    return form_type(request.POST if request.method == "POST" else None, initial={"request_token": token})


def _stock_request_id(request, item, action, token):
    try:
        payload = signing.loads(token, salt=STOCK_REQUEST_SALT, max_age=1800)
    except signing.BadSignature:
        raise ValidationError("This movement form expired or changed. Check movement history, then reopen the form if needed.")
    if payload.get("actor") != request.user.pk or payload.get("item") != str(item.public_id) or payload.get("action") != action:
        raise PermissionDenied
    return payload["request"]


@never_cache
@require_http_methods(["GET", "POST"])
@stock_access_required("receive")
def stock_receive(request, pk):
    item = get_object_or_404(_stock_items(request.user), pk=pk)
    form = _stock_request_form(request, item, "receive", StockReceiptForm)
    if request.method == "POST" and form.is_valid():
        try:
            data = dict(form.cleaned_data)
            identity = _stock_request_id(request, item, "receive", data.pop("request_token"))
            record_stock_movement(
                actor=request.user, item=item, kind=StockMovement.RECEIPT, request_id=identity, **data,
            )
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, "Stock receipt recorded.")
            return redirect("inventory:consumable-detail", pk=item.pk)
    return render(request, "inventory/stock_movement_form.html", {"form": form, "item": item, "heading": "Record received stock"})


@never_cache
@require_http_methods(["GET", "POST"])
@stock_access_required("issue")
def stock_issue(request, pk):
    item = get_object_or_404(_stock_items(request.user), pk=pk)
    form = _stock_request_form(request, item, "issue", StockIssueForm)
    if request.method == "POST" and form.is_valid():
        data = dict(form.cleaned_data)
        department = _resolve_department(data.pop("department"))
        try:
            identity = _stock_request_id(request, item, "issue", data.pop("request_token"))
            record_stock_movement(
                actor=request.user, item=item, kind=StockMovement.ISSUE,
                department_id=department.pk, department_label=department.name, request_id=identity, **data,
            )
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, "Supply issue recorded.")
            return redirect("inventory:consumable-detail", pk=item.pk)
    return render(request, "inventory/stock_movement_form.html", {"form": form, "item": item, "heading": "Issue supplies"})


@never_cache
@require_http_methods(["GET", "POST"])
@stock_access_required("adjust")
def stock_adjust(request, pk):
    item = get_object_or_404(_stock_items(request.user), pk=pk)
    form = _stock_request_form(request, item, "adjust", StockAdjustmentForm)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        kind = StockMovement.ADJUSTMENT_IN if data["direction"] == "in" else StockMovement.ADJUSTMENT_OUT
        try:
            identity = _stock_request_id(request, item, "adjust", data["request_token"])
            record_stock_movement(
                actor=request.user, item=item, kind=kind, quantity=data["quantity"], reason=data["reason"],
                request_id=identity,
            )
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, "Stock adjustment recorded with its reason.")
            return redirect("inventory:consumable-detail", pk=item.pk)
    return render(request, "inventory/stock_movement_form.html", {"form": form, "item": item, "heading": "Adjust stock balance"})


def _resolve_department(pk):
    model = department_model()
    department = model.objects.filter(pk=pk).first() if model else None
    if department is None:
        raise PermissionDenied("The selected department is no longer available.")
    return department
