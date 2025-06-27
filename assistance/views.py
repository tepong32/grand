from urllib import request
from django.core.mail import EmailMultiAlternatives
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from django.utils.html import strip_tags
from django.utils.translation import gettext as _
from django.utils.safestring import mark_safe
from .models import AssistanceRequest, AssistanceType, RequestDocument, RequestLog
from .forms import AssistanceRequestForm, AssistanceRequestEditForm, RequestDocumentForm
from io import BytesIO
from telegram import Bot
import qrcode
import os
import logging
logger = logging.getLogger(__name__)


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
        form = AssistanceRequestForm(request.POST)

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
                messages.error(request, mark_safe(
                    "You have already submitted a request for this school year and semester.<br>"
                    "Please check your email again for your <b><i><u>reference and edit codes</u></i></b> and track them here:"
                ))
                return redirect(f"{reverse('assistance:assistance_landing')}?duplicate=1")

            # ✅ Save request (Step 1)
            instance = form.save()

            # 📩 Send email with Step 2 instructions
            subject = 'Your Assistance Request Confirmation'

            edit_link = request.build_absolute_uri(reverse('assistance:edit_request', args=[instance.edit_code]))
            track_link = request.build_absolute_uri(reverse('assistance:track_request', args=[instance.reference_code]))
            bot_link = os.getenv("ASSISTANCE_BOT_LINK")

            html_message = f"""
            <p>Hi <strong>{instance.full_name}</strong>,</p>

            <p>Thank you for submitting your financial assistance request.</p>

            <h4>📝 Step 1 Complete: Personal Information Submitted</h4>
            <p>
                Your request was received successfully.<br>
                To complete your application, please proceed to <strong>Step 2</strong> by uploading your required supporting documents.
            </p>

            <h5 class="mt-3">📌 Reference Code: <code>{instance.reference_code}</code></h5>
            <h5>🔑 Edit Code: <code>{instance.edit_code}</code></h5>

            <p>
                <a href="{edit_link}" style="background-color:#0d6efd;color:white;padding:10px 16px;border-radius:6px;text-decoration:none;display:inline-block;">
                    ➕ Continue to Upload Supporting Documents
                </a>
            </p>

            <hr style="margin:20px 0;">

            <h4>💬 Optional: Connect to Telegram</h4>
            <p>
                To receive status updates via Telegram, send the following message to our bot:
            </p>

            <pre style="background:#f8f9fa;padding:10px;border-radius:5px;">
            /link {instance.reference_code} {instance.edit_code}
            </pre>

            <p>
                You can start the bot here:<br>
                👉 <a href={{bot_link}} target="_blank">{{bot_link}}</a>
            </p>

            <p style="font-size:0.9em;color:#888;">
                This is an automated message. Please do not reply.
            </p>
            """

            plain_message = f"""
            Hi {instance.full_name},

            Thank you for submitting your financial assistance request.

            Step 1 Complete: Personal Information Submitted
            Kindly make sure to complete Step 2 to upload your supporting documents.

            Reference Code: {instance.reference_code}
            Edit Code: {instance.edit_code}

            Continue here: {edit_link}

            Telegram Updates (optional):
            To receive updates via Telegram, send the following to our bot:

            /link {instance.reference_code} {instance.edit_code}
            Bot: {{bot_link}}

            – This is an automated message.
            """

            email = EmailMultiAlternatives(
                subject,
                plain_message,
                settings.ASSISTANCE_FROM_EMAIL,
                [instance.email]
            )
            email.attach_alternative(html_message, "text/html")
            email.send(fail_silently=True)

            # ➡️ Redirect to Step 2: Upload page
            return redirect('assistance:edit_request', edit_code=instance.edit_code)

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

    form = AssistanceRequestEditForm(instance=req)
    document_form = RequestDocumentForm()

    if request.method == 'POST':
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' and 'file' in request.FILES:
            doc_type = request.POST.get('document_type')
            uploaded_file = request.FILES['file']

            if not doc_type:
                return JsonResponse({'status': 'danger', 'message': 'Please select a document type.'})

            try:
                validate_file_upload(uploaded_file)

                # 🧼 Delete existing doc of same type (optional: soft delete later)
                RequestDocument.objects.filter(request=req, document_type=doc_type).delete()

                # ✅ Save new file
                RequestDocument.objects.create(
                    request=req,
                    file=uploaded_file,
                    document_type=doc_type
                )
                return JsonResponse({'status': 'success', 'message': f'{uploaded_file.name} uploaded as {doc_type}.'})

            except ValidationError as e:
                return JsonResponse({'status': 'danger', 'message': f'{uploaded_file.name}: {str(e)}'})

        else:
            # ✏️ Updating request info (if allowed)
            form = AssistanceRequestEditForm(request.POST, instance=req)
            if form.is_valid():
                form.save()
                messages.success(request, _("Request updated."))
            else:
                messages.error(request, _("Please fix the errors."))

        return redirect('assistance:edit_request', edit_code=edit_code)

    locked_types = [
        doc.document_type for doc in req.documents.all()
        if doc.status in ['approved', 'pending']  # you can adjust this logic
    ]

    return render(request, 'assistance/edit_request.html', {
        'request_obj': req,
        'form': form,
        'document_form': document_form,
        'documents': req.documents.all().order_by('-uploaded_at'),
        'step': 2,
        'locked_types': locked_types,
    })


def track_request_view(request, reference_code):
    req = get_object_or_404(AssistanceRequest, reference_code=reference_code)
    return render(request, 'assistance/track_request.html', {
        'request_obj': req,
        'documents': req.documents.all(),
        'logs': req.logs.all().order_by('-timestamp'),
    })


def assistance_landing(request):
    if request.method == "POST":
        form_type = request.POST.get('form_type')

        if form_type == 'track_edit':
            reference_code = request.POST.get('reference_code', '').strip().upper()
            edit_code = request.POST.get('edit_code', '').strip().upper()

            if not reference_code:
                messages.warning(request, "Please enter at least a reference code.")
                return redirect('assistance:assistance_landing')

            # First, check if the reference exists
            base_qs = AssistanceRequest.objects.filter(reference_code=reference_code)

            if not base_qs.exists():
                messages.error(request, "Reference code not found.")
                return redirect('assistance:assistance_landing')

            if edit_code:
                # Try to match both codes
                if base_qs.filter(edit_code=edit_code).exists():
                    return redirect('assistance:edit_request', edit_code=edit_code)
                else:
                    messages.error(request, "Invalid reference or edit code.")
            else:
                return redirect('assistance:track_request', reference_code=reference_code)

        elif form_type == 'resend_codes':
            email = request.POST.get('email', '').strip()
            requests = AssistanceRequest.objects.filter(email=email).order_by('-submitted_at')

            if requests.exists():
                for req in requests:
                    subject = f"Your Assistance Request for {req.period} {req.get_semester_display() if req.semester else ''}".strip()
                    track_link = request.build_absolute_uri(reverse('assistance:track_request', args=[req.reference_code]))
                    edit_link = request.build_absolute_uri(reverse('assistance:edit_request', args=[req.edit_code]))

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
                    reverse('assistance:track_request', args=[req.reference_code])
                )
                edit_link = request.build_absolute_uri(
                    reverse('assistance:edit_request', args=[req.edit_code])
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

    return redirect('assistance:assistance_landing')


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


from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required

@require_POST
def delete_document_view(request):
    if request.headers.get('x-requested-with') != 'XMLHttpRequest':
        return JsonResponse({'status': 'error', 'message': 'Invalid request.'})

    doc_id = request.POST.get('doc_id')
    try:
        doc = RequestDocument.objects.get(id=doc_id)
        # Optional: only allow delete if not yet approved/locked
        if doc.request.status == 'approved' or doc.request.claimed_at:
            return JsonResponse({'status': 'error', 'message': 'Request is locked.'})

        doc.delete()
        return JsonResponse({'status': 'success', 'message': 'Document deleted.'})
    except RequestDocument.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Document not found.'})


@require_POST
def upload_document_ajax(request, edit_code):
    req = get_object_or_404(AssistanceRequest, edit_code=edit_code)

    # 🔒 Prevent uploads to locked requests
    if req.status == 'approved' or req.claimed_at:
        return JsonResponse({'status': 'error', 'message': 'This request is locked.'})

    doc_type = request.POST.get('document_type')
    uploaded_file = request.FILES.get('file')

    # 🧠 Extra safety: validate inputs
    if not doc_type or not uploaded_file:
        return JsonResponse({'status': 'error', 'message': 'Missing file or document type.'})

    try:
        # ✅ Validate file
        validate_file_upload(uploaded_file)

        # 💡 Optional: double-check doc_type against choices
        valid_doc_types = dict(RequestDocumentForm().fields['document_type'].choices).keys()
        if doc_type not in valid_doc_types:
            return JsonResponse({'status': 'error', 'message': 'Invalid document type.'})

        # 🟢 Replace or create document
        RequestDocument.objects.update_or_create(
            request=req,
            document_type=doc_type,
            defaults={
                'file': uploaded_file,
                'status': 'pending',
            }
        )

        return JsonResponse({'status': 'success', 'message': 'File uploaded successfully.'})

    except ValidationError as e:
        return JsonResponse({'status': 'error', 'message': str(e)})
    except Exception as e:
        logger.warning(f"Unexpected upload error: {e}")
        return JsonResponse({'status': 'error', 'message': 'Upload failed. Please try again later.'})



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

            # ✅ Send Telegram message if linked
            chat_id = assistance_request.telegram_chat_id
            if chat_id:
                msg = (
                    f"📢 *Your assistance request has been updated!*\n\n"
                    f"• Status: *{assistance_request.get_status_display()}*\n"
                    f"• Remarks: _{remarks or 'None'}_\n\n"
                    f"📌 Reference Code: `{assistance_request.reference_code}`"
                )
                send_telegram_update(chat_id, msg)

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
            message=f"One of your uploaded files has been reviewed.\n\n"
                    f"Status: {document.get_status_display()}\n"
                    f"Remarks: {new_remarks or 'None'}\n\n"
                    f"Reference: {document.request.reference_code}",
            from_email=settings.NOTIFICATIONS_FROM_EMAIL,
            recipient_list=[document.request.email],
            fail_silently=True
        )

        # ✅ Send Telegram message if linked
        ### Telegram notification utility
        # This function is used to send updates to Telegram users about their assistance requests.
        chat_id = document.request.telegram_chat_id
        if chat_id:
            msg = (
                f"📄 *Your uploaded document has been reviewed!*\n\n"
                f"• Status: *{document.get_status_display()}*\n"
                f"• Remarks: _{new_remarks or 'None'}_\n\n"
                f"📌 Reference Code: `{document.request.reference_code}`"
            )
            send_telegram_update(chat_id, msg)


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


def send_telegram_update(chat_id, message):
    if not chat_id or not message:
        return  # silently fail if either is missing

    try:
        from telegram import Bot
        bot = Bot(token=os.environ.get("TELEGRAM_BOT_TOKEN"))
        bot.send_message(chat_id=chat_id, text=message, parse_mode="Markdown")
    except Exception as e:
        logger.warning(f"[TELEGRAM ERROR] Failed to send message to chat {chat_id}: {str(e)}")

