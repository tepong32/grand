from io import BytesIO

from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _
from django_ratelimit.decorators import ratelimit
import qrcode

from assistance.forms import AssistanceRequestEditForm, AssistanceRequestForm, RequestDocumentForm
from assistance.models import AssistanceRequest, RequestDocument
from assistance.services import (
    AssistanceNotificationService,
    AssistanceRequestService,
    DocumentService,
    DocumentServiceError,
    validate_reference_code_match,
)


ALLOWED_AJAX_HEADER = "XMLHttpRequest"


def _ajax_fail(message: str):
    return JsonResponse({"status": "error", "message": message}, status=400)


def _ajax_success(message: str):
    return JsonResponse({"status": "success", "message": message})


@ratelimit(key="ip", method="POST", rate="5/m", block=True)
def submit_assistance_view(request):
    if request.method != "POST":
        form = AssistanceRequestForm()
        return render(request, "assistance/submit.html", {"form": form})

    form = AssistanceRequestForm(request.POST)
    if not form.is_valid():
        messages.error(request, _("Please correct the errors below."))
        return render(request, "assistance/submit.html", {"form": form})

    cleaned = form.cleaned_data
    assistance_type = cleaned["assistance_type"]
    email = cleaned["email"]
    period = cleaned["period"]
    semester = cleaned.get("semester")

    if AssistanceRequestService.duplicate_exists(
        assistance_type=assistance_type,
        email=email,
        period=period,
        semester=semester,
    ):
        messages.error(
            request,
            mark_safe(
                "You have already submitted a request for this school year and semester."
                " <b><i><u>Reference and edit codes</u></i></b> were not changed."
            ),
        )
        return redirect(f"{reverse('assistance:assistance_landing')}?duplicate=1")

    instance = AssistanceRequestService.submit_request(
        assistance_type=assistance_type,
        period=period,
        semester=semester,
        full_name=cleaned["full_name"],
        email=email,
        phone=cleaned["phone"],
    )
    links = AssistanceRequestService.build_links(instance, request)
    AssistanceNotificationService.send_submission_codes(
        request_obj=instance,
        track_link=links.track_link,
        edit_link=links.edit_link,
    )
    return redirect(
        "assistance:confirmation_view",
        reference_code=instance.reference_code,
        edit_code=instance.edit_code,
    )


def confirmation_view(request, reference_code, edit_code):
    request_obj = get_object_or_404(
        AssistanceRequest,
        reference_code=reference_code.upper(),
        edit_code=edit_code.upper(),
        is_active=True,
    )
    return render(
        request,
        "assistance/confirmation.html",
        {
            "reference_code": request_obj.reference_code,
            "edit_code": request_obj.edit_code,
            "edit_link": request.build_absolute_uri(request_obj.get_edit_url()),
            "track_link": request.build_absolute_uri(request_obj.get_track_url()),
        },
    )


def edit_request_view(request, edit_code):
    req = get_object_or_404(AssistanceRequest, edit_code=edit_code.upper(), is_active=True)
    if req.is_locked:
        return render(
            request,
            "assistance/edit_locked.html",
            {
                "request_obj": req,
                "documents": req.documents.filter(is_removed=False).order_by("-uploaded_at"),
            },
        )

    form = AssistanceRequestEditForm(instance=req)
    document_form = RequestDocumentForm()

    if request.method == "POST":
        form = AssistanceRequestEditForm(request.POST, instance=req)
        if form.is_valid():
            form.save()
            messages.success(request, _("Request updated."))
            return redirect("assistance:edit_request", edit_code=edit_code.upper())
        messages.error(request, _("Please fix the errors."))

    locked_types = [
        doc.document_type
        for doc in req.documents.filter(is_removed=False)
        if doc.status in ["approved", "pending"]
    ]

    return render(
        request,
        "assistance/edit_request.html",
        {
            "request_obj": req,
            "form": form,
            "document_form": document_form,
            "documents": req.documents.filter(is_removed=False).order_by("-uploaded_at"),
            "step": 2,
            "locked_types": locked_types,
        },
    )


def track_request_view(request, reference_code):
    req = get_object_or_404(
        AssistanceRequest,
        reference_code=reference_code.upper(),
        is_active=True,
    )
    return render(
        request,
        "assistance/track_request.html",
        {
            "request_obj": req,
            "documents": req.documents.filter(is_removed=False),
            "logs": req.logs.all().order_by("-timestamp"),
        },
    )


def assistance_landing(request):
    if request.method == "POST":
        form_type = request.POST.get("form_type")

        if form_type == "track_edit":
            request_codes = validate_reference_code_match(
                reference_code=request.POST.get("reference_code", "").strip().upper(),
                edit_code=request.POST.get("edit_code", "").strip().upper(),
            )

            if not request_codes.reference_code:
                messages.error(request, "Reference code is required.")
                return redirect("assistance:assistance_landing")

            base_qs = AssistanceRequest.objects.filter(
                reference_code=request_codes.reference_code,
                is_active=True,
            )
            if not base_qs.exists():
                messages.error(request, "Reference code not found.")
                return redirect("assistance:assistance_landing")

            if request_codes.edit_code:
                if base_qs.filter(edit_code=request_codes.edit_code).exists():
                    return redirect("assistance:edit_request", edit_code=request_codes.edit_code)
                messages.error(request, "Invalid reference or edit code.")
            else:
                return redirect(
                    "assistance:track_request",
                    reference_code=request_codes.reference_code,
                )

        elif form_type == "resend_codes":
            email = request.POST.get("email", "").strip()
            if not email:
                messages.warning(request, "Email is required to resend access codes.")
                return redirect("assistance:assistance_landing")

            requests = AssistanceRequest.objects.filter(email=email, is_active=True).order_by("-submitted_at")

            if requests.exists():
                for req in requests:
                    links = AssistanceRequestService.build_links(req, request)
                    AssistanceNotificationService.send_resend_codes(
                        request_obj=req,
                        track_link=links.track_link,
                        edit_link=links.edit_link,
                    )
                messages.success(
                    request,
                    _("We've re-sent your request codes to your email. Please check your inbox."),
                )
            else:
                messages.warning(
                    request,
                    _("We couldn't find any requests associated with that email address."),
                )

    return render(request, "assistance/landing.html")


def generate_qr(request, reference_code, edit_code):
    edit_link = request.build_absolute_uri(
        reverse("assistance:edit_request", args=[edit_code])
    )
    img = qrcode.make(edit_link)
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return HttpResponse(buffer.getvalue(), content_type="image/png")


@ratelimit(key="ip", method="POST", rate="10/m", block=True)
@require_POST
def validate_codes_view(request):
    reference_code = request.POST.get("reference_code", "").strip().upper()
    edit_code = request.POST.get("edit_code", "").strip().upper()

    response = {"reference_valid": False, "edit_valid": False, "message": ""}

    base_qs = AssistanceRequest.objects.filter(reference_code=reference_code, is_active=True)
    if not base_qs.exists():
        response["message"] = "Reference code not found."
        return JsonResponse(response, status=404)

    response["reference_valid"] = True
    if edit_code:
        if base_qs.filter(edit_code=edit_code).exists():
            response["edit_valid"] = True
            response["message"] = "Reference and edit code match."
        else:
            response["message"] = "Edit code does not match."
    else:
        response["message"] = "Reference code found. Edit code optional."

    return JsonResponse(response)


@ratelimit(key="ip", method="POST", rate="10/m", block=True)
@require_POST
def resend_codes_view(request):
    email = request.POST.get("email", "").strip()
    if not email:
        messages.error(request, _("Email is required to resend codes."))
        return redirect("assistance:assistance_landing")

    requests = AssistanceRequest.objects.filter(email=email, is_active=True)

    if requests.exists():
        for req in requests.order_by("-submitted_at"):
            links = AssistanceRequestService.build_links(req, request)
            AssistanceNotificationService.send_resend_codes(
                request_obj=req,
                track_link=links.track_link,
                edit_link=links.edit_link,
            )
        messages.success(
            request,
            _("We've re-sent your request codes to your email. Please check your inbox."),
        )
    else:
        messages.warning(
            request,
            _("We couldn't find any requests associated with that email address."),
        )

    return redirect("assistance:assistance_landing")


def _rate_key_edit(_, request):
    token = request.resolver_match.kwargs.get("edit_code", "") if request.resolver_match else ""
    if not token:
        token = request.POST.get("edit_code", "")
    return f"{token}:{request.META.get('REMOTE_ADDR', '')}"


def _is_ajax_request(request):
    return request.headers.get("x-requested-with") == ALLOWED_AJAX_HEADER


@ratelimit(key=_rate_key_edit, method="POST", rate="12/m", block=True)
@require_POST
def upload_document_ajax(request, edit_code):
    if not _is_ajax_request(request):
        return _ajax_fail("Invalid request.")

    req = get_object_or_404(AssistanceRequest, edit_code=edit_code.upper(), is_active=True)
    if req.is_locked:
        return _ajax_fail("This request is locked.")

    document_type = request.POST.get("document_type", "").strip()
    uploaded_file = request.FILES.get("file")

    if not document_type or not uploaded_file:
        return _ajax_fail("Missing file or document type.")

    try:
        DocumentService.upload_or_replace(
            request_obj=req,
            document_type=document_type,
            uploaded_file=uploaded_file,
            created_by=request.user if request.user.is_authenticated else None,
        )
    except DocumentServiceError as exc:
        return _ajax_fail(str(exc))
    except Exception:
        return _ajax_fail("Upload failed. Please try again later.")

    return _ajax_success("File uploaded successfully.")


@ratelimit(key=_rate_key_edit, method="POST", rate="12/m", block=True)
@require_POST
def delete_document_view(request):
    if not _is_ajax_request(request):
        return _ajax_fail("Invalid request.")

    edit_code = request.POST.get("edit_code", "").strip().upper()
    doc_id_raw = request.POST.get("doc_id", "")
    try:
        doc_id = int(doc_id_raw)
    except (TypeError, ValueError):
        return _ajax_fail("Document not found.")

    doc = RequestDocument.objects.filter(id=doc_id, is_removed=False).select_related("request").first()
    if not doc:
        return _ajax_fail("Document not found.")

    req = doc.request
    if not edit_code or req.edit_code != edit_code:
        return _ajax_fail("Invalid request.")
    if req.is_locked:
        return _ajax_fail("Request is locked.")

    try:
        DocumentService.soft_delete_document(
            request_obj=req,
            document_id=doc_id,
            created_by=request.user if request.user.is_authenticated else None,
        )
    except DocumentServiceError as exc:
        return _ajax_fail(str(exc))
    except Exception:
        return _ajax_fail("Delete failed. Please try again later.")

    return _ajax_success("Document deleted.")
