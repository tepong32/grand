# GRAND product roadmap

This file records the platform-level delivery history and product direction. Each implementation phase uses a dedicated `codex/` branch, tests, synthetic showcase data, portfolio screenshots, review, CI, and merge into `master`. See the [documentation map](README.md) for operator and project guides.

## Completed - Professional, configurable civic UI

- Use plain-language, task-oriented public and employee navigation.
- Preserve GRAND's institutional identity while keeping branding neutral across changes in administration.
- Let authorized administrators configure the institution name, portal labels, colors, logo, hero image, optional official media, footer text, service-card labels, icons, links, and ordering.
- Remove fabricated links, campaign-specific content, and shared-template assumptions that every authenticated user is an employee.
- Verify responsive layouts, keyboard navigation, readable contrast, real workflows, and portfolio screenshots.

## Completed - Citizen profiles, review, and service history

- Continue using the existing `CitizenProfile` as the canonical citizen identity; do not create a parallel identity table.
- Provide a permission-restricted review queue/table with search, sorting, pagination, review state, assigned reviewer, review notes, review timestamps, and audit history.
- Show assistance usage through neutral operational measures: total requests, active requests, last request date, assistance types used, status distribution, and request frequency by period.
- Add duplicate-candidate indicators using carefully normalized identifiers while requiring human review before records are linked or merged.
- Never treat frequent usage as fraud, ineligibility, or a risk score. Keep labels factual and explainable.
- Restrict PII columns, exports, notes, and cross-department visibility through explicit permissions; test privacy boundaries and object-level access.
- Design a reusable service-participation contract so future permits, appointments, programs, complaints, registrations, and other approved government services can contribute history without coupling citizen identity to Assistance.
- Define consent, correction, retention, archival, and merge/unmerge behavior before exposing citizen-facing registration or cross-service analytics.

The first delivery uses Assistance as the only service-history provider. The review workflow and stable operational profile remain intentionally separate from eligibility decisions, and future service integrations must use an approved adapter rather than creating another citizen identity table.

## Completed - Configurable reporting automation

- Provide department-bounded report definitions over an allowlisted dataset registry; never accept arbitrary SQL, Python, macros, or executable templates.
- Preserve familiar departmental PDF, spreadsheet, document, and scanned forms as non-executable references that require mapping and approval.
- Generate PDF, XLSX, and CSV with exact template versions, parameters, checksums, manual and recurring runs, safe retries, and auditable review and approval.
- Pilot five real MSWD presets for Assistance volume, accomplishments, aggregate reach, schedules, and workload.
- Retain failures and superseded approvals without deleting preceding official files or history.

## Completed - Native template fidelity controls

- Separate technical approval for pilot generation from evidence-backed department validation for official use.
- Configure versioned paper size, orientation, margins, page borders, repeating headers, logos, footers, page numbers, document-control identifiers, and signatories.
- Block pilot outputs from official approval while allowing authorized side-by-side comparison.
- Show Print only for archived PDFs and Download only for authorized archived outputs.

## Completed - Existing-template compatibility

- Preserve macro-free departmental XLSX forms through fixed, reviewed named ranges without destroying formatting, formulas, print areas, or neighboring cells.
- Preserve exact PDF pages and overlay only allowlisted report metadata, dataset fields, and configured totals at reviewed coordinates.
- Require checksum-backed preflight before approval and invalidate evidence after any mapping change.
- Lock approved source files and mappings, snapshot mapper evidence into every run, and reject incompatible output formats before generation or scheduling.
- Keep DOCX and image uploads as intake evidence rather than introducing a fragile desktop-office rendering dependency.

## Completed - Records and document workflows

- Attach supporting records to programs, activities, citizen service history, and generated reports.
- Add retention, review, approval, supersession, controlled exports, and department-bounded access.
- Allow approved report runs to become official departmental records without losing their report configuration, checksum, or audit history.
- Preserve existing operational files in place and store only typed references so Assistance and Reporting remain authoritative.
- Record controlled downloads, confidentiality boundaries, legal holds, retention due dates, and disposition decisions in an audit ledger.

## Completed - TracePoint physical-document custody

- Tag each physical paper/report bundle with one stable, opaque packet QR.
- Issue active employees random, revocable daily QR credentials without exposing identity data in the code.
- Require a visible confirmation step before an append-only, atomic custody transfer is recorded.
- Let preparers declare the final department or employee while preserving the actual, flexible intermediate route.
- Treat delivery to the destination and completion of the underlying work as separate audited events.
- Link physical packets to governed Records and approved report runs without copying or weakening access to their authoritative files.
- Keep TracePoint codes separate from Assistance secure-link QR codes and preserve GRAND as the platform identity.
- Deliver the capability through the reviewed `0.6.x` patch train documented in [TracePoint physical custody](TRACEPOINT.md).

The `0.6.0` through `0.6.6` train now includes the operating workspace, print labels, daily-code presentation, shared-station confirmation, individual voucher manifests, controlled bundle splitting/rebundling, repeatable office checkpoints, deliberate terminal receipt, department dashboard indicators, exception controls, automated regressions, and synthetic portfolio evidence. Production rollout should begin with a small inter-office pilot and written receiving procedure before expanding LGU-wide.

## Completed - Finance Setup Center foundation

- Govern future voucher configuration through effective-dated releases and stable, retire-not-delete versions.
- Separate Finance Configuration Manager preparation from Finance Configuration Approver review and activation; retain an append-only event history even for superusers.
- Cover transaction/payee/fund/responsibility/payment/account/obligation/tax/document/routing/confidentiality configuration without inventing authoritative defaults.
- Govern signatory validity, acting assignments, and fiscal-year/document numbering without issuing transaction numbers in setup.
- Accept macro-free `.xlsx` voucher templates with reviewed workbook names, checksums, print-area/row-capacity validation, external-link and suspicious-formula rejection, and synthetic-only preview.
- Explain incomplete official readiness through stable reason codes and block activation until every applicable requirement passes.

## Completed - Voucher Workbench vertical slice

- Use one shared, state-versioned disbursement case across Budget OBR allocation, Accounting DV preparation, wet-signature return, Accounting validation/JEV reference, Treasury checks, Accounting advice, and Treasury release.
- Select transaction types, codes, signatories, suppliers, payees, bank accounts, and authorized claimants from pinned, approved Finance Setup data while preserving historical snapshots.
- Enforce explicit financial permissions, segregation of duties, separately approved emergency overrides, atomic numbering, check-number non-reuse, monetary reconciliation, correction rounds, and append-only events.
- Generate checksum-backed shadow DV workbooks and preserve strict boundaries with TracePoint custody, Records, MPDO, and other departmental apps.
- Keep official use, exact remaining-budget authority, full JEV posting, and direct check printing blocked until their local evidence and validation requirements are met.

The vertical slice proves that one shared Budget–Accounting–Treasury case can work in GRAND. It does not prove the complete LGU cycle or authorize official use.

## Planned - GRAND Finance complete cycle

The [GRAND Finance complete-cycle roadmap](FINANCE_ROADMAP.md) is the canonical plan for the long-term Finance sub-application. It replaces the earlier assumption that the next material step is only an ordinary-supplier voucher pilot.

The essential delivery order is:

1. governance, evidence, local authority, terminology, roles, and audit foundation;
2. governed finance master data, fiscal-year readiness, and reconciled opening balances;
3. annual budget preparation, authorization, review, and approved appropriations;
4. allotment releases, ALOBS/ORS/OBR, the obligation registry, and authoritative balance control;
5. transaction-specific request, procurement/delivery, payable, and DV workflows;
6. controlled printing, wet-signature rounds, and mandatory physical-custody evidence;
7. accounting recognition, JEVs, posting, ledgers, period control, and corrections;
8. cash control, checks/payment instruments, advice, release, remittance, and bank reconciliation;
9. statutory reports, financial statements, governed templates, shadow comparison, training, and explicit cutover.

Existing Finance Setup, Accounting, Voucher Workbench, Reporting, Records, and TracePoint features are foundations to extend, not separate replacement systems. Historical eGAPS migration remains optional and cannot block standalone GRAND operation.

F9.3 adds versioned maker–checker financial-statement mappings, exact non-zero account coverage, visible position/performance equations, pinned JEV drill-through, explained measures, and contextual Accounting guidance. F9.4 adds governed statement-note packages and exact checksummed signed/redacted-reference control comparison. Exact forms/layouts, current accepted tax outputs, complete signed-package replay, and named-office acceptance remain open.

F7.4 closes the earlier period-control dependency with human-modifiable Observe/Enforce policies, pinned close evidence, independent approval, source-drift detection, ordered governed reopen, contextual Accounting guidance, and TraceSync-ready exports. Exact locally accepted close calendars, adjusting/closing-entry procedures, supporting schedules, signed outputs, and named-office replay remain open.

F5.1 supplies the authoritative obligation-to-payable/voucher handoff for a synthetic ordinary-supplier case. F5.2 adds configurable transaction variants, pinned documentary rules, requesting-office decisions, and independent Accounting accept/return. F5.3 adds versioned allocation relationships, recognition/adjustment decisions, exact claim controls, guided pre-DV corrections, and portable transaction exports. F6.1 adds editable starter templates, controlled print versions/reprints, TraceSync archive evidence, mandatory TracePoint packet creation, configured signature-custody checkpoints, and returned-packet gates. F7.1 adds locally reviewable transaction/event posting rules, immutable rule-backed JEV handoffs, duplicate-recognition guards, and portable posted-ledger/trial-balance exports. F7.2 adds immutable payable/withholding subsidiary movements, reversal lineage, dated control reconciliation, and portable evidence. F7.3 adds payment-release JEV orchestration, explicit cancellation/replacement no-entry decisions, exact Treasury-stage resume, and portable payment registers. F7.4 adds governed close policies, checksummed evidence, independent close, and ordered reopen. F8.1 adds controlled cross-voucher deduction/withholding remittance schedules, pre-release revisions, independent review, actual-release JEV posting, and portable registers. F8.2 adds checksummed monthly bank-statement versions, exact/guided posted-GL matching, adjusted-balance timing evidence, zero-difference independent reconciliation, starter CSV, and portable evidence. F8.3 adds locally reviewable Observe/Enforce cash policies, reconciliation-backed positions, issue reservations, configurable instrument ageing, floating guidance, a planning starter, and portable evidence. F8.4 adds retained multi-case advice review/submission/bank response, acknowledgement-gated release, reasoned successors, and returned-payment Accounting/reissue orchestration. F8.5 adds prior-reconciled timing-item carry-forward, ageing, later clearance, and reasoned reopening. F9.1 adds controlled Budget accountability and posted-trial-balance starters, explicit local-applicability gates, source drill-through, immutable evidence, and reproduction receipts. F9.2 adds exact-key Budget-versus-actual mapping, posted general-ledger and subsidiary schedules, and a Treasury disbursement register with control-gated incomplete-source handling. F9.3 adds governed statement composition, and F9.4 adds note packages plus signed-reference control comparison. Accepted rules/forms/tax outputs/thresholds, complete signed reference outputs, consecutive redacted replay, and named-office paper/printer/accounting acceptance remain mandatory before official use.
