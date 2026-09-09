"""Read-only attribution over retained DV printing and packet evidence."""

PRINT_HISTORY_ACTIONS = {
    "dv_signing_copy_ready": ("prepared_by_id", "Prepared signing copy"),
    "dv_copies_printed": ("printed_by_id", "Recorded printed copies"),
    "finance_packet_assembled": ("custody_confirmed_by_id", "Assembled signing packet"),
}


def _number(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int) or (isinstance(value, str) and value.isascii() and value.isdigit()):
        if len(str(value)) <= 19:
            number = int(value)
            if 0 <= number <= 2**63 - 1:
                return number
    return None


def print_history_evidence(events):
    """Batch-match event references; neither current status nor a bare event is proof."""
    from vouchers.models import VoucherPrintJob

    candidates = [event for event in events
                  if event.action in PRINT_HISTORY_ACTIONS and isinstance(event.metadata, dict)]
    identifiers = {_number(event.metadata.get("print_job_id")) for event in candidates} - {None}
    jobs = {job.pk: job for job in VoucherPrintJob.objects.filter(pk__in=identifiers).select_related(
        "output", "tracepoint_item",
    )}
    evidence = {}
    for event in candidates:
        meta = event.metadata
        job = jobs.get(_number(meta.get("print_job_id")))
        actor_field, label = PRINT_HISTORY_ACTIONS[event.action]
        if (
            job is None or job.case_id != event.case_id
            or job.version != _number(meta.get("print_version"))
            or getattr(job, actor_field) != event.actor_id
            or job.output.case_id != event.case_id
            or not job.output_checksum or job.output.checksum != job.output_checksum
        ):
            continue
        if event.action == "dv_signing_copy_ready":
            if job.output_id != _number(meta.get("output_id")) or meta.get("checksum") != job.output_checksum:
                continue
        elif event.action == "dv_copies_printed":
            if not job.printed_at or not job.copy_count or job.copy_count != _number(meta.get("copy_count")):
                continue
        else:
            manifest = job.custody_manifest
            if (
                not job.custody_confirmed_at or not job.tracepoint_item_id
                or not isinstance(manifest, dict) or not isinstance(manifest.get("checkpoints"), list)
                or meta.get("packet_reference") != job.packet_reference
                or meta.get("item_reference") != job.tracepoint_item.reference_number
                or manifest.get("tracepoint_packet") != job.packet_reference
                or manifest.get("tracepoint_item") != job.tracepoint_item.reference_number
                or _number(meta.get("checkpoint_count")) != len(manifest["checkpoints"])
            ):
                continue
        label = f"{label} v{job.version}"
        if event.action == "dv_copies_printed":
            label += f" ({job.copy_count} copies)"
        elif event.action == "finance_packet_assembled":
            label += f" - {job.packet_reference}"
        evidence[event.pk] = {
            "label": label,
            "state": job.get_status_display(),
            "snapshot": {
                "print_job_id": job.pk, "print_version": job.version,
                "output_id": job.output_id, "checksum": job.output_checksum,
                "copy_count": job.copy_count, "packet_reference": job.packet_reference,
                "item_reference": job.tracepoint_item.reference_number if job.tracepoint_item_id else "",
                "status": job.status, "supersession_reason": job.supersession_reason,
                "actor_id": getattr(job, actor_field),
            },
            "exception": (
                "This signing copy was later superseded; retain it as history and use the current copy for signing."
                if job.status == VoucherPrintJob.SUPERSEDED else ""
            ),
        }
    return evidence
