from urllib import request
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.http import HttpResponse
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from django.utils.translation import gettext as _
from django.utils.safestring import mark_safe
from .models import AssistanceRequest, AssistanceType, RequestDocument, RequestLog
from .forms import AssistanceRequestForm, AssistanceRequestEditForm, RequestDocumentForm
from io import BytesIO
import qrcode

import logging
logger = logging.getLogger(__name__)


import os
from django.core.exceptions import ValidationError

ALLOWED_EXTENSIONS = ['.pdf', '.doc', '.docx', '.txt', '.rtf', '.jpg', '.jpeg', '.png', '.gif', '.xls', '.xlsx', '.csv', '.ppt', '.pptx']
MAX_FILE_SIZE_MB = 5

def validate_file_upload(f):
    ext = os.path.splitext(f.name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError(f"Unsupported file type: {ext}")

    if f.size > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise ValidationError(f"File size exceeds {MAX_FILE_SIZE_MB}MB.")


### Assistance Requests-related views ###
def submit_assistance_view(request):
    if request.method == 'POST':
        form = AssistanceRequestForm(request.POST, request.FILES)
        files = request.FILES.getlist('file')

        if form.is_valid():
            cleaned = form.cleaned_data
            assistance_type = cleaned.get('assistance_type')
            email = cleaned.get('email')
            period = cleaned.get('period')
            semester = cleaned.get('semester')

            # 🔒 DUPLICATE CHECK
            existing = AssistanceRequest.objects.filter(
                assistance_type=assistance_type,
                email=email,
                period=period,
                is_active=True
            )
            if semester:
                existing = existing.filter(semester=semester)
            else:
                existing = existing.filter(semester__isnull=True)

            if existing.exists():
                # when blocking duplicate submissions
                messages.error(request, mark_safe(
                    "You have already submitted a request for this school year and semester.<br>"
                    "Please check your email again for your <b><i><u>reference and edit codes</u></i></b> and track them here:"
                ))
                return redirect(f"{reverse('assistance_landing')}?duplicate=1")

            # Proceed if no duplicate
            instance = form.save()
            file_errors = []

            for f in files:
                try:
                    validate_file_upload(f)
                    RequestDocument.objects.create(request=instance, file=f)
                except ValidationError as e:
                    file_errors.append(f"{f.name}: {e}")

            if file_errors:
                for err in file_errors:
                    messages.warning(request, err)

            # Generate links
            access_link = request.build_absolute_uri(
                reverse('edit_request', args=[instance.edit_code])
            )
            track_link = request.build_absolute_uri(
                reverse('track_request', args=[instance.reference_code])
            )

            # Optional: Send confirmation email
            send_mail(
                'Your Assistance Request Confirmation',
                f"""Hi {instance.full_name},

Thanks for submitting your request!

📌 Reference Code: {instance.reference_code}
🔑 Edit Code: {instance.edit_code}

You may edit or track your request here:
Edit: {access_link}
Track: {track_link}

– This is an automated message. Please do not reply.
""",
                settings.ASSISTANCE_FROM_EMAIL,
                [instance.email],
                fail_silently=True,
            )

            return redirect('confirmation_view', reference_code=instance.reference_code, edit_code=instance.edit_code)
        else:
            messages.error(request, _("Please correct the errors below."))

    else:
        form = AssistanceRequestForm()

    return render(request, 'assistance/submit.html', {'form': form})


def confirmation_view(request, reference_code, edit_code):
    access_link = request.build_absolute_uri(reverse('edit_request', args=[edit_code]))
    track_link = request.build_absolute_uri(reverse('track_request', args=[reference_code]))
    return render(request, 'assistance/confirmation.html', {
        'reference_code': reference_code,
        'edit_code': edit_code,
        'edit_link': access_link,
        'track_link': track_link,
    })


def edit_request_view(request, edit_code):
    req = get_object_or_404(AssistanceRequest, edit_code=edit_code)

    # 🔒 Lock everything if already approved or claimed
    if req.status == 'approved' or req.claimed_at:
        return render(request, 'assistance/edit_locked.html', {
            'request_obj': req,
            'documents': req.documents.all().order_by('-uploaded_at'),
        })

    # 🟢 Editable if still pending or under review
    document_form = RequestDocumentForm()
    form = AssistanceRequestEditForm(instance=req)

    if request.method == 'POST':
        if 'upload_files' in request.POST:
            files = request.FILES.getlist('file')
            for f in files:
                try:
                    validate_file_upload(f)
                    RequestDocument.objects.create(request=req, file=f)
                except ValidationError as e:
                    messages.warning(request, f"{f.name}: {e}")
            messages.success(request, _("Files uploaded."))
        else:
            form = AssistanceRequestEditForm(request.POST, request.FILES, instance=req)
            if form.is_valid():
                form.save()
                messages.success(request, _("Request updated."))
            else:
                messages.error(request, _("Please fix the errors."))

        return redirect('edit_request', edit_code=edit_code)

    return render(request, 'assistance/edit_request.html', {
        'request_obj': req,
        'form': form,
        'document_form': document_form,
        'documents': req.documents.all().order_by('-uploaded_at'),
    })


def track_request_view(request, reference_code):
    req = get_object_or_404(AssistanceRequest, reference_code=reference_code)
    return render(request, 'assistance/track_request.html', {
        'request_obj': req,
        'documents': req.documents.all(),
        'logs': req.logs.all().order_by('-timestamp'),
    })


from django.core.mail import EmailMultiAlternatives
from django.utils.html import strip_tags

def assistance_landing(request):
    if request.method == "POST":
        form_type = request.POST.get('form_type')

        if form_type == 'track_edit':
            reference_code = request.POST.get('reference_code', '').strip().upper()
            edit_code = request.POST.get('edit_code', '').strip().upper()

            if not reference_code:
                messages.warning(request, "Please enter at least a reference code.")
                return redirect('assistance_landing')

            # First, check if the reference exists
            base_qs = AssistanceRequest.objects.filter(reference_code=reference_code)

            if not base_qs.exists():
                messages.error(request, "Reference code not found.")
                return redirect('assistance_landing')

            if edit_code:
                # Try to match both codes
                if base_qs.filter(edit_code=edit_code).exists():
                    return redirect('edit_request', edit_code=edit_code)
                else:
                    messages.error(request, "Invalid reference or edit code.")
            else:
                return redirect('track_request', reference_code=reference_code)

        elif form_type == 'resend_codes':
            email = request.POST.get('email', '').strip()
            requests = AssistanceRequest.objects.filter(email=email).order_by('-submitted_at')

            if requests.exists():
                for req in requests:
                    subject = f"Your Assistance Request for {req.period} {req.get_semester_display() if req.semester else ''}".strip()
                    track_link = request.build_absolute_uri(reverse('track_request', args=[req.reference_code]))
                    edit_link = request.build_absolute_uri(reverse('edit_request', args=[req.edit_code]))

                    html_message = f"""
                    <p>Hi <strong>{req.full_name}</strong>,</p>
                    <p>Here are your request details:</p>
                    <ul>
                        <li><strong>School Year:</strong> {req.period}</li>
                        {f'<li><strong>Semester:</strong> {req.get_semester_display()}</li>' if req.semester else ''}
                    </ul>
                    <p>
                        📌 <strong>Reference Code:</strong> {req.reference_code}<br>
                        🔑 <strong>Edit Code:</strong> {req.edit_code}
                    </p>
                    <p>
                        🔍 <a href="{track_link}">Track Request</a><br>
                        ✏️ <a href="{edit_link}">Edit Request</a>
                    </p>
                    <p class="text-muted" style="font-size: 0.9em;">This is an automated message.</p>
                    """

                    plain_message = strip_tags(html_message)

                    email_msg = EmailMultiAlternatives(
                        subject,
                        plain_message,
                        settings.ASSISTANCE_FROM_EMAIL,
                        [req.email]
                    )
                    email_msg.attach_alternative(html_message, "text/html")
                    email_msg.send(fail_silently=True)

                messages.success(request, _("We've re-sent your request codes to your email. Please check your inbox."))
            else:
                messages.warning(request, _("We couldn’t find any requests associated with that email address."))

    return render(request, 'assistance/landing.html')


def generate_qr(request, reference_code, edit_code):
    link = request.build_absolute_uri(
        reverse('edit_request', args=[edit_code])
    )
    img = qrcode.make(link)
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    return HttpResponse(buffer.getvalue(), content_type='image/png')


def resend_codes_view(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        requests = AssistanceRequest.objects.filter(email=email).order_by('-submitted_at')

        if requests.exists():
            for req in requests:
                subject = f"Your Assistance Request for {req.period} {req.get_semester_display() if req.semester else ''}".strip()
                
                track_link = request.build_absolute_uri(
                    reverse('track_request', args=[req.reference_code])
                )
                edit_link = request.build_absolute_uri(
                    reverse('edit_request', args=[req.edit_code])
                )

                html_message = f"""
                <p>Hi <strong>{req.full_name}</strong>,</p>

                <p>Here are your request details for:</p>
                <ul>
                    <li><strong>School Year:</strong> {req.period}</li>
                    {f'<li><strong>Semester:</strong> {req.get_semester_display()}</li>' if req.semester else ''}
                </ul>

                <p>
                    📌 <strong>Reference Code:</strong> {req.reference_code}<br>
                    🔑 <strong>Edit Code:</strong> {req.edit_code}
                </p>

                <p>
                    🔍 <a href="{track_link}">Track Request</a><br>
                    <br>
                    ✏️ <a href="{edit_link}">Edit Request</a>
                </p>

                <p class="text-muted" style="font-size: 0.9em;">This is an automated message.</p>
                """

                plain_message = strip_tags(html_message)

                email_msg = EmailMultiAlternatives(
                    subject,
                    plain_message,
                    settings.ASSISTANCE_FROM_EMAIL,
                    [req.email]
                )
                email_msg.attach_alternative(html_message, "text/html")
                email_msg.send(fail_silently=True)

            messages.success(request, _("We've re-sent your request codes to your email. Please check your inbox."))
        else:
            messages.warning(request, _("We couldn’t find any requests associated with that email address."))

    return redirect('assistance_landing')


from django.http import JsonResponse

def validate_codes_view(request):
    if request.method == "POST":
        reference_code = request.POST.get("reference_code", "").strip().upper()
        edit_code = request.POST.get("edit_code", "").strip().upper()

        response = {
            "reference_valid": False,
            "edit_valid": False,
            "message": ""
        }

        base_qs = AssistanceRequest.objects.filter(reference_code=reference_code)

        if not base_qs.exists():
            response["message"] = "❌ Reference code not found."
            return JsonResponse(response)

        response["reference_valid"] = True

        if edit_code:
            if base_qs.filter(edit_code=edit_code).exists():
                response["edit_valid"] = True
                response["message"] = "✅ Reference and edit code match."
            else:
                response["message"] = "❌ Edit code does not match."
        else:
            response["message"] = "✅ Reference code found. Edit code optional."

        return JsonResponse(response)
    
    return JsonResponse({"error": "Invalid request"}, status=400)


### MSWD Dashboard-related views ###
from .decorators import mswd_required

@login_required
@mswd_required
def mswd_dashboard_view(request):
    status_filter = request.GET.get('status', '')
    type_filter = request.GET.get('type', '')

    requests = AssistanceRequest.objects.filter(is_active=True).order_by('-submitted_at')

    if status_filter:
        requests = requests.filter(status=status_filter)
    if type_filter:
        requests = requests.filter(assistance_type__id=type_filter)

    types = AssistanceType.objects.filter(is_active=True)

    context = {
        'requests': requests,
        'types': types,
        'selected_status': status_filter,
        'selected_type': type_filter,
    }
    return render(request, 'assistance/mswd/dashboard.html', context)


from django.views.decorators.http import require_POST

@login_required
@mswd_required
def mswd_request_detail_view(request, ref_code):
    assistance_request = get_object_or_404(AssistanceRequest, reference_code=ref_code)
    documents = assistance_request.documents.all().order_by('uploaded_at')

    if request.method == "POST":
        old_status = assistance_request.status
        new_status = request.POST.get('status')
        remarks = request.POST.get('remarks', '')

        status_changed = new_status != old_status
        remarks_changed = remarks != (assistance_request.remarks or '')

        if status_changed or remarks_changed:
            # Save updated values
            assistance_request.status = new_status
            assistance_request.remarks = remarks
            assistance_request.save()

            # Determine action type
            if status_changed and remarks_changed:
                action = 'manual_edit'
            elif status_changed:
                action = 'status_change'
            elif remarks_changed:
                action = 'remarks_updated'
            else:
                action = 'manual_edit'

            # Log the change
            RequestLog.objects.create(
                request=assistance_request,
                updated_by=request.user,
                action_type=action,
                status_before=old_status,
                status_after=new_status,
                remarks=remarks if remarks_changed else ''
            )

            # Send email notification
            send_mail(
                subject=f"Update on your Assistance Request ({assistance_request.reference_code})",
                message=f"Dear {assistance_request.full_name},\n\n"
                        f"Your request status has been updated to: {assistance_request.get_status_display()}.\n\n"
                        f"Remarks: {remarks or 'None'}\n\nThank you.",
                from_email=settings.NOTIFICATIONS_FROM_EMAIL,
                recipient_list=[assistance_request.email],
                fail_silently=True
            )

            messages.success(request, "Status and remarks updated. Email sent to requester.")

            logger.info(
                f"[MSWD STATUS UPDATE] Ref: {assistance_request.reference_code} | "
                f"By: {request.user.username} | From: {old_status} → {new_status} | "
                f"Remarks: {remarks or 'None'}"
            )

        return redirect('mswd_request_detail', ref_code=ref_code)

    # 🆕 Include logs in the GET context
    return render(request, 'assistance/mswd/request_detail.html', {
        'request_obj': assistance_request,
        'documents': documents,
        'logs': assistance_request.logs.select_related('updated_by').order_by('-timestamp'),
    })



@require_POST
@login_required
@mswd_required
def mswd_update_document_ajax(request, doc_id):
    try:
        document = RequestDocument.objects.get(pk=doc_id)
        new_status = request.POST.get('status')
        new_remarks = request.POST.get('remarks', '')

        document.status = new_status
        document.remarks = new_remarks
        document.save()
        logger.info(f"[MSWD FILE UPDATE] File ID: {document.id} | Ref: {document.request.reference_code} | "
            f"By: {request.user.username} | Status: {new_status} | Remarks: {new_remarks}")


        # Send email to requester
        send_mail(
            subject="Update on your uploaded document",
            message=f"One of your uploaded files has been reviewed.\n\nStatus: {document.get_status_display()}\nRemarks: {new_remarks or 'None'}\n\nReference: {document.request.reference_code}",
            from_email=settings.NOTIFICATIONS_FROM_EMAIL,
            recipient_list=[document.request.email],
            fail_silently=True
        )

        return JsonResponse({'success': True})
    except Exception as e:
        logger.error(f"[MSWD FILE UPDATE ERROR] {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@mswd_required
def mswd_printable_view(request, ref_code):
    assistance_request = get_object_or_404(AssistanceRequest, reference_code=ref_code)
    documents = assistance_request.documents.all().order_by('uploaded_at')
    return render(request, 'assistance/mswd/printable_request.html', {
        'request_obj': assistance_request,
        'documents': documents,
    })
