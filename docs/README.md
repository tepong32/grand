# GRAND documentation

Use this page as the entry point for project and operator documentation.

## Start here

- [Project overview and local setup](../README.md) describes the product, application boundaries, development commands, and verification gates.
- [Reporting operations](REPORTING.md) explains approved datasets, familiar-template onboarding, generation, scheduling, permissions, and audit behavior.
- [Portable GRAND export archive](EXPORT_ARCHIVE.md) defines the one-root department/user/category layout, atomic artifacts, checksum manifests, and TraceSync operating boundary.
- [Database backup and recovery](DATABASE_BACKUP.md) defines the separate restricted two-store backup root, native MySQL logical dumps, atomic completed sets, retention safeguards, off-host verification, and isolated restore-rehearsal gate.
- [Production Docker and Render preparation](DEPLOYMENT_RENDER.md) defines the non-root container, health/static/logging contract, two-store environment, configuration/live preflight receipts, persistent-file boundary, migration sequence, Render scheduling constraint, and still-unresolved infrastructure decisions.
- [Department Internal How-Tos](INTERNAL_HOWTOS.md) defines the floating non-modal guidance window, live department/role visibility, private progress, succession behavior, and governed publishing.
- [Department report-template intake](REPORT_TEMPLATE_INTAKE.md) provides the artifact checklist, compatibility decision, pilot comparison, and print/download rules used before official validation.
- [Department records operations](RECORDS.md) explains source-in-place filing, permissions, approval, retention, legal holds, controlled downloads, and disposition.
- [TracePoint physical custody](TRACEPOINT.md) defines packet identity, daily employee credentials, confirmed handoffs, delivery/completion semantics, security boundaries, and the `0.6.x` delivery train.
- [Finance Setup Center](FINANCE_SETUP.md) defines finance roles, effective-dated configuration, readiness, safe Excel intake, approval, activation, and domain boundaries.
- [GRAND Finance complete-cycle roadmap](FINANCE_ROADMAP.md) is the canonical delivery plan from annual budget preparation through appropriation, allotment, obligation, DV, wet-signature custody, accounting, payment, reporting, reconciliation, and cutover.
- [Finance obligation control and RAAO-equivalent registry](FINANCE_OBLIGATION_CONTROL.md) explains requesting-office initiation, Budget certification, balance protection, modification limits, portable exports, and remaining local form acceptance.
- [Finance payable intake and obligation handoff](FINANCE_PAYABLE_INTAKE.md) explains F5.1 certified-obligation selection, payable evidence, recoverable cross-database linkage, modification boundaries, and remaining F5 work.
- [Finance transaction variants and payable readiness](FINANCE_PAYABLE_VARIANTS.md) explains F5.2 typed variants, authority-backed documentary rules, requesting-office checklists, independent Accounting acceptance/return, and versioned role guidance.
- [Finance payable relationships, recognition decisions, and transaction exports](FINANCE_PAYABLE_RELATIONSHIPS.md) explains F5.3 one-to-many/many-to-one/partial/progress/final controls, guided pre-DV revisions, Accounting decisions, and TraceSync-ready case exports.
- [Finance controlled DV printing and custody](FINANCE_CONTROLLED_PRINT_CUSTODY.md) explains F6.1 editable starter forms, checksum/versioned signing copies, recorded print evidence, TracePoint packet creation, wet-signature gates, reasoned reprints, and remaining local acceptance.
- [Finance transaction posting rules and governed JEV handoff](FINANCE_TRANSACTION_POSTING_RULES.md) explains F7.1 editable event rules, recognition timing, immutable rule snapshots, balanced JEV materialization, correction boundaries, and portable ledger/trial-balance exports.
- [Finance payable and withholding subsidiary controls](FINANCE_SUBSIDIARY_CONTROLS.md) explains F7.2 immutable claimant/payee and deduction detail, reversal lineage, GL control reconciliation, role guidance, and TraceSync-ready evidence exports.
- [Finance payment-event posting and portable register](FINANCE_PAYMENT_EVENT_POSTING.md) explains F7.3 payment-release JEVs, explicit cancellation/replacement no-entry decisions, exact workflow resume, draft recovery, starter policies, and TraceSync-ready instrument evidence.
- [Finance period close and controlled reopen](FINANCE_PERIOD_CLOSE.md) explains F7.4 human-modifiable close policies, checksummed evidence, maker–checker close, ordered reopen, floating guidance, and TraceSync-ready exports.
- [Finance deduction and withholding remittance execution](FINANCE_REMITTANCE_EXECUTION.md) explains F8.1 cross-voucher posted-balance selection, reasoned pre-release revisions, independent review, actual-release evidence, liability-reducing JEVs, recovery, Internal How-Tos, and TraceSync-ready registers.
- [Finance bank-statement intake and reconciliation](FINANCE_BANK_RECONCILIATION.md) explains F8.2/F8.5 checksummed statement versions, posted-GL matching, prior-item carry/clearance lineage, adjusted-balance timing items, zero-difference independent review, starter CSV, floating guidance, and TraceSync-ready evidence exports.
- [Finance accountability reporting](FINANCE_ACCOUNTABILITY_REPORTING.md) explains F9.1 Budget accountability and posted-trial-balance starters, local-applicability controls, immutable report evidence, source drill-through, reproduction receipts, floating guidance, and TraceSync-ready exports.
- [Finance operational report catalog](FINANCE_OPERATIONAL_REPORT_CATALOG.md) explains F9.2 Budget-versus-posted-actual mapping, posted general ledger, payable/withholding subsidiary controls, Treasury disbursement register, exception handling, and local-form/tax boundaries.
- [Finance statement controls](FINANCE_STATEMENT_CONTROLS.md) explains F9.3 governed statement mappings, financial-position/performance equations, explained measures, source drill-through, guidance, and acceptance boundaries.
- [Finance statement notes and signed-reference comparison](FINANCE_STATEMENT_NOTES.md) explains F9.4 editable disclosure packages, pinned statement evidence, independent working/official review, exact redacted-reference control comparison, guidance, exports, and the tax/form acceptance boundary.
- [Finance governed tax withholding capture and reporting](FINANCE_TAX_REPORTING.md) explains F9.5 plain-language locally governed tax rules, multi-line DV capture, immutable Accounting evidence, reconciled detail/summary source schedules, privacy, correction, guidance, export, and official-use boundaries.
- [Finance governed tax remittance and filing evidence](FINANCE_TAX_REMITTANCE_EVIDENCE.md) explains F9.6 tax-aware remittance allocations, guided approved-report evidence locking, the reasoned external-schedule fallback, independently reviewed filing/payment references, correction/amendment lineage, privacy, and TraceSync-ready evidence exports.
- [Finance accountability-package profiles and assembly](FINANCE_ACCOUNTABILITY_PACKAGES.md) explains F9.7 plain-language package recipes, cross-office approved evidence slots, maker–checker assembly, reasoned selection/profile/package successors, source-reversal boundaries, and TraceSync manifests.
- [F9 comprehensive review and implementation handoff](FINANCE_F9_REVIEW_AND_HANDOFF.md) records the F9.1–F9.7 control review, parent-gate boundary, and recommended F10/F11 field-acceptance train.
- [Finance visual template promotion and rollback](FINANCE_TEMPLATE_PROMOTION.md) explains F10.1 retained previews, golden checks, human layout comparison, schedule impact, independent promotion, deployment-free activation, rollback, guidance, and TraceSync receipts.
- [Finance local-form inventory and acceptance](FINANCE_LOCAL_FORM_ACCEPTANCE.md) explains the F10.2 in-app 31-form DBM candidate catalog, locally resolved dynamic sections, independently witnessed practical tests, maker–checker acceptance, reasoned successors, historical schema compatibility, and portable evidence.
- [Finance field-acceptance starter pack](finance-field-acceptance/README.md) provides the editable DBM-form inventory, candidate field mappings, COA documentary-rule intake, practical-test sheets, field-cycle plan, decisions, and structured recovery worksheet used to prepare actual F10/F11 evidence without claiming local acceptance.
- [Finance shadow operation, UAT acceptance, and controlled cutover](FINANCE_SHADOW_CUTOVER.md) explains F11.1–F11.8 transition controls: source staging/drift review, locally approved cadence, scheduled reconciliation snapshots, defect escalation/resolution, curriculum/support planning, independently witnessed role/nonfunctional exercises, consecutive field-cycle qualification, exact F10.2 accepted-form lineage, structured two-store recovery evidence, the field-acceptance coordination board, retained signed-decision references, seven-party acceptance, explicit authority, rollback, floating guidance, and TraceSync evidence.
- [Finance Field Acceptance Board](FINANCE_FIELD_ACCEPTANCE_BOARD.md) explains the ten plain-language checkpoints, role-bounded cycle access, truthful percentage/authority boundary, correction behavior, and audited TraceSync-ready CSV status index.
- [Finance roadmap completion audit](FINANCE_ROADMAP_COMPLETION_AUDIT.md) maps F0–F11 software evidence to the still-required LGU field proof and orders the remaining work without claiming production authority.
- [Finance cross-cycle synthetic replay](FINANCE_CROSS_CYCLE_REPLAY.md) records the automated one-case F2–F9 integration checkpoint from maker–checker fiscal readiness and reconciled opening balances through authorized appropriation, payable/DV, recognition and payment JEVs, acknowledged release, zero-difference bank reconciliation, and the controlled Treasury register, together with the remaining field-acceptance boundary.
- [Finance cash position and instrument ageing](FINANCE_CASH_POSITION.md) explains F8.3 locally reviewable Observe/Enforce policies, reconciliation-backed positions, issue reservations, reasoned successor corrections, unclaimed/stale/returned evidence, planning starter, floating guidance, and TraceSync-ready exports.
- [Finance bank advice and returned instruments](FINANCE_BANK_ADVICE.md) explains F8.4 retained multi-case advice versions, independent review, actual submission and acknowledgement gates, reasoned successors, returned-payment Accounting/reissue orchestration, starter CSV, guidance, and portable evidence.
- [eGAPS-to-GRAND finance modernization plan](EGAPS_GRAND_PLAN.md) records the read-only findings, separate-database architecture, workflow and CRUD contract, no-code Excel Template Studio, and phased prototype-to-cutover plan.
- [Finance process discovery protocol](FINANCE_PROCESS_DISCOVERY.md) defines the redacted voucher replay, office interview, evidence, comparison, and acceptance procedure used before claiming process fidelity.
- [Finance evidence register and interview kit](finance-discovery/README.md) provides repository-safe F0.1 templates for evidence, transaction variants, roles/signatures, actual steps, decisions, and redacted synthetic replay.
- [Finance decisions and evidence register](FINANCE_DISCOVERY_DECISIONS.md) explains the F0.2–F0.5 evidence labels, cross-office ownership/review, editable cycle coverage starters, acceptance examples, exact-scope blockers, immutable successors, role-bounded triage, cutover gates, floating guidance, and per-record/filtered-department TraceSync exports.
- [Initial COA/DBM official-source register](finance-discovery/OFFICIAL_SOURCE_REGISTER.md) maps public budget, accounting, documentary, form, and internal-control references to roadmap slices while keeping applicability questions explicit.
- [Complete-cycle Finance information architecture](finance-ia/README.md) defines the F1.1 role, workspace, case/timeline/search, status, responsive, and clickable synthetic-prototype contract.
- [Finance fiscal-year and classification foundation](FINANCE_FISCAL_FOUNDATION.md) documents the F2.1 typed year, calendar, effective-dated classifications, readiness layers, setup-release adoption, and synthetic acceptance procedure.
- [Finance opening balances and control-total intake](FINANCE_OPENING_BALANCES.md) documents the F2.2 staged import, reasoned correction, independent approval, opening-JEV posting, reconciliation, and controlled export workflow.
- [Finance annual budget preparation](FINANCE_ANNUAL_BUDGET.md) documents F3.1 calls, ceilings, classified proposals and targets, resource estimates, consolidation, review, comparison, and the non-spendable authority boundary.
- [Finance allotment release control](FINANCE_ALLOTMENT_CONTROL.md) documents F4.1 release/reserve/deferral/adjustment movements, balance locks, independent posting, correction lineage, and portable schedules.
- [Finance process fidelity baseline](FINANCE_PROCESS_FIDELITY_BASELINE.md) maps the full annual-budget-to-close cycle to current GRAND coverage, evidence still required, and the complete-cycle and voucher-subcycle divergences.
- [Product roadmap](ROADMAP.md) records completed platform phases and points to the canonical long-term Finance delivery train.
- [Security maintenance](../SECURITY.md) covers dependency auditing, CI checks, Dependabot, and bundled browser assets.
- [Change history](../CHANGELOG.md) summarizes material delivered work.

## Showcase assets

The [portfolio screenshot guide](../output/playwright/grand-portfolio/README.md) and its `manifest.json` describe the reproducible synthetic UI captures. These assets contain no production citizens or official records.

## Operating principles

- Department membership is a boundary, not merely a filter. Explicit permissions do not grant access to another department's records.
- Public service flows and employee processing workspaces remain separate.
- Planned modules do not display fabricated links, records, or statistics.
- Citizen-service frequency is operational history, not a fraud score or eligibility decision.
- Uploaded report examples are non-executable references. Approved native layouts generate official outputs.
- Generated reports are not official until the required review and approval steps are complete.
- Existing operational files are referenced in place when filed as records; GRAND does not create a second authoritative copy.
- Disposition requires an archived, due record with no legal hold, and records the decision without pretending to perform physical destruction.
- A TracePoint scan identifies a packet or employee credential; only an authenticated, confirmed receipt changes custody.
- TracePoint delivery records physical arrival. Completion is a separate authorization that records finished work.
- Finance configuration must pass a separate local Accounting approval and readiness gate; platform administration alone cannot activate financial policy.
- An approved budget, released allotment, recorded obligation, accounting recognition, and cash disbursement are distinct authorities and balances.
- A finance screen is not complete merely because it is implemented; the applicable roadmap exit gate and process-owner evidence are required before official use.
- Local databases, uploaded citizen files, secrets, and generated official reports do not belong in source control.
