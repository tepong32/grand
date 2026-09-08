from __future__ import annotations

from uuid import UUID

from django.db.models import Exists, F, OuterRef, Q, Subquery
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
    from .work_tasks import FinanceWorkTask, _age_days, _projection_checksum, _source_record_identity, _due_state

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

    def add(item, *, kind, area, reference, subject, received, queue, scope, route, attribution, source_id=None, route_kwargs=None, due_on=None, status=None, status_label=None, fragment=""):
        status = status if status is not None else item.status
        status_label = status_label if status_label is not None else item.get_status_display()
        source_id = source_id if source_id is not None else item.public_id
        identity = f"{kind}:{source_id}"
        if identity in actionable:
            return
        missing_time = received is None
        revision = _projection_checksum({
            "identity": identity, "status": status, "attribution": attribution,
            "received": received.isoformat() if received else None,
            "scope": scope, "queue": queue,
            "version": getattr(item, "state_version", getattr(item, "version", None)),
            "reference": reference, "subject": subject, "due_on": due_on.isoformat() if due_on else None,
        })
        tasks.append(FinanceWorkTask(
            task_id=f"finwork:v1:{identity}:waiting", task_type=f"finance.{kind}.waiting.v1",
            area=area, case_id=identity, reference=reference, subject=subject,
            transaction_type=item._meta.verbose_name.title(), action="View submitted work",
            gate="You prepared or submitted this record. Its current handoff is with the named queue; no supported action on this record is available to you now.",
            owner_queue=queue, scope=scope, received_at=received,
            due_on=due_on, due_state=_due_state(due_on, today) if due_on else "No structured target",
            calendar_basis="Retained local review target for the named reviewer; age is elapsed calendar days since handoff. No working-day adjustment inferred." if due_on else "Elapsed calendar days since the retained handoff; document and ledger dates are not deadlines.",
            age_days=_age_days(received, today), state="Waiting", source_state=status_label,
            source_version=f"projection-sha256:{revision}",
            exception="The source has no retained handoff time; age is unavailable." if missing_time else "",
            url=reverse(route, kwargs=route_kwargs if route_kwargs is not None else {"public_id": item.public_id}) + fragment,
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

    from .access import can_view_finance_discovery_decision
    from .discovery_register import visible_discovery_decisions
    from .models import FinanceDiscoveryDecision

    decisions = visible_discovery_decisions(user).filter(status=FinanceDiscoveryDecision.SUBMITTED).filter(
        Q(created_by_id=user.pk) | Q(submitted_by_id=user.pk),
    )
    for item in decisions:
        if not can_view_finance_discovery_decision(user, item):
            continue
        add(item, kind="discovery-decision", area="Finance decisions", reference=f"{item.code} v{item.version} · {item.phase}",
            subject=item.question, received=item.submitted_at, queue=f"Named decision reviewer - {item.reviewer.get_username()}",
            scope=f"{item.department.name}; {item.affected_scope}", route="finance:discovery_decision_detail",
            attribution=[item.created_by_id, item.submitted_by_id], due_on=item.due_date)

    from vouchers.case_exports import visible_cases_for_user
    from vouchers.models import BankAdviceItem, PayableIntake, PaymentInstrument, ReturnedInstrumentReview, VoucherCase, VoucherEvent, VoucherPostingRequest, WetSignatureTask

    if can_view_workbench(user):
        processing_stages = (VoucherCase.AWAITING_SIGNATURES, VoucherCase.ACCOUNTING_VALIDATION, VoucherCase.ACCOUNTING_POSTING,
                     VoucherCase.TREASURY_CHECK_PREPARATION, VoucherCase.ACCOUNTING_BANK_ADVICE,
                             VoucherCase.TREASURY_RELEASE, VoucherCase.ACCOUNTING_EVENT_POSTING)
        actionable.update(f"voucher-case:{case_id}" for case_id in identities("voucher:"))
        actionable.update(
            f"voucher-case:{case_id}" for case_id in BankAdviceItem.objects.filter(
                batch__public_id__in=identities("bank-advice:"), instrument__current_advice_batch_id=F("batch_id"),
            ).values_list("instrument__case__public_id", flat=True)
        )
        actionable.update(
            f"voucher-case:{case_id}" for case_id in ReturnedInstrumentReview.objects.filter(
                public_id__in=identities("returned-payment:"),
            ).values_list("case__public_id", flat=True)
        )
        issued = PaymentInstrument.objects.filter(
            case_id=OuterRef("pk"), issued_by_id=user.pk, status__in=(PaymentInstrument.ISSUED, PaymentInstrument.ADVISED),
        )
        voucher_source_ids = identities("voucher-source:")
        if journal_ids:
            for reference in JournalEntry.objects.filter(public_id__in=journal_ids, source_type="voucher").values_list("source_reference", flat=True):
                try:
                    voucher_source_ids.add(UUID(str(reference)))
                except (ValueError, TypeError, AttributeError):
                    continue
        actionable.update(
            f"voucher-case:{case_id}" for case_id in VoucherPostingRequest.objects.filter(
                public_id__in=voucher_source_ids,
            ).values_list("case__public_id", flat=True)
        )
        requested = VoucherPostingRequest.objects.filter(
            case_id=OuterRef("pk"), kind=VoucherPostingRequest.RECOGNITION, requested_by_id=user.pk,
            status__in=(VoucherPostingRequest.PENDING, VoucherPostingRequest.MATERIALIZED, VoucherPostingRequest.FAILED),
        )
        event_requested = VoucherPostingRequest.objects.filter(
            case_id=OuterRef("pk"), requested_by_id=user.pk,
            kind__in=(VoucherPostingRequest.PAYMENT, VoucherPostingRequest.REMITTANCE, VoucherPostingRequest.CANCELLATION,
                      VoucherPostingRequest.REPLACEMENT, VoucherPostingRequest.REVERSAL),
            status__in=(VoucherPostingRequest.PENDING, VoucherPostingRequest.MATERIALIZED, VoucherPostingRequest.FAILED),
        )
        intake_owner = Q(payable_intake__prepared_by_id=user.pk) | Q(payable_intake__submitted_by_id=user.pk)
        handoffs = VoucherEvent.objects.filter(
            case_id=OuterRef("pk"), to_stage=OuterRef("current_stage"),
        ).exclude(from_stage=F("to_stage")).order_by("-state_version", "-created_at", "-pk")
        cases = visible_cases_for_user(user).annotate(_work_posting_requester=Exists(requested), _work_instrument_issuer=Exists(issued),
                                                            _work_event_requester=Exists(event_requested)).filter(
            (Q(current_stage=VoucherCase.PAYABLE_REVIEW, payable_intake__status=PayableIntake.FOR_REVIEW)
             | Q(current_stage=VoucherCase.ACCOUNTING_PREPARATION, payable_intake__status=PayableIntake.READY)) & intake_owner
            | Q(current_stage__in=processing_stages, disbursement_voucher__isnull=False)
            & (intake_owner | Q(disbursement_voucher__prepared_by_id=user.pk)
               | Q(current_stage=VoucherCase.ACCOUNTING_POSTING, _work_posting_requester=True)
               | Q(current_stage__in=(VoucherCase.ACCOUNTING_BANK_ADVICE, VoucherCase.TREASURY_RELEASE), _work_instrument_issuer=True)
               | Q(current_stage=VoucherCase.ACCOUNTING_EVENT_POSTING, _work_event_requester=True)),
        ).select_related(
            "payable_intake", "disbursement_voucher", "requesting_department", "current_department",
        ).annotate(_work_handoff_at=Subquery(handoffs.values("created_at")[:1]))
        # Only already-authorized child actions suppress the parent handoff.
        # Resolve this before the caller applies its display limit.
        for task_pk, case_id in WetSignatureTask.objects.filter(case__in=cases).values_list("pk", "case__public_id"):
            if f"wet-signature:{_source_record_identity('wet-signature', task_pk)}" in actionable:
                actionable.add(f"voucher-case:{case_id}")
        for item in cases:
            intake = getattr(item, "payable_intake", None)
            voucher = getattr(item, "disbursement_voucher", None)
            office = item.current_department.name if item.current_department else "office assignment missing"
            attribution = [intake.prepared_by_id, intake.submitted_by_id] if intake else []
            if item.current_stage in processing_stages:
                attribution.append(voucher.prepared_by_id)
                received = item._work_handoff_at
                queue = {
                    VoucherCase.AWAITING_SIGNATURES: f"DV custody and signature return - {office}",
                    VoucherCase.ACCOUNTING_VALIDATION: f"Independent Accounting validation - {office}",
                    VoucherCase.ACCOUNTING_POSTING: f"Accounting journal preparation, posting and source synchronization - {office}",
                    VoucherCase.TREASURY_CHECK_PREPARATION: f"Treasury check preparation - {office}",
                    VoucherCase.ACCOUNTING_BANK_ADVICE: f"Accounting bank-advice preparation and response - {office}",
                    VoucherCase.TREASURY_RELEASE: f"Treasury claimant verification and check release - {office}",
                    VoucherCase.ACCOUNTING_EVENT_POSTING: f"Accounting event journal posting and source synchronization - {office}",
                }[item.current_stage]
                if (item.current_stage == VoucherCase.ACCOUNTING_POSTING and item._work_posting_requester
                        or item.current_stage in (VoucherCase.ACCOUNTING_BANK_ADVICE, VoucherCase.TREASURY_RELEASE) and item._work_instrument_issuer
                        or item.current_stage == VoucherCase.ACCOUNTING_EVENT_POSTING and item._work_event_requester):
                    attribution.append(user.pk)
            else:
                reviewing = item.current_stage == VoucherCase.PAYABLE_REVIEW
                received = intake.submitted_at if reviewing else intake.reviewed_at
                queue = f"Accounting payable reviewers - {office}" if reviewing else f"Accounting DV preparers - {office}"
            add(item, kind="voucher-case", area="Voucher case", reference=item.reference_code,
                subject=f"{item.payee_name} · {item.particulars}", received=received,
                queue=queue, scope=f"Requesting office: {item.requesting_department.name}; current processing office: {office}",
                route="vouchers:case_detail", attribution=attribution,
                status=item.current_stage, status_label=item.get_current_stage_display())

    if can_view_workbench(user) and has_explicit_permission(user, "vouchers.view_bank_advice"):
        from vouchers.returned_instrument_register import visible_returned_instrument_reviews

        reviews = visible_returned_instrument_reviews(user).filter(
            Q(status__in=(ReturnedInstrumentReview.AWAITING_REVIEW, ReturnedInstrumentReview.RETURNED_FOR_CLARIFICATION),
              case__current_stage=VoucherCase.ACCOUNTING_RETURNED_ITEM)
            | Q(status=ReturnedInstrumentReview.AWAITING_POSTING, case__current_stage=VoucherCase.ACCOUNTING_EVENT_POSTING)
            | Q(status=ReturnedInstrumentReview.READY_FOR_TREASURY, outcome=ReturnedInstrumentReview.REISSUE,
                case__current_stage=VoucherCase.TREASURY_CHECK_PREPARATION),
        ).filter(
            Q(prepared_by_id=user.pk)
            | Q(status=ReturnedInstrumentReview.AWAITING_POSTING, posting_request__requested_by_id=user.pk,
                posting_request__status__in=(VoucherPostingRequest.PENDING, VoucherPostingRequest.MATERIALIZED, VoucherPostingRequest.FAILED)),
        )
        for item in reviews:
            if f"voucher-case:{item.case.public_id}" in actionable:
                continue
            treasury = item.exception.policy.treasury_department.name
            accounting = item.case.configuration_release.department.name if item.case.configuration_release_id else "Accounting assignment missing"
            request = item.posting_request
            queue, received = {
                item.AWAITING_REVIEW: (f"Independent returned-payment review - {accounting}", item.prepared_at),
                item.RETURNED_FOR_CLARIFICATION: (f"Returned-payment clarification - {treasury}", item.reviewed_at),
                item.AWAITING_POSTING: (f"Returned-payment journal posting and synchronization - {accounting}", item.reviewed_at),
                item.READY_FOR_TREASURY: (f"Controlled replacement check preparation - {treasury}",
                                        request.posted_at if request and request.posted_at else item.reviewed_at),
            }[item.status]
            add(item, kind="returned-payment", area="Returned payment",
                reference=f"{item.case.reference_code} · check {item.instrument.check_number} · review v{item.version}",
                subject="Submitted returned-payment evidence", received=received, queue=queue,
                scope=f"{accounting}; Treasury: {treasury}; current source register access",
                route="vouchers:advice_workspace", route_kwargs={}, fragment=f"#returned-review-{item.public_id}",
                attribution=[item.prepared_by_id, request.requested_by_id if request else None])

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
