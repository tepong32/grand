from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.http import HttpResponse
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from django.utils.translation import gettext as _
from .models import AssistanceRequest, RequestDocument
from .forms import AssistanceRequestForm, AssistanceRequestEditForm, RequestDocumentForm
from io import BytesIO
import qrcode

def submit_assistance_view(request):
    if request.method == 'POST':
        form = AssistanceRequestForm(request.POST, request.FILES)
        files = request.FILES.getlist('file')

        if form.is_valid():
            instance = form.save()
            for f in files:
                RequestDocument.objects.create(request=instance, file=f)

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

Edit or track here:
{access_link}

- This is an automated message.
""",
                settings.ASSISTANCE_FROM_EMAIL,
                [instance.email],
                fail_silently=True,
            )

            return redirect('confirmation_view', reference_code=instance.reference_code, edit_code=instance.edit_code)
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
    document_form = RequestDocumentForm()
    form = AssistanceRequestEditForm(instance=req)

    if request.method == 'POST':
        if 'upload_files' in request.POST:
            files = request.FILES.getlist('file')
            for f in files:
                RequestDocument.objects.create(request=req, file=f)
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

def assistance_landing(request):
    if request.method == "POST":
        reference_code = request.POST.get('reference_code', '').strip()
        edit_code = request.POST.get('edit_code', '').strip()

        if reference_code:
            if edit_code:
                if AssistanceRequest.objects.filter(reference_code=reference_code, edit_code=edit_code).exists():
                    return redirect('edit_request', edit_code=edit_code)
                else:
                    messages.error(request, "Invalid reference or edit code.")
            else:
                if AssistanceRequest.objects.filter(reference_code=reference_code).exists():
                    return redirect('track_request', reference_code=reference_code)
                else:
                    messages.error(request, "Reference code not found.")
        else:
            messages.warning(request, "Please enter at least a reference code.")

    return render(request, 'assistance/landing.html')

def generate_qr(request, reference_code, edit_code):
    link = request.build_absolute_uri(
        reverse('edit_request', args=[edit_code])
    )
    img = qrcode.make(link)
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    return HttpResponse(buffer.getvalue(), content_type='image/png')
