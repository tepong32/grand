# GRAND documentation

Use this page as the entry point for project and operator documentation.

## Start here

- [Project overview and local setup](../README.md) describes the product, application boundaries, development commands, and verification gates.
- [Reporting operations](REPORTING.md) explains approved datasets, familiar-template onboarding, generation, scheduling, permissions, and audit behavior.
- [Portable GRAND export archive](EXPORT_ARCHIVE.md) defines the one-root department/user/category layout, atomic artifacts, checksum manifests, and TraceSync operating boundary.
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
- [Finance deduction and withholding remittance execution](FINANCE_REMITTANCE_EXECUTION.md) explains F8.1 cross-voucher posted-balance selection, reasoned pre-release revisions, independent review, actual-release evidence, liability-reducing JEVs, recovery, Internal How-Tos, and TraceSync-ready registers.
- [eGAPS-to-GRAND finance modernization plan](EGAPS_GRAND_PLAN.md) records the read-only findings, separate-database architecture, workflow and CRUD contract, no-code Excel Template Studio, and phased prototype-to-cutover plan.
- [Finance process discovery protocol](FINANCE_PROCESS_DISCOVERY.md) defines the redacted voucher replay, office interview, evidence, comparison, and acceptance procedure used before claiming process fidelity.
- [Finance evidence register and interview kit](finance-discovery/README.md) provides repository-safe F0.1 templates for evidence, transaction variants, roles/signatures, actual steps, decisions, and redacted synthetic replay.
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
