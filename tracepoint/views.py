from __future__ import annotations

import secrets

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST
from django_ratelimit.decorators import ratelimit

from .access import (
    can_complete_packets,
    can_prepare_packets,
    can_print_labels,
    can_resolve_exceptions,
    can_view_restricted,
    can_view_workspace,
    department_for_user,
    is_eligible_employee,
    packet_is_visible,
)
from .controls import (
    PacketControlError,
    cancel_packet,
    complete_packet,
    correct_current_custody,
    hold_packet,
    report_discrepancy,
    resolve_discrepancy,
    resume_packet,
)
from .credentials import CredentialError, issue_daily_credential, resolve_daily_credential, revoke_daily_credential
from .forms import DiscrepancyForm, EmployeeCodeScanForm, TrackedPacketForm
from .handoffs import HandoffError, attach_recipient_code, confirm_handoff, start_scan_session
from .models import DailyEmployeeCredential, PacketDiscrepancy, PacketScanSession, TrackedPacket
from .qr import QRPayloadError, employee_qr_payload, extract_employee_token, packet_qr_payload, render_qr_png
from .services import PacketWorkflowError, create_packet


def _require_employee(user):
    if not is_eligible_employee(user):
        raise PermissionDenied


def _visible_packets(user):
    department = department_for_user(user)
    if not department:
        return TrackedPacket.objects.none()
    direct = Q(prepared_by=user) | Q(current_holder=user) | Q(final_destination_employee=user) | Q(handoffs__confirmed_by=user)
    scope = direct
    if can_view_workspace(user, department):
        scope |= Q(origin_department=department) | Q(current_department=department) | Q(final_destination_department=department)
    queryset = TrackedPacket.objects.filter(scope).select_related(
        "origin_department", "prepared_by", "final_destination_department", "final_destination_employee",
        "current_holder", "current_department", "department_record", "report_run__definition",
    ).distinct()
    if not can_view_restricted(user, department):
        queryset = queryset.filter(Q(confidentiality=TrackedPacket.INTERNAL) | direct)
    return queryset


def _packet(user, public_id):
    packet = get_object_or_404(TrackedPacket.objects.select_related(
        "origin_department", "prepared_by", "final_destination_department", "final_destination_employee",
        "current_holder", "current_department", "completed_by", "department_record", "report_run__definition",
    ), public_id=public_id)
    if not packet_is_visible(user, packet):
        raise Http404
    return packet


def _can_resolve(user, packet):
    department = department_for_user(user)
    return bool(
        department
        and department.pk in {
            packet.origin_department_id, packet.current_department_id, packet.final_destination_department_id,
        }
        and can_resolve_exceptions(user, department)
    )


@login_required
def workspace(request):
    _require_employee(request.user)
    if not can_view_workspace(request.user):
        raise PermissionDenied
    packets = _visible_packets(request.user)
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    if query:
        packets = packets.filter(Q(tracking_number__icontains=query) | Q(title__icontains=query) | Q(contents_manifest__icontains=query))
    if status in dict(TrackedPacket.STATUS_CHOICES):
        packets = packets.filter(status=status)
    all_packets = _visible_packets(request.user)
    return render(request, "tracepoint/workspace.html", {
        "packets": packets[:100], "query": query, "selected_status": status,
        "status_choices": TrackedPacket.STATUS_CHOICES,
        "draft_count": all_packets.filter(status=TrackedPacket.DRAFT).count(),
        "active_count": all_packets.filter(status__in=(TrackedPacket.ACTIVE, TrackedPacket.ON_HOLD)).count(),
        "delivered_count": all_packets.filter(status=TrackedPacket.DELIVERED).count(),
        "issue_count": PacketDiscrepancy.objects.filter(packet__in=all_packets, status=PacketDiscrepancy.OPEN).count(),
        "can_prepare": can_prepare_packets(request.user),
    })


@login_required
@require_http_methods(["GET", "POST"])
def packet_create(request):
    _require_employee(request.user)
    department = department_for_user(request.user)
    if not can_prepare_packets(request.user, department):
        raise PermissionDenied
    form = TrackedPacketForm(request.POST or None, origin_department=department)
    if request.method == "POST" and form.is_valid():
        try:
            packet = create_packet(
                actor=request.user,
                title=form.cleaned_data["title"],
                contents_manifest=form.cleaned_data["contents_manifest"],
                expected_document_count=form.cleaned_data["expected_document_count"],
                expected_page_count=form.cleaned_data["expected_page_count"],
                confidentiality=form.cleaned_data["confidentiality"],
                final_destination_department=form.cleaned_data["final_destination_department"],
                final_destination_employee=form.cleaned_data["final_destination_employee"],
                department_record=form.cleaned_data["department_record"],
                report_run=form.cleaned_data["report_run"],
            )
        except (PacketWorkflowError, ValidationError) as error:
            form.add_error(None, error)
        else:
            messages.success(request, f"Packet {packet.tracking_number} is ready for its label and preparer activation.")
            return redirect(packet)
    return render(request, "tracepoint/packet_form.html", {"form": form})


@login_required
def packet_detail(request, public_id):
    packet = _packet(request.user, public_id)
    can_resolve = _can_resolve(request.user, packet)
    department = department_for_user(request.user)
    correction_employees = get_user_model().objects.none()
    if can_resolve:
        correction_employees = get_user_model().objects.filter(
            is_active=True, employeeprofile__assigned_department__isnull=False,
        ).select_related("employeeprofile__assigned_department").order_by(
            "employeeprofile__assigned_department__name", "last_name", "first_name", "username",
        )
    return render(request, "tracepoint/packet_detail.html", {
        "packet": packet,
        "handoffs": packet.handoffs.select_related("from_holder", "to_holder", "from_department", "to_department"),
        "events": packet.events.select_related("actor")[:100],
        "discrepancies": packet.discrepancies.select_related("reported_by", "resolved_by", "related_handoff"),
        "corrections": packet.corrections.select_related("prior_holder", "corrected_holder", "created_by", "related_handoff"),
        "discrepancy_form": DiscrepancyForm(),
        "can_print": can_print_labels(request.user, packet.origin_department),
        "can_complete": packet.status == TrackedPacket.DELIVERED and can_complete_packets(request.user, packet.final_destination_department),
        "can_hold": packet.status == TrackedPacket.ACTIVE and (packet.current_holder_id == request.user.pk or can_resolve),
        "can_resume": packet.status == TrackedPacket.ON_HOLD and (packet.current_holder_id == request.user.pk or can_resolve),
        "can_cancel": packet.status in (TrackedPacket.DRAFT, TrackedPacket.ACTIVE, TrackedPacket.ON_HOLD) and (packet.prepared_by_id == request.user.pk or can_resolve),
        "can_resolve": can_resolve,
        "correction_employees": correction_employees,
        "department": department,
    })


@login_required
def packet_label(request, public_id):
    packet = _packet(request.user, public_id)
    if not can_print_labels(request.user, packet.origin_department):
        raise PermissionDenied
    return render(request, "tracepoint/packet_label.html", {"packet": packet})


@login_required
def packet_label_qr(request, public_id):
    packet = _packet(request.user, public_id)
    if not can_print_labels(request.user, packet.origin_department):
        raise PermissionDenied
    payload = packet_qr_payload(packet, base_url=request.build_absolute_uri("/"))
    return HttpResponse(render_qr_png(payload), content_type="image/png")


@login_required
@require_http_methods(["GET", "POST"])
def daily_code(request):
    _require_employee(request.user)
    token = request.session.get("tracepoint_daily_token", "")
    credential = None
    if token:
        try:
            credential = resolve_daily_credential(token)
            if credential.employee_id != request.user.pk:
                raise CredentialError("Code belongs to another employee.")
        except CredentialError:
            request.session.pop("tracepoint_daily_token", None)
            token = ""
            credential = None
    active_exists = DailyEmployeeCredential.objects.filter(
        employee=request.user, valid_on=timezone.localdate(), revoked_at__isnull=True,
    ).order_by("-valid_on").first()
    if request.method == "POST":
        try:
            issued = issue_daily_credential(
                employee=request.user,
                actor=request.user,
                replace=bool(active_exists),
                replacement_reason="Employee generated a new daily display code.",
            )
        except CredentialError as error:
            messages.error(request, str(error))
        else:
            request.session["tracepoint_daily_token"] = issued.token
            messages.success(request, "Your daily employee code is ready. Any earlier code for today is now invalid.")
        return redirect("tracepoint:daily_code")
    return render(request, "tracepoint/daily_code.html", {"credential": credential, "has_unrecoverable_active": bool(active_exists and not credential)})


@login_required
def daily_code_image(request):
    _require_employee(request.user)
    token = request.session.get("tracepoint_daily_token", "")
    try:
        credential = resolve_daily_credential(token)
    except CredentialError as error:
        raise Http404 from error
    if credential.employee_id != request.user.pk:
        raise Http404
    payload = employee_qr_payload(token, base_url=request.build_absolute_uri("/"))
    return HttpResponse(render_qr_png(payload), content_type="image/png")


@login_required
@require_POST
def daily_code_revoke(request):
    _require_employee(request.user)
    credential = DailyEmployeeCredential.objects.filter(
        employee=request.user, revoked_at__isnull=True,
    ).order_by("-valid_on", "-issued_at").first()
    if credential:
        revoke_daily_credential(credential=credential, actor=request.user, reason="Employee revoked their displayed daily code.")
    request.session.pop("tracepoint_daily_token", None)
    messages.success(request, "Your displayed employee code has been revoked.")
    return redirect("tracepoint:daily_code")


@login_required
@require_http_methods(["GET", "POST"])
def packet_scan(request, public_id):
    _require_employee(request.user)
    packet = get_object_or_404(TrackedPacket.objects.select_related(
        "origin_department", "final_destination_department", "final_destination_employee", "current_holder",
    ), public_id=public_id)
    if request.method == "POST":
        try:
            session = start_scan_session(
                packet=packet, operator=request.user, idempotency_key=secrets.token_urlsafe(32)[:64],
            )
        except HandoffError as error:
            messages.error(request, str(error))
        else:
            request.session["tracepoint_scan_session"] = str(session.public_id)
            return redirect("tracepoint:scan_session", public_id=session.public_id)
    return render(request, "tracepoint/scan_start.html", {"packet": packet, "can_see_details": packet_is_visible(request.user, packet)})


def _owned_scan_session(user, public_id):
    return get_object_or_404(PacketScanSession.objects.select_related(
        "packet__origin_department", "packet__final_destination_department", "packet__final_destination_employee",
        "packet__current_holder", "recipient",
    ), public_id=public_id, initiated_by=user)


@login_required
@require_http_methods(["GET", "POST"])
def scan_session(request, public_id):
    _require_employee(request.user)
    session = _owned_scan_session(request.user, public_id)
    form = EmployeeCodeScanForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            token = extract_employee_token(form.cleaned_data["employee_code"])
            attach_recipient_code(session=session, operator=request.user, token=token)
        except (HandoffError, QRPayloadError) as error:
            form.add_error("employee_code", error)
        else:
            return redirect("tracepoint:scan_session", public_id=session.public_id)
    session.refresh_from_db()
    return render(request, "tracepoint/scan_session.html", {"scan": session, "form": form})


@login_required
@ratelimit(key="ip", rate="30/m", block=True)
def employee_scan(request, token):
    _require_employee(request.user)
    session_id = request.session.get("tracepoint_scan_session")
    if not session_id:
        messages.error(request, "Scan a packet label at this station before scanning an employee code.")
        return redirect("tracepoint:workspace")
    session = _owned_scan_session(request.user, session_id)
    try:
        attach_recipient_code(session=session, operator=request.user, token=extract_employee_token(token))
    except (HandoffError, QRPayloadError) as error:
        messages.error(request, str(error))
    return redirect("tracepoint:scan_session", public_id=session.public_id)


@login_required
@require_POST
def scan_confirm(request, public_id):
    _require_employee(request.user)
    session = _owned_scan_session(request.user, public_id)
    try:
        handoff = confirm_handoff(session=session, operator=request.user, receipt_note=request.POST.get("receipt_note", ""))
    except HandoffError as error:
        messages.error(request, str(error))
        return redirect("tracepoint:scan_session", public_id=session.public_id)
    request.session.pop("tracepoint_scan_session", None)
    messages.success(request, f"Receipt recorded. {handoff.to_employee_name} is now responsible for {handoff.packet.tracking_number}.")
    return redirect(handoff.packet)


@login_required
@require_POST
def packet_action(request, public_id, action):
    packet = _packet(request.user, public_id)
    try:
        if action == "complete":
            complete_packet(packet=packet, actor=request.user, note=request.POST.get("note", ""))
        elif action == "hold":
            hold_packet(packet=packet, actor=request.user, reason=request.POST.get("reason", ""))
        elif action == "resume":
            resume_packet(packet=packet, actor=request.user, note=request.POST.get("note", ""))
        elif action == "cancel":
            cancel_packet(packet=packet, actor=request.user, reason=request.POST.get("reason", ""))
        else:
            raise Http404
    except PacketControlError as error:
        messages.error(request, str(error))
    else:
        messages.success(request, "TracePoint status updated with an audit entry.")
    return redirect(packet)


@login_required
@require_POST
def discrepancy_report(request, public_id):
    packet = _packet(request.user, public_id)
    form = DiscrepancyForm(request.POST)
    if form.is_valid():
        related = packet.handoffs.filter(pk=form.cleaned_data.get("related_handoff")).first()
        try:
            report_discrepancy(
                packet=packet, actor=request.user, category=form.cleaned_data["category"],
                description=form.cleaned_data["description"], related_handoff=related,
            )
        except (PacketControlError, ValidationError) as error:
            messages.error(request, str(error))
        else:
            messages.success(request, "The discrepancy was recorded without changing the custody receipt.")
    else:
        messages.error(request, "Choose an issue type and describe what was observed.")
    return redirect(packet)


@login_required
@require_POST
def discrepancy_resolve(request, public_id, discrepancy_id):
    packet = _packet(request.user, public_id)
    discrepancy = get_object_or_404(packet.discrepancies, pk=discrepancy_id)
    try:
        resolve_discrepancy(discrepancy=discrepancy, actor=request.user, resolution=request.POST.get("resolution", ""))
    except PacketControlError as error:
        messages.error(request, str(error))
    else:
        messages.success(request, "The discrepancy resolution is now part of the audit history.")
    return redirect(packet)


@login_required
@require_POST
def custody_correct(request, public_id):
    packet = _packet(request.user, public_id)
    corrected_holder = get_object_or_404(get_user_model(), pk=request.POST.get("corrected_holder"), is_active=True)
    related = packet.handoffs.filter(pk=request.POST.get("related_handoff")).first()
    try:
        correct_current_custody(
            packet=packet, actor=request.user, corrected_holder=corrected_holder,
            reason=request.POST.get("reason", ""), related_handoff=related,
        )
    except (PacketControlError, ValidationError) as error:
        messages.error(request, str(error))
    else:
        messages.success(request, "Current custody was corrected; the original receipt remains unchanged.")
    return redirect(packet)
