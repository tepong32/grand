from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.core.mail import send_mail
from django.conf import settings
from .forms import AssistanceRequestForm, AssistanceRequestEditForm, RequestDocumentForm
from .models import RequestDocument, AssistanceRequest
from django.utils.translation import gettext as _


def request_assistance_view(request):
    """
    Handles submission of financial assistance requests.
    Displays form, saves documents, and emails confirmation with access link.
    """
    if request.method == 'POST':
        form = AssistanceRequestForm(request.POST, request.FILES)
        files = request.FILES.getlist('file')

        if form.is_valid():
            instance = form.save()

            # Save uploaded documents
            for file in files:
                RequestDocument.objects.create(request=instance, file=file)

            # Unified edit/track access link
            access_link = request.build_absolute_uri(
                reverse('assistance_request_access_view', args=[instance.edit_code])
            )

            # Send confirmation email (if email configured)
            subject = 'Your Financial Assistance Request Confirmation'
            message = f"""
Hi {instance.full_name},

Thank you for submitting your financial assistance request.

📌 Reference Code: {instance.reference_code}
🔑 Edit Code: {instance.edit_code}

Use the link below to edit your request, upload documents, or track progress:
{access_link}

This is an automated message — please do not reply.
            """.strip()

            ### Optional: Enable this after setting up email config
            # send_mail(
            #     subject,
            #     message,
            #     settings.DEFAULT_FROM_EMAIL,
            #     [instance.email],
            #     fail_silently=True,
            # )

            return render(request, 'assistance/confirmation.html', {
                'reference_code': instance.reference_code,
                'edit_code': instance.edit_code,
                'access_link': access_link,
            })
    else:
        form = AssistanceRequestForm()

    return render(request, 'assistance/submit.html', {
        'form': form
    })


def track_request_view(request, reference_code):
    request_obj = get_object_or_404(AssistanceRequest, reference_code=reference_code)
    return render(request, 'assistance/track.html', {
        'request_obj': request_obj,
        'documents': request_obj.documents.all(),
        'logs': request_obj.logs.all().order_by('-timestamp'),
    })


def assistance_request_access_entry(request):
    '''
    View to handle access to an existing assistance request using an edit code.
    Users can enter their edit code to retrieve their request.
    '''
    if request.method == 'POST':
        edit_code = request.POST.get('edit_code', '').strip()
        if not edit_code:
            messages.error(request, _("Please enter a valid edit code."))
            return redirect('assistance_access')

        try:
            req = AssistanceRequest.objects.get(edit_code=edit_code)
            return redirect('assistance_request_access_view', edit_code=edit_code)
        except AssistanceRequest.DoesNotExist:
            messages.error(request, _("No request found for that edit code."))
            return redirect('assistance_access')

    return render(request, 'assistance/assistance_request_code_entry.html')


def assistance_request_access_view(request, edit_code):
    request_obj = get_object_or_404(AssistanceRequest, edit_code=edit_code)
    document_form = RequestDocumentForm()
    form = AssistanceRequestEditForm(instance=request_obj)

    if request.method == 'POST':
        if 'upload_files' in request.POST:
            files = request.FILES.getlist('file')
            if files:
                for f in files:
                    RequestDocument.objects.create(request=request_obj, file=f)
                messages.success(request, _("Files uploaded successfully."))
            else:
                messages.warning(request, _("No files selected for upload."))
        else:
            form = AssistanceRequestEditForm(request.POST, request.FILES, instance=request_obj)
            if form.is_valid():
                form.save()
                messages.success(request, _("Request updated successfully."))
            else:
                messages.error(request, _("Please correct the errors in the form."))

        return redirect('assistance_request_access_view', edit_code=edit_code)

    return render(request, 'assistance/assistance_request_access.html', {
        'request_obj': request_obj,
        'form': form,
        'document_form': document_form,
        'documents': request_obj.documents.all().order_by('-uploaded_at'),
    })


import qrcode
from io import BytesIO
from django.http import HttpResponse

def generate_qr(request, reference_code, edit_code):
    access_url = request.build_absolute_uri(
        reverse('assistance_request_access_view', args=[edit_code])
    )
    img = qrcode.make(access_url)
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    return HttpResponse(buffer.getvalue(), content_type='image/png')
