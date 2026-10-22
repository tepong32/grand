"""Start RSMI preparation from original issues without netting returns or valuing stock."""
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import QueryDict
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from .access import can_stock, in_gso_scope
from .models import StockMovement
from .supply_draft_sources import read_selection, sign_selection, source_digest
from .supply_drafts import MAX_DRAFT_LINES, RSMIHeaderForm, RSMILines, _prepare
from .views import _stock_history_selection, _stock_items


TOKEN_SALT = "gso-issue-rsmi-draft-v1"


def _sources(movements):
    return [{"id": row.pk, "uuid": str(row.public_id), "item_id": row.item_id,
             "item_uuid": str(row.item.public_id), "name": row.item.name, "unit": row.item.unit,
             "kind": row.kind, "quantity": str(row.quantity), "signed_quantity": str(row.signed_quantity),
             "recorded_at": timezone.localtime(row.occurred_at).isoformat(), "actor": row.actor_id,
             "department_id": row.department_id, "department": row.department_label,
             "recipient": row.recipient, "reference": row.reference, "reason": row.reason,
             "unit_cost": str(row.unit_cost) if row.unit_cost is not None else None}
            for row in movements]


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def rsmi_from_issues(request):
    if not in_gso_scope(request.user) or not can_stock(request.user, "view") or not can_stock(request.user, "export"):
        raise PermissionDenied
    token = request.POST.get("issue_source_token", "") if request.method == "POST" else ""
    sources, initial, error = [], None, ""
    try:
        if request.method == "POST":
            payload = read_selection(token, request.user, salt=TOKEN_SALT)
            movements = list(StockMovement.objects.filter(item__in=_stock_items(request.user), pk__in=payload["ids"])
                             .select_related("item").order_by("occurred_at", "pk"))
            if len(movements) != len(payload["ids"]):
                raise ValidationError("A selected issue is no longer available in your office scope. Reopen movement history to start again.")
            candidate = _sources(movements)
            if source_digest(candidate) != payload["digest"]:
                raise ValidationError("A selected issue changed. Your entries are retained; reopen movement history to start from current records.")
            sources = candidate
        else:
            form, rows, _ = _stock_history_selection(request)
            if not form.is_valid():
                raise ValidationError("Check the recording dates, movement type and source search in Movement history before starting the draft.")
            if form.cleaned_data["kind"] != StockMovement.ISSUE:
                raise ValidationError("Choose Issued in Movement history before starting an RSMI draft.")
            movements = list(rows.order_by("occurred_at", "pk")[:MAX_DRAFT_LINES + 1])
            if not movements:
                raise ValidationError("No recorded issues match. Change the filters; an empty selection does not certify that no supplies were issued.")
            if len(movements) > MAX_DRAFT_LINES:
                raise ValidationError("More than 50 issues match. Narrow the recording dates, supply item or source reference; no issues have been omitted.")
            sources = _sources(movements)
            token = sign_selection(request.user, sources, salt=TOKEN_SALT)
            initial = QueryDict(mutable=True)
            initial.update({"lines-TOTAL_FORMS": str(len(sources)), "lines-INITIAL_FORMS": "0"})
            for index, source in enumerate(sources):
                values = {"description": source["name"], "unit": source["unit"], "quantity": source["quantity"],
                          "reference": source["reference"], "unit_cost": source["unit_cost"] or "",
                          "recipient_office": " · ".join(filter(None, (source["department"], source["recipient"]))),
                          "remarks": f"Recorded in GRAND {source['recorded_at']}. {source['reason']}"}
                for name, value in values.items():
                    initial[f"lines-{index}-{name}"] = value
        if any(row.kind != StockMovement.ISSUE for row in movements):
            raise ValidationError("Only original issue movements can start this draft. Returns and adjustments remain separate records.")
    except (signing.BadSignature, KeyError, TypeError):
        error = "The issue selection is missing, expired or invalid. Your entries are retained; reopen movement history to start again."
    except ValidationError as exc:
        error = " ".join(exc.messages)
    if error:
        sources = []
    return _prepare(request, kind="RSMI", title="Report of Supplies and Materials Issued",
                    header_class=RSMIHeaderForm, line_set=RSMILines, initial_data=initial,
                    source_context={"issue_sources": sources, "issue_source_token": token,
                                    "source_error": error, "from_issues": True})
