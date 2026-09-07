"""Read-only source handoff projections across the core and Finance stores."""
from dataclasses import dataclass
from uuid import UUID

from django.core.exceptions import ValidationError

from .access import can_post_journals, can_prepare_journals, department_for_user
from .models import JournalEntry
from .posted_evidence import require_persisted_posting, verify_source_link


@dataclass(frozen=True)
class SourceHandoff:
    kind: str
    source: object
    entry: object
    action: str
    exception: str


def source_handoffs(user, *, kind=None, public_id=None):
    """Project creation and synchronization; existing draft/review stays a JEV task."""
    from vouchers.models import RemittancePostingRequest, VoucherPostingRequest

    department = department_for_user(user)
    prepare, post = can_prepare_journals(user), can_post_journals(user)
    if department is None or not (prepare or post):
        return []
    result = []
    for source_kind, model, related in (
        ("voucher", VoucherPostingRequest, "case"),
        ("remittance", RemittancePostingRequest, "batch"),
    ):
        if kind is not None and kind != source_kind:
            continue
        sources = model.objects.filter(
            finance_department_id=department.pk,
            status__in=(model.PENDING, model.FAILED, model.MATERIALIZED),
        ).select_related(related)
        if public_id is not None:
            sources = sources.filter(public_id=public_id)
        sources = list(sources)
        entries = {entry.source_reference: entry for entry in JournalEntry.objects.filter(
            department_id=department.pk, source_type=source_kind,
            source_reference__in=[str(source.public_id) for source in sources],
        )}
        for source in sources:
            entry = entries.get(str(source.public_id))
            action = ""
            if entry is None and prepare:
                action = "materialize"
            elif entry is not None and entry.status == JournalEntry.POSTED and post:
                action = "synchronize"
            if not action:
                continue
            exceptions = [source.failure_reason] if source.failure_reason else []
            if entry is None and source.accounting_entry_public_id:
                exceptions.append("The retained JEV link is missing from this office's ledger; investigate before recovery.")
            if entry is not None:
                try:
                    verify_source_link(source, entry, source_type=source_kind)
                    require_persisted_posting(entry, user, source_type=source_kind)
                except ValidationError as exc:
                    exceptions.extend(exc.messages)
            result.append(SourceHandoff(source_kind, source, entry, action, " ".join(exceptions)))
    return result


def actionable_voucher_source_ids(user):
    """Match shared-case readiness to a source action or an eligible journal action."""
    from .journal_exports import journal_action_choices_for_user, journal_action_queryset

    source_ids = {str(item.source.public_id) for item in source_handoffs(user, kind="voucher")}
    for action, _label in journal_action_choices_for_user(user):
        journals, _selected = journal_action_queryset(user, action)
        source_ids.update(journals.filter(source_type="voucher").exclude(
            source_reference__isnull=True,
        ).values_list("source_reference", flat=True))
    valid_ids = set()
    for value in source_ids:
        try:
            valid_ids.add(UUID(str(value)))
        except (ValueError, TypeError, AttributeError):
            continue
    return valid_ids
