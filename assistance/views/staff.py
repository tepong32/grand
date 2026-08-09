from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from django_ratelimit.decorators import ratelimit
from telegram import Bot

from assistance.decorators import mswd_required
from assistance.models import AssistanceRequest, AssistanceType, RequestDocument, RequestLog
from assistance.services.notifications import AssistanceNotificationService


def _active_types():
    type_ids = (
        AssistanceRequest.objects.filter(is_active=True)
        .values_list("assistance_type_id", flat=True)
        .distinct()
    )
    return AssistanceType.objects.filter(id__in=type_ids, is_active=True)


@login_required
@mswd_required
def mswd_dashboard_view(request):
    status_filter = request.GET.get("status", "")
    type_filter = request.GET.get("type", "")

    requests = AssistanceRequest.objects.filter(is_active=True).order_by("-submitted_at")
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
        AssistanceRequest,
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
