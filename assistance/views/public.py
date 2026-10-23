from functools import wraps
from io import BytesIO

from django.contrib import messages
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.db import DatabaseError
from users.auth_throttle import consume_attempt, network_identity
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from django_ratelimit.decorators import ratelimit
import qrcode

from assistance.forms import AssistanceRequestEditForm, AssistanceRequestForm, RequestDocumentForm
from assistance.models import AssistanceRequest, RequestDocument
from assistance.files import document_response
from assistance.services import AssistanceRequestService, DocumentService, DocumentServiceError
from assistance.services.access_service import locked_request_for_mutation, resolve_request_for_edit, private_link_lifetime
from assistance.services.notifications import AssistanceNotificationService

ALLOWED_AJAX_HEADER = "XMLHttpRequest"


def _ajax_fail(message):
    return JsonResponse({"status": "error", "message": message}, status=400)


def _ajax_success(message):
    return JsonResponse({"status": "success", "message": message})


def private_response(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        try:
            response = view(request, *args, **kwargs)
        except Http404:
            if request.headers.get("x-requested-with") == ALLOWED_AJAX_HEADER:
                response = JsonResponse({"status": "error", "access_unavailable": True,
                    "message": "Private link unavailable. Use the Assistance page to email a new private link."}, status=404)
            else:
                response = render(request, "assistance/access_unavailable.html", status=404)
        except DatabaseError:
            response = HttpResponse("Request temporarily unavailable. Please try again later.", status=503)
        response["Cache-Control"] = "private, no-store"
        # Keep same-origin form CSRF checks working, including HTTP development;
        # never send the private URL as a referrer to an external origin.
        response["Referrer-Policy"] = "same-origin"
        response["X-Robots-Tag"] = "noindex, nofollow"
        return response
    return wrapped


@private_response
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
            "A request already exists for this school year and semester. Use your private email link or request a new one.",
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
        edit_code=instance.secure_edit_token,
    )



@private_response
@require_GET
def confirmation_view(request, reference_code, edit_code):
    req = resolve_request_for_edit(edit_code)
    if req.reference_code != reference_code.upper():
        raise Http404
    return render(request, "assistance/confirmation.html", {
        "reference_code": req.reference_code, "edit_code": edit_code, "private_link_days": f"{private_link_lifetime() / 86400:g}",
        "edit_link": request.build_absolute_uri(reverse("assistance:edit_request", args=[edit_code])),
        "track_link": request.build_absolute_uri(req.get_track_url()),
    })


@private_response
@require_http_methods(["GET", "POST"])
def edit_request_view(request, edit_code):
    if request.method == "POST":
        with locked_request_for_mutation(token=edit_code) as req:
            return _edit_request_response(request, req, edit_code)
    return _edit_request_response(request, resolve_request_for_edit(edit_code), edit_code)


def _edit_request_response(request, req, edit_code):
    context = {"request_obj": req, "access_token": edit_code, "private_link_days": f"{private_link_lifetime() / 86400:g}",
               "documents": req.documents.filter(is_removed=False).order_by("-uploaded_at"),
               "logs": req.logs.all().order_by("-timestamp")}
    if req.is_locked:
        return render(request, "assistance/edit_locked.html", context)
    previous_email = req.email
    form = AssistanceRequestEditForm(request.POST or None, instance=req)
    if request.method == "POST":
        if form.is_valid():
            updated = form.save(commit=False)
            updated.save(update_fields=("full_name", "email", "phone"))
            messages.success(request, _("Request updated."))
            if req.email != previous_email:
                # An email change revokes previous links. Renewal still goes
                # through the registered inbox, never a refreshed browser token.
                messages.info(request, _("Your email changed. Request a new private link using your updated email."))
                return redirect("assistance:assistance_landing")
            # Ordinary editing must not extend the original link's expiry.
            return redirect("assistance:edit_request", edit_code=edit_code)
        messages.error(request, _("Please fix the errors."))
    context.update(form=form, document_form=RequestDocumentForm(), step=2,
                   locked_types=[d.document_type for d in context["documents"] if d.status in {"approved", "pending"}])
    return render(request, "assistance/edit_request.html", context)


@require_GET
def track_request_view(request, reference_code):
    req = get_object_or_404(AssistanceRequest, reference_code=reference_code.upper(), is_active=True)
    # Intentionally do not pass the case, attachments or free-text logs publicly.
    return render(request, "assistance/track_request.html", {
        "reference_code": req.reference_code, "status_display": req.get_status_display(),
    })


def _renew_links(request):
    email = request.POST.get("email", "").strip()
    try:
        # Reuse the platform's atomic default-store counters across workers and
        # both renewal entry points. No raw email/IP is retained in the bucket.
        allowed = consume_attempt("assistance-private-link:network", network_identity(request), limit=10, window=60)
        retry_after = 60
        if allowed:
            retry_after = 3600
            allowed = consume_attempt("assistance-private-link:email", email.casefold(), limit=3, window=3600)
        if not allowed:
            response = HttpResponse("Too many requests. Please wait and try again.", status=429)
            response["Retry-After"] = str(retry_after)
            response["Cache-Control"] = "no-store"
            return response
        try:
            validate_email(email)
        except ValidationError:
            email = ""
        requests = list(AssistanceRequest.objects.filter(email__iexact=email, is_active=True).order_by("-submitted_at")) if email else []
    except DatabaseError:
        response = HttpResponse("Private link renewal is temporarily unavailable. Please try again later.", status=503)
        response["Cache-Control"] = "no-store"
        return response
    for req in requests:
        # Native collations can match accent aliases belonging to a different
        # email domain. Only the registered case-insensitive address is eligible.
        if req.email.strip().casefold() != email.casefold():
            continue
        links = AssistanceRequestService.build_links(req, request)
        AssistanceNotificationService.send_resend_codes(
            request_obj=req, track_link=links.track_link, edit_link=links.edit_link)
    # Same response for absent, inactive and existing requests; no destination or
    # private URL is returned to the caller. Recipients always come from the DB.
    messages.success(request, _("If an active request uses that email, a new private link will be sent there. Check your inbox and spam folder."))


@require_http_methods(["GET", "POST"])
def assistance_landing(request):
    if request.method == "POST":
        if request.POST.get("form_type") == "resend_codes":
            response = _renew_links(request)
            if response is not None:
                return response
        elif request.POST.get("form_type") == "track_edit":
            reference = request.POST.get("reference_code", "").strip().upper()
            if reference:
                return redirect("assistance:track_request", reference_code=reference)
            messages.error(request, _("Reference code is required."))
    return render(request, "assistance/landing.html", {"private_link_days": f"{private_link_lifetime() / 86400:g}"})


@private_response
@require_GET
def generate_qr(request, reference_code, edit_code):
    req = resolve_request_for_edit(edit_code)
    if req.reference_code != reference_code.upper():
        raise Http404
    # Reuse this token: viewing or scanning a QR does not extend its lifetime.
    link = request.build_absolute_uri(reverse("assistance:edit_request", args=[edit_code]))
    buffer = BytesIO()
    qrcode.make(link).save(buffer, format="PNG")
    return HttpResponse(buffer.getvalue(), content_type="image/png")


@ratelimit(key="ip", method="POST", rate="10/m", block=True)
@require_POST
def validate_codes_view(request):
    reference = request.POST.get("reference_code", "").strip().upper()
    exists = AssistanceRequest.objects.filter(reference_code=reference, is_active=True).exists()
    return JsonResponse({"reference_valid": exists, "edit_valid": False,
                         "message": "Use your private email link to view or edit details."}, status=200 if exists else 404)


@require_POST
def resend_codes_view(request):
    response = _renew_links(request)
    if response is not None:
        return response
    return redirect("assistance:assistance_landing")


def _rate_key_edit(_, request):
    token = request.resolver_match.kwargs.get("edit_code", "") if request.resolver_match else ""
    return f"{token or request.POST.get('access_token', '')}:{request.META.get('REMOTE_ADDR', '')}"


@private_response
@ratelimit(key=_rate_key_edit, method="POST", rate="12/m", block=True)
@require_POST
def upload_document_ajax(request, edit_code):
    if request.headers.get("x-requested-with") != ALLOWED_AJAX_HEADER:
        return _ajax_fail("Invalid request.")
    req = resolve_request_for_edit(edit_code)
    if req.is_locked:
        return _ajax_fail("This request is locked.")
    document_type = request.POST.get("document_type", "").strip()
    uploaded_file = request.FILES.get("file")
    if not document_type or not uploaded_file:
        return _ajax_fail("Missing file or document type.")
    try:
        DocumentService.upload_or_replace(request_obj=req, document_type=document_type, uploaded_file=uploaded_file,
                                          created_by=request.user if request.user.is_authenticated else None,
                                          access_token=edit_code)
    except Http404:
        raise
    except (DocumentServiceError, ValidationError) as exc:
        return _ajax_fail(str(exc))
    except Exception:
        return _ajax_fail("Upload failed. Please try again later.")
    return _ajax_success("File uploaded successfully.")


@private_response
@ratelimit(key=_rate_key_edit, method="POST", rate="12/m", block=True)
@require_POST
def delete_document_view(request):
    if request.headers.get("x-requested-with") != ALLOWED_AJAX_HEADER:
        return _ajax_fail("Invalid request.")
    req = resolve_request_for_edit(request.POST.get("access_token", ""))
    try:
        doc_id = int(request.POST.get("doc_id", ""))
    except (TypeError, ValueError):
        return _ajax_fail("Document not found.")
    try:
        DocumentService.soft_delete_document(request_obj=req, document_id=doc_id,
                                             created_by=request.user if request.user.is_authenticated else None,
                                             access_token=request.POST.get("access_token", ""))
    except Http404:
        raise
    except DocumentServiceError as exc:
        return _ajax_fail(str(exc))
    except Exception:
        return _ajax_fail("Delete failed. Please try again later.")
    return _ajax_success("Document deleted.")


@private_response
@require_GET
def citizen_document(request, edit_code, doc_id):
    req = resolve_request_for_edit(edit_code)
    doc = get_object_or_404(RequestDocument, pk=doc_id, request=req, is_removed=False)
    return document_response(doc)
