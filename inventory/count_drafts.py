"""Start an editable RPCI draft from a bounded, explicitly selected count cohort."""
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import QueryDict
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from .access import can_stock
from .models import StockCount
from .stock_count_views import _count_selection, scoped_counts
from .supply_drafts import MAX_DRAFT_LINES, RPCIHeaderForm, RPCILines, _prepare
from .supply_draft_sources import read_selection, sign_selection, source_digest


TOKEN_SALT = "gso-count-rpci-draft-v1"


def _sources(counts):
    return [{"id": count.pk, "uuid": str(count.public_id), "basis": count.basis,
             "counted_on": count.counted_on.isoformat(), "quantity": str(count.quantity),
             "reference": count.reference, "note": count.note, "status": count.status,
             "version": count.state_version, "recorded_by": count.recorded_by_id,
             "decided_by": count.decided_by_id, "decided_at": str(count.decided_at),
             "decision_note": count.decision_note, "adjustment": count.adjustment_id}
            for count in counts]


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def rpci_from_counts(request):
    # Recheck both grants and current ownership before reading any source, on every request.
    rows = scoped_counts(request.user)
    if not can_stock(request.user, "export"):
        raise PermissionDenied
    token = request.POST.get("count_source_token", "") if request.method == "POST" else ""
    sources, initial, error = [], None, ""
    try:
        if request.method == "POST":
            payload = read_selection(token, request.user, salt=TOKEN_SALT)
            ids = payload["ids"]
            counts = list(rows.filter(pk__in=ids).order_by("counted_on", "public_id"))
            if len(counts) != len(ids):
                raise ValidationError("A selected count is no longer available in your office scope. Reopen the reviewed counts to start again.")
            candidate = _sources(counts)
            if source_digest(candidate) != payload["digest"]:
                raise ValidationError("A selected count changed. Your entries are retained below; reopen the reviewed counts to start from current records.")
            sources = candidate
        else:
            rows, selection = _count_selection(request)
            if selection["status"] != "approved":
                raise ValidationError("Choose Reviewed counts before starting an RPCI draft.")
            counts = list(rows.order_by("counted_on", "public_id")[:MAX_DRAFT_LINES + 1])
            if not counts:
                raise ValidationError("No reviewed counts match. Choose a count-sheet reference or supply item first; an empty selection does not certify zero stock.")
            if len(counts) > MAX_DRAFT_LINES:
                raise ValidationError("More than 50 counts match. Narrow the count-sheet reference or supply item before starting; no counts have been omitted.")
            sources = _sources(counts)
            token = sign_selection(request.user, sources, salt=TOKEN_SALT)
            initial = QueryDict(mutable=True)
            initial.update({"lines-TOTAL_FORMS": str(len(counts)), "lines-INITIAL_FORMS": "0"})
            for index, count in enumerate(counts):
                for name, value in {"article": count.basis["name"], "unit": count.basis["unit"],
                                    "card_quantity": count.basis["balance"], "counted_quantity": count.quantity,
                                    "remarks": f"Count {count.counted_on.isoformat()} · {count.reference}"}.items():
                    initial[f"lines-{index}-{name}"] = str(value)
        if any(count.status != StockCount.APPROVED for count in counts):
            raise ValidationError("Only reviewed counts can start this draft. Return to Reviewed counts to select current records.")
    except (signing.BadSignature, KeyError, TypeError):
        error = "The count selection is missing, expired or invalid. Your entries are retained; reopen the reviewed counts to start again."
    except ValidationError as exc:
        error = " ".join(exc.messages)
    if error:
        sources = []
    return _prepare(request, kind="RPCI", title="Report on the Physical Count of Inventories",
                    header_class=RPCIHeaderForm, line_set=RPCILines, initial_data=initial,
                    source_context={"count_sources": sources, "count_source_token": token,
                                    "source_error": error, "from_counts": True})
