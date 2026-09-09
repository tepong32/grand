"""Personal amendment history proved by retained versions and signature rounds."""
from collections import defaultdict

from .work_dv_print_history import _number

AMENDMENT_HISTORY_ACTIONS = {
    "voucher_nonfinancial_amended": "Corrected DV date or signatories",
    "nonfinancial_amendment_signatures_completed": "Recorded final replacement-signature return",
}


def _descends(job, amendment, jobs):
    visited = set()
    previous_version = None
    while job is not None and job.pk not in visited:
        if job.case_id != amendment.case_id or (previous_version is not None and job.version >= previous_version):
            return False
        if job.signature_round == amendment.signature_round_number:
            return True
        visited.add(job.pk)
        previous_version = job.version
        job = jobs.get(job.supersedes_id)
    return False


def amendment_history_evidence(events):
    from vouchers.models import VoucherCase, VoucherNonFinancialAmendment, VoucherPrintJob, WetSignatureTask

    candidates = [event for event in events
                  if event.action in AMENDMENT_HISTORY_ACTIONS and isinstance(event.metadata, dict)]
    identifiers = {_number(event.metadata.get("amendment_id")) for event in candidates} - {None}
    amendments = {item.pk: item for item in VoucherNonFinancialAmendment.objects.filter(pk__in=identifiers)}
    case_ids = {item.case_id for item in amendments.values()}
    jobs = {job.pk: job for job in VoucherPrintJob.objects.filter(case_id__in=case_ids)}
    rounds = defaultdict(list)
    for task in WetSignatureTask.objects.filter(case_id__in=case_ids).order_by("sequence", "pk"):
        rounds[(task.case_id, task.round_number)].append(task)
    evidence = {}
    for event in candidates:
        meta = event.metadata
        amendment = amendments.get(_number(meta.get("amendment_id")))
        if amendment is None or amendment.case_id != event.case_id or amendment.version != _number(meta.get("amendment_version")):
            continue
        job = None
        actual_round = amendment.signature_round_number
        final_task = None
        created = event.action == "voucher_nonfinancial_amended"
        if created:
            if (
                event.actor_id != amendment.amended_by_id or event.from_stage != amendment.prior_stage
                or event.to_stage != VoucherCase.AWAITING_SIGNATURES
                or meta.get("old_voucher_date") != amendment.old_voucher_date.isoformat()
                or meta.get("new_voucher_date") != amendment.new_voucher_date.isoformat()
                or meta.get("financial_snapshot") != amendment.financial_snapshot
                or meta.get("resume_stage") != amendment.resume_stage
            ):
                continue
        else:
            if (
                event.from_stage != VoucherCase.AWAITING_SIGNATURES or event.to_stage != amendment.resume_stage
                or not amendment.completed_at or amendment.completed_at > event.created_at
            ):
                continue
            # Old events identify only the original amendment round. Never substitute the newest round.
            modern = any(key in meta for key in ("signature_round", "amendment_signature_round", "print_job_id"))
            if modern:
                actual_round = _number(meta.get("signature_round"))
                if not actual_round or _number(meta.get("amendment_signature_round")) != amendment.signature_round_number:
                    continue
                if meta.get("print_job_id") is not None:
                    job = jobs.get(_number(meta["print_job_id"]))
                    if job is None:
                        continue
            else:
                retained_jobs = [row for row in jobs.values()
                                 if row.case_id == event.case_id and row.signature_round == actual_round
                                 and row.signed_returned_by_id == event.actor_id and row.signed_returned_at
                                 and amendment.amended_at <= row.signed_returned_at <= event.created_at]
                if len(retained_jobs) > 1:
                    continue
                job = retained_jobs[0] if retained_jobs else None
            tasks = rounds.get((event.case_id, actual_round), [])
            if not tasks or any(task.status != WetSignatureTask.SIGNED_RETURNED for task in tasks):
                continue
            final_task = tasks[-1]
            if (
                final_task.recorded_by_id != event.actor_id or not final_task.recorded_at
                or not amendment.amended_at <= final_task.recorded_at <= event.created_at
            ):
                continue
            controlled = event.case.voucher_template_id and event.case.voucher_template.controlled_print_required
            if job is None:
                if controlled or actual_round != amendment.signature_round_number:
                    continue
            elif (
                job.signature_round != actual_round or job.signed_returned_by_id != event.actor_id
                or not job.signed_returned_at or not amendment.amended_at <= job.signed_returned_at <= event.created_at
                or not _descends(job, amendment, jobs)
            ):
                continue
        evidence[event.pk] = {
            "label": f"{AMENDMENT_HISTORY_ACTIONS[event.action]} - amendment v{amendment.version}",
            "state_label": "Amendment state", "state": amendment.get_status_display(),
            "exception": "" if created else "This credits the custody recorder, not the physical signatories.",
            "snapshot": {
                "amendment_id": amendment.pk, "version": amendment.version, "status": amendment.status,
                "old_date": amendment.old_voucher_date.isoformat(), "new_date": amendment.new_voucher_date.isoformat(),
                "financial_snapshot": amendment.financial_snapshot, "original_round": amendment.signature_round_number,
                "actual_round": actual_round, "print_job_id": job.pk if job else None,
                "final_task_id": final_task.pk if final_task else None, "actor_id": event.actor_id,
            },
        }
    return evidence
