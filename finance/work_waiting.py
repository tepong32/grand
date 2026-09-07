from __future__ import annotations

from uuid import UUID

from django.db.models import Q
from django.urls import reverse


def personal_waiting_tasks(user, department, today, actionable_tasks):
    """Project attributed handoffs only after current source-record authorization."""
    from accounting.access import can_view_accounting
    from accounting.models import JournalEntry, OpeningBalanceBatch, PeriodCloseRun
    from vouchers.access import can_view_workbench, has_explicit_permission
    from vouchers.advice_register import visible_bank_advice_batches
    from vouchers.models import BankAdviceBatch, RemittancePostingRequest, TreasuryRemittanceBatch
    from vouchers.remittance_register import visible_remittance_batches
    from vouchers.roles import is_finance_uat_viewer
    from .work_tasks import FinanceWorkTask, _age_days, _projection_checksum, _source_record_identity

    if is_finance_uat_viewer(user):
        return []
    actionable = {task.case_id for task in actionable_tasks}
    # A remittance batch, its posting request and its journal have distinct stable
    # IDs. Resolve the user's already-authorized child actions before Waiting.
    def identities(prefix):
        result = set()
        for identity in actionable:
            if identity.startswith(prefix):
                try:
                    result.add(UUID(identity[len(prefix):]))
                except (ValueError, TypeError, AttributeError):
                    continue
        return result

    source_ids = identities("remittance-source:")
    journal_ids = identities("journal-entry:")
    if journal_ids:
        for reference in JournalEntry.objects.filter(public_id__in=journal_ids, source_type="remittance").values_list("source_reference", flat=True):
            try:
                source_ids.add(UUID(str(reference)))
            except (ValueError, TypeError, AttributeError):
                continue
    if source_ids:
        actionable.update(
            f"treasury-remittance:{batch_id}" for batch_id in RemittancePostingRequest.objects.filter(
                public_id__in=source_ids,
            ).values_list("batch__public_id", flat=True)
        )
    tasks = []

    def add(item, *, kind, area, reference, subject, received, queue, scope, route, attribution, source_id=None, route_kwargs=None):
        source_id = source_id if source_id is not None else item.public_id
        identity = f"{kind}:{source_id}"
        if identity in actionable:
            return
        missing_time = received is None
        revision = _projection_checksum({
            "identity": identity, "status": item.status, "attribution": attribution,
            "received": received.isoformat() if received else None,
            "scope": scope, "queue": queue,
            "version": getattr(item, "state_version", getattr(item, "version", None)),
            "reference": reference, "subject": subject,
        })
        tasks.append(FinanceWorkTask(
            task_id=f"finwork:v1:{identity}:waiting", task_type=f"finance.{kind}.waiting.v1",
            area=area, case_id=identity, reference=reference, subject=subject,
            transaction_type=item._meta.verbose_name.title(), action="View submitted work",
            gate="You prepared or submitted this record. Its current handoff is with the named queue; no supported action on this record is available to you now.",
            owner_queue=queue, scope=scope, received_at=received,
            due_on=None, due_state="No structured target",
            calendar_basis="Elapsed calendar days since the retained handoff; document and ledger dates are not deadlines.",
            age_days=_age_days(received, today), state="Waiting", source_state=item.get_status_display(),
            source_version=f"projection-sha256:{revision}",
            exception="The source has no retained handoff time; age is unavailable." if missing_time else "",
            url=reverse(route, kwargs=route_kwargs if route_kwargs is not None else {"public_id": item.public_id}),
        ))

    from .access import can_view_finance_setup
    from .models import FinanceConfigurationRelease

    if can_view_finance_setup(user):
        releases = FinanceConfigurationRelease.objects.filter(department_id=department.pk, status="submitted").filter(
            Q(created_by_id=user.pk) | Q(submitted_by_id=user.pk),
        )
        for item in releases:
            add(item, kind="setup-release", area="Finance setup", reference=f"{item.code} v{item.version} · FY {item.fiscal_year}",
                subject=item.title, received=item.submitted_at, queue=f"Independent Accounting configuration approvers - {department.name}",
                scope=f"{department.name}; FY {item.fiscal_year}", route="finance:release_detail",
                attribution=[item.created_by_id, item.submitted_by_id], source_id=_source_record_identity("setup-release", item.pk),
                route_kwargs={"pk": item.pk})

    from budget.access import can_view as can_view_budget, has_budget_permission
    from budget.control_exports import obligation_scope_for_user
    from budget.models import AllotmentReleaseOrder, BudgetVersion, ObligationRequest

    if can_view_budget(user):
        versions = BudgetVersion.objects.filter(department_id=department.pk, status=BudgetVersion.FOR_REVIEW).filter(
            Q(created_by_id=user.pk) | Q(submitted_by_id=user.pk),
        ).select_related("fiscal_year")
        for item in versions:
            add(item, kind="budget-version", area="Budget", reference=f"FY {item.fiscal_year.year} {item.get_kind_display()} v{item.version}",
                subject=item.title, received=item.submitted_at, queue=f"Independent Budget proposal reviewers - {department.name}",
                scope=f"{department.name}; {item.requesting_department_label}", route="budget:version_detail",
                attribution=[item.created_by_id, item.submitted_by_id])
        if has_budget_permission(user, "view_allotment_control"):
            allotments = AllotmentReleaseOrder.objects.filter(department_id=department.pk, status=AllotmentReleaseOrder.FOR_REVIEW).filter(
                Q(created_by_id=user.pk) | Q(submitted_by_id=user.pk),
            ).select_related("fiscal_year")
            for item in allotments:
                add(item, kind="allotment-order", area="Budget", reference=item.order_number,
                    subject="Submitted allotment order", received=item.submitted_at, queue=f"Independent allotment reviewers - {department.name}",
                    scope=f"{department.name}; FY {item.fiscal_year.year}", route="budget:allotment_detail",
                    attribution=[item.created_by_id, item.submitted_by_id])
        obligations = obligation_scope_for_user(user).filter(status=ObligationRequest.FOR_CERTIFICATION).filter(
            Q(created_by_id=user.pk) | Q(submitted_by_id=user.pk),
        ).select_related("fiscal_year")
        for item in obligations:
            add(item, kind="obligation-request", area="Budget", reference=item.request_reference,
                subject=item.particulars, received=item.submitted_at, queue=f"Budget certification officers - {item.department_label}",
                scope=f"{item.requesting_department_label}; FY {item.fiscal_year.year}", route="budget:obligation_detail",
                attribution=[item.created_by_id, item.submitted_by_id])

    if can_view_accounting(user):
        journals = JournalEntry.objects.filter(department_id=department.pk, status=JournalEntry.SUBMITTED).filter(
            Q(created_by_id=user.pk) | Q(submitted_by_id=user.pk),
        ).select_related("period", "fund")
        for item in journals:
            add(item, kind="journal-entry", area="Accounting", reference=item.reference,
                subject=item.description, received=item.submitted_at,
                queue=f"Independent Accounting JEV posters - {department.name}",
                scope=f"{department.name}; {item.period}; fund {item.fund.code}", route="accounting:entry_detail",
                attribution=[item.created_by_id, item.submitted_by_id])
        openings = OpeningBalanceBatch.objects.filter(department_id=department.pk, status__in=(
            OpeningBalanceBatch.FOR_REVIEW, OpeningBalanceBatch.APPROVED, OpeningBalanceBatch.POSTED,
        )).filter(Q(created_by_id=user.pk) | Q(submitted_by_id=user.pk)).select_related("period")
        for item in openings:
            queue, received = {
                item.FOR_REVIEW: ("Independent opening-balance reviewers", item.submitted_at),
                item.APPROVED: ("Opening-balance posters", item.approved_at),
                item.POSTED: ("Opening-balance reconciliation", item.posted_at),
            }[item.status]
            add(item, kind="opening-batch", area="Accounting", reference=item.source_reference,
                subject=item.title, received=received, queue=f"{queue} - {department.name}",
                scope=f"{department.name}; {item.period}", route="accounting:opening_detail",
                attribution=[item.created_by_id, item.submitted_by_id])
        closes = PeriodCloseRun.objects.filter(department_id=department.pk, status=PeriodCloseRun.SUBMITTED).filter(
            Q(prepared_by_id=user.pk) | Q(submitted_by_id=user.pk),
        ).select_related("period")
        for item in closes:
            add(item, kind="period-close", area="Accounting", reference=f"{item.period} v{item.version}",
                subject="Submitted period-close checklist", received=item.submitted_at,
                queue=f"Independent period-close reviewers - {department.name}",
                scope=f"{department.name}; {item.period}", route="accounting:period_close_detail",
                attribution=[item.prepared_by_id, item.submitted_by_id])

    if can_view_workbench(user) and has_explicit_permission(user, "vouchers.view_bank_advice"):
        advice = visible_bank_advice_batches(user).filter(status__in=(
            BankAdviceBatch.FOR_REVIEW, BankAdviceBatch.APPROVED, BankAdviceBatch.SUBMITTED,
        )).filter(Q(created_by_id=user.pk) | Q(review_submitted_by_id=user.pk) | Q(bank_submitted_by_id=user.pk))
        for item in advice:
            queue, received = {
                item.FOR_REVIEW: ("Independent Accounting advice reviewers", item.review_submitted_at),
                item.APPROVED: ("Authorized bank-submission officers", item.approved_at),
                item.SUBMITTED: ("Accounting bank-response officers", item.bank_submitted_at),
            }[item.status]
            add(item, kind="bank-advice", area="Bank advice", reference=item.advice_number,
                subject="Submitted bank-advice batch", received=received, queue=queue,
                scope=f"{item.accounting_department}; bank {item.bank_account_code}", route="vouchers:advice_detail",
                attribution=[item.created_by_id, item.review_submitted_by_id, item.bank_submitted_by_id])
    remittance_read = any(has_explicit_permission(user, permission) for permission in (
        "vouchers.view_remittance_workbench", "vouchers.prepare_remittances", "vouchers.approve_remittances",
        "vouchers.release_remittances", "vouchers.view_remittance_audit",
    ))
    if can_view_workbench(user) and remittance_read:
        batches = visible_remittance_batches(user).filter(status__in=(
            TreasuryRemittanceBatch.FOR_REVIEW, TreasuryRemittanceBatch.APPROVED, TreasuryRemittanceBatch.ACCOUNTING_POSTING,
        )).filter(Q(created_by_id=user.pk) | Q(submitted_by_id=user.pk) | Q(released_by_id=user.pk, status=TreasuryRemittanceBatch.ACCOUNTING_POSTING)).select_related("treasury_department")
        for item in batches:
            queue, received = {
                item.FOR_REVIEW: (f"Accounting remittance reviewers - {item.finance_department_label}", item.submitted_at),
                item.APPROVED: (f"Treasury release officers - {item.treasury_department}", item.reviewed_at),
                item.ACCOUNTING_POSTING: (f"Accounting posting officers - {item.finance_department_label}", item.released_at),
            }[item.status]
            add(item, kind="treasury-remittance", area="Treasury", reference=item.reference_code,
                subject="Released remittance awaiting Accounting posting" if item.status == item.ACCOUNTING_POSTING else "Submitted remittance schedule",
                received=received, queue=queue, scope=f"{item.treasury_department}; fund {item.fund_code}", route="vouchers:remittance_detail",
                attribution=[item.created_by_id, item.submitted_by_id, item.released_by_id])
    return tasks
