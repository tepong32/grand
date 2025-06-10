from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.core.mail import send_mail
from django.conf import settings
from .forms import AssistanceRequestForm, EmailUpdateForm
from .models import RequestDocument, AssistanceRequest
from django.utils.translation import gettext as _


def request_assistance_view(request):
    """
    View to handle the submission of financial assistance requests.
    Displays a form for users to fill out their details and upload documents.
    Handles both GET and POST requests.
    """
    if request.method == 'POST':
        form = AssistanceRequestForm(request.POST, request.FILES)
        files = request.FILES.getlist('file')
        if form.is_valid():
            instance = form.save()

            # Save uploaded documents
            for file in files:
                RequestDocument.objects.create(request=instance, file=file)

            # Generate correct links
            edit_link = request.build_absolute_uri(
                reverse('edit_request', args=[instance.reference_code]) + f'?code={instance.edit_code}'
            )
            track_link = request.build_absolute_uri(
                reverse('track_request', args=[instance.reference_code])
            )

            # Send confirmation email
            subject = 'Your Financial Assistance Request Confirmation'
            message = f"""
                Hi {instance.full_name},

                Thank you for submitting a financial assistance request.

                📌 Reference Code: {instance.reference_code}
                🔑 Edit Code: {instance.edit_code}

                You can edit your request or upload more files using this link:
                {edit_link}

                You may also track your request’s progress here:
                {track_link}

                This is an automated message — please do not reply.
                """

            ### set proper email settings in your Django settings.py first
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
                'edit_link': edit_link,
                'track_link': track_link,
            })
    else:
        form = AssistanceRequestForm()

    print("Form valid?", form.is_valid())
    print("POST data:", request.POST)
    print("FILES received:", request.FILES.getlist('file'))

    return render(request, 'assistance/submit.html', {
        'form': form
    })


def edit_request_view(request, reference_code):
    """
    View to edit an existing assistance request.
    Allows updating email and uploading additional documents.
    """
    code = request.GET.get('code')
    request_obj = get_object_or_404(AssistanceRequest, reference_code=reference_code, edit_code=code)

    email_form = EmailUpdateForm(instance=request_obj)
    message = None

    if request.method == 'POST':
        if 'update_email' in request.POST:
            email_form = EmailUpdateForm(request.POST, instance=request_obj)
            if email_form.is_valid():
                email_form.save()
                message = _("Email updated successfully.")
        else:
            files = request.FILES.getlist('file')
            for f in files:
                RequestDocument.objects.create(request=request_obj, file=f)
            return redirect(request.path + f"?code={code}")

    return render(request, 'assistance/edit.html', {
        'request_obj': request_obj,
        'documents': request_obj.documents.all(),
        'email_form': email_form,
        'message': message,
    })

def track_request_view(request, reference_code):
    request_obj = get_object_or_404(AssistanceRequest, reference_code=reference_code)
    return render(request, 'assistance/track.html', {
        'request_obj': request_obj,
        'documents': request_obj.documents.all(),
        'logs': request_obj.logs.all().order_by('-timestamp'),
    })