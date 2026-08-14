from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from django_ratelimit.decorators import ratelimit
from telegram import Bot

from assistance.decorators import mswd_required
from assistance.access import (
    can_review_citizen_profiles,
    can_view_citizen_pii,
    citizen_review_access_required,
)
from assistance.forms import CitizenReviewForm
from assistance.models import (
    AssistanceRequest,
    AssistanceType,
    CitizenProfile,
    CitizenReviewLog,
    RequestDocument,
    RequestLog,
)
from assistance.services.citizen_service import CitizenReviewQueryService
from assistance.services.notifications import AssistanceNotificationService


def _active_types():
    type_ids = (
        AssistanceRequest.objects.filter(is_active=True)
        .values_list("assistance_type_id", flat=True)
        .distinct()
    )
    return AssistanceType.objects.filter(id__in=type_ids, is_active=True)


@citizen_review_access_required
def citizen_profile_list_view(request):
    search = request.GET.get("q", "").strip()
    review_status = request.GET.get("review_status", "").strip()
    sort = request.GET.get("sort", "recent").strip()
    allow_pii = can_view_citizen_pii(request.user)
    profiles = CitizenReviewQueryService.profiles(
        search=search,
        review_status=review_status,
        sort=sort,
        allow_pii=allow_pii,
    )
    page = Paginator(profiles, 25).get_page(request.GET.get("page"))
    duplicate_ids = CitizenReviewQueryService.duplicate_profile_ids()
    for profile in page.object_list:
        profile.has_duplicate_identifiers = profile.pk in duplicate_ids
        if not allow_pii:
            CitizenReviewQueryService.mask(profile)

    summary = CitizenProfile.objects.aggregate(
        total=Count("pk"),
        unreviewed=Count("pk", filter=Q(review_status="unreviewed")),
        in_review=Count("pk", filter=Q(review_status="in_review")),
        verified=Count("pk", filter=Q(review_status="verified")),
    )
    return render(
        request,
        "assistance/mswd/citizen_profiles.html",
        {
            "page_obj": page,
            "summary": summary,
            "search": search if allow_pii else "",
            "selected_review_status": review_status,
            "selected_sort": sort,
            "review_status_choices": CitizenProfile.REVIEW_STATUS_CHOICES,
            "can_view_pii": allow_pii,
            "can_review_profiles": can_review_citizen_profiles(request.user),
        },
    )


@citizen_review_access_required
def citizen_profile_detail_view(request, profile_id):
    allow_pii = can_view_citizen_pii(request.user)
    may_review = can_review_citizen_profiles(request.user)
    profile = get_object_or_404(
        CitizenProfile.objects.select_related("assigned_reviewer", "reviewed_by"),
        pk=profile_id,
    )

    if request.method == "POST":
        if not may_review:
            raise PermissionDenied
        with transaction.atomic():
            profile = CitizenProfile.objects.select_for_update().get(pk=profile.pk)
            old_status = profile.review_status
            old_reviewer = profile.assigned_reviewer
            old_notes = profile.review_notes
            form = CitizenReviewForm(request.POST, instance=profile)
            if form.is_valid():
                updated = form.save(commit=False)
                now = timezone.now()
                has_changes = bool(
                    old_status != updated.review_status
                    or old_reviewer != updated.assigned_reviewer
                    or old_notes != updated.review_notes
                )
                if not has_changes:
                    messages.info(request, "No review changes were detected.")
                    return redirect("assistance:citizen_profile_detail", profile_id=profile.pk)
                if updated.review_status != "unreviewed" and not updated.review_started_at:
                    updated.review_started_at = now
                if updated.review_status in ("verified", "needs_update"):
                    if not updated.assigned_reviewer:
                        updated.assigned_reviewer = request.user
                    updated.reviewed_by = request.user
                    updated.reviewed_at = now
                elif updated.review_status == "in_review":
                    updated.reviewed_by = None
                    updated.reviewed_at = None
                elif updated.review_status == "unreviewed":
                    updated.reviewed_by = None
                    updated.reviewed_at = None
                    updated.review_started_at = None
                updated.save()
                change_note = "Review record updated."
                if old_notes != updated.review_notes:
                    change_note = updated.review_notes or "Review notes cleared."
                CitizenReviewLog.objects.create(
                    profile=updated,
                    actor=request.user,
                    previous_status=old_status,
                    new_status=updated.review_status,
                    previous_reviewer=old_reviewer,
                    new_reviewer=updated.assigned_reviewer,
                    note=change_note,
                )
                messages.success(request, "Citizen review saved with an audit entry.")
                return redirect("assistance:citizen_profile_detail", profile_id=profile.pk)
    else:
        form = CitizenReviewForm(instance=profile) if may_review else None

    requests = profile.requests.select_related("assistance_type").order_by("-submitted_at")
    request_summary = requests.aggregate(
        total=Count("pk"),
        active=Count("pk", filter=Q(is_active=True)),
        awaiting=Count("pk", filter=Q(is_active=True, status__in=("submitted", "pending"))),
        under_review=Count("pk", filter=Q(is_active=True, status="review")),
    )
    status_labels = dict(AssistanceRequest.STATUS_CHOICES)
    status_breakdown = list(
        requests.values("status").annotate(total=Count("pk")).order_by("status")
    )
    for row in status_breakdown:
        row["label"] = status_labels.get(row["status"], row["status"].replace("_", " ").title())
    type_breakdown = (
        requests.values("assistance_type__name")
        .annotate(total=Count("pk"))
        .order_by("-total", "assistance_type__name")
    )
    frequency = (
        requests.values("submitted_at__year", "submitted_at__month")
        .annotate(total=Count("pk"))
        .order_by("-submitted_at__year", "-submitted_at__month")[:12]
    )
    identity_variants = []
    if allow_pii:
        identity_variants = list(
            requests.values("full_name", "email", "phone")
            .annotate(total=Count("pk"))
            .order_by("-total", "full_name")
        )
    duplicates = CitizenProfile.objects.none()
    if profile.normalized_email or profile.normalized_phone:
        duplicate_filter = Q()
        if profile.normalized_email:
            duplicate_filter |= Q(normalized_email=profile.normalized_email)
        if profile.normalized_phone:
            duplicate_filter |= Q(normalized_phone=profile.normalized_phone)
        duplicates = CitizenProfile.objects.filter(duplicate_filter).exclude(pk=profile.pk).order_by("full_name")

    if not allow_pii:
        CitizenReviewQueryService.mask(profile)
        duplicates = [CitizenReviewQueryService.mask(candidate) for candidate in duplicates]

    return render(
        request,
        "assistance/mswd/citizen_profile_detail.html",
        {
            "profile": profile,
            "review_form": form,
            "requests": requests,
            "request_summary": request_summary,
            "status_breakdown": status_breakdown,
            "type_breakdown": type_breakdown,
            "frequency": frequency,
            "identity_variants": identity_variants,
            "duplicate_profiles": duplicates,
            "review_logs": profile.review_logs.select_related(
                "actor", "previous_reviewer", "new_reviewer"
            ),
            "can_view_pii": allow_pii,
            "can_review_profiles": may_review,
        },
    )


@login_required
@mswd_required
def mswd_dashboard_view(request):
    status_filter = request.GET.get("status", "")
    type_filter = request.GET.get("type", "")

    requests = AssistanceRequest.objects.filter(is_active=True).order_by("-submitted_at").select_related(
        "assistance_type", "citizen"
    ).prefetch_related(
        Prefetch(
            "documents",
            queryset=RequestDocument.objects.filter(is_removed=False).order_by("uploaded_at"),
            to_attr="active_documents",
        )
    )
    if status_filter:
        requests = requests.filter(status=status_filter)
    if type_filter:
        requests = requests.filter(assistance_type__id=type_filter)

    return render(
        request,
        "assistance/mswd/dashboard.html",
        {
            "requests": requests,
            "types": _active_types(),
            "selected_status": status_filter,
            "selected_type": type_filter,
        },
    )


@login_required
@mswd_required
def mswd_request_detail_view(request, ref_code):
    assistance_request = get_object_or_404(
        AssistanceRequest.objects.select_related("citizen", "assistance_type"),
        reference_code=ref_code,
        is_active=True,
    )
    documents = assistance_request.documents.filter(is_removed=False).order_by("uploaded_at")
    allowed_statuses = {status for status, _ in AssistanceRequest.STATUS_CHOICES}

    if request.method == "POST":
        old_status = assistance_request.status
        new_status = request.POST.get("status", "").strip()
        if new_status and new_status not in allowed_statuses:
            messages.error(request, "Invalid status.")
            return redirect("assistance:mswd_request_detail", ref_code=ref_code)

        remarks = request.POST.get("remarks", "")

        status_changed = new_status and new_status != old_status
        remarks_changed = remarks != (assistance_request.remarks or "")

        if status_changed or remarks_changed:
            if status_changed:
                assistance_request.status = new_status
            if remarks_changed:
                assistance_request.remarks = remarks
            update_fields = ["remarks"]
            if status_changed:
                update_fields.append("status")
            assistance_request.save(update_fields=update_fields)

            if status_changed and remarks_changed:
                action = "manual_edit"
            elif status_changed:
                action = "status_change"
            else:
                action = "remarks_updated"

            RequestLog.objects.create(
                request=assistance_request,
                updated_by=request.user,
                action_type=action,
                status_before=old_status if status_changed else old_status,
                status_after=assistance_request.status if status_changed else old_status,
                remarks=remarks if remarks_changed else "",
            )

            AssistanceNotificationService.send_status_update_email(request_obj=assistance_request)

            if assistance_request.telegram_chat_id:
                msg = (
                    "*Your assistance request has been updated!*\n\n"
                    f"• Status: *{assistance_request.get_status_display()}*\n"
                    f"• Remarks: _{remarks or 'None'}_\n\n"
                    f"• Reference Code: `{assistance_request.reference_code}`"
                )
                send_telegram_update(assistance_request.telegram_chat_id, msg)

            messages.success(request, "Status and remarks updated. Email sent to requester.")

        return redirect("assistance:mswd_request_detail", ref_code=ref_code)

    return render(
        request,
        "assistance/mswd/request_detail.html",
        {
            "request_obj": assistance_request,
            "documents": documents,
            "logs": assistance_request.logs.select_related("updated_by").order_by("-timestamp"),
        },
    )


@require_POST
@login_required
@mswd_required
@ratelimit(key="ip", method="POST", rate="20/m", block=True)
def mswd_update_document_ajax(request, doc_id):
    allowed_status = {status for status, _ in RequestDocument.REQUEST_STATUS_CHOICES}
    try:
        document = RequestDocument.objects.get(pk=doc_id)
        new_status = request.POST.get("status", "").strip()
        if new_status not in allowed_status:
            return JsonResponse({"success": False, "error": "Invalid status."}, status=400)

        new_remarks = request.POST.get("remarks", "")

        document.status = new_status
        document.remarks = new_remarks
        document.save(update_fields=["status", "remarks"])

        send_mail(
            subject="Update on your uploaded document",
            message=(
                "One of your uploaded files has been reviewed.\n\n"
                f"Status: {document.get_status_display()}\n"
                f"Remarks: {new_remarks or 'None'}\n\n"
                f"Reference: {document.request.reference_code}"
            ),
            from_email=getattr(settings, "NOTIFICATIONS_FROM_EMAIL", None),
            recipient_list=[document.request.email],
            fail_silently=True,
        )

        if document.request.telegram_chat_id:
            msg = (
                "*Your uploaded document has been reviewed!*\n\n"
                f"• Status: *{document.get_status_display()}*\n"
                f"• Remarks: _{new_remarks or 'None'}_\n\n"
                f"• Reference Code: `{document.request.reference_code}`"
            )
            send_telegram_update(document.request.telegram_chat_id, msg)

        return JsonResponse({"success": True})
    except Exception as exc:
        return JsonResponse({"success": False, "error": str(exc)})


@login_required
@mswd_required
def mswd_printable_view(request, ref_code):
    assistance_request = get_object_or_404(AssistanceRequest, reference_code=ref_code, is_active=True)
    documents = assistance_request.documents.filter(is_removed=False).order_by("uploaded_at")
    return render(
        request,
        "assistance/mswd/printable_request.html",
        {
            "request_obj": assistance_request,
            "documents": documents,
        },
    )


def send_telegram_update(chat_id, message):
    if not chat_id or not message:
        return

    try:
        bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        bot.send_message(chat_id=chat_id, text=message, parse_mode="Markdown")
    except Exception:
        return
