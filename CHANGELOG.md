# Changelog

Material GRAND changes are recorded here. The repository's Git history remains the detailed source of truth.

## Unreleased

### Department Internal How-Tos

- Added reusable department-scoped, permission-filtered, page-aware internal guides with ordered instructions, expected results, cautions, workspace links, draft/published/retired lifecycle, and immutable published versions.
- Added a persistent floating `?` button and responsive non-modal help window so employees can read a tutorial while continuing work on the current page.
- Added private per-user step progress while computing guide visibility live from the current employee department/role, preventing reassigned employees and successors from inheriting another user's tutorial state.
- Added department-bounded guide administration, protected asynchronous completion actions, repeatable Finance starter-guide seeding, and role-specific opening, journal, DV, Budget, Treasury, and setup tutorials.

### Finance opening balances and control totals

- Added F2.2 checksum-backed opening CSV staging with governed fund/account/center mapping, row and declared controls, exact batch and per-fund balancing, and explicit zero-balance declarations.
- Added reason-required row/control corrections, independent approval and pre-posting return, immutable per-fund opening JEV lineage, and a separate zero-difference reconciliation gate for fiscal readiness.
- Added department-scoped opening workspaces, guided actions, controlled CSV exports, dedicated Finance roles, synthetic regression coverage, and an operating/acceptance guide.
- Defined reusable Finance exports as scoped evidence/data interchange carrying stable lineage and context, without representing them as automatically approved official forms.

### Portable export archive

- Added one configurable `GRAND_EXPORT_ROOT` with normalized department/user/category/year/month folders suitable for whole-tree synchronization by TraceSync or another ordinary folder-copy tool.
- Added atomic, collision-resistant artifact retention and adjacent JSON manifests carrying SHA-256, size, export time, exporting identity, department, and source lineage.
- Connected controlled Finance opening CSV exports and generated report downloads to the archive while preserving their browser download and existing authorization boundaries.

### Finance fiscal-year and classification foundation

- Added the F2.1 typed fiscal year and business-date lifecycle in the isolated Finance store, with maker-checker approval, state versions, and append-only evidence.
- Added effective-dated funding sources and MFO/program/PPA/project/activity hierarchies plus stable UUID and account/office dimensions for existing ledger masters.
- Added independently evidenced technical, Budget, Accounting, Treasury, and forms readiness layers that block activation until structural checks and all decisions pass.
- Added checksum-pinned, idempotent adoption of approved Finance Setup releases and an additive migration path for existing periods and accounting masters.
- Added guided setup screens, explicit configuration-manager/approver roles, synthetic regression tests, and an F2.1 operating/acceptance guide.
- Added a reason-required guided modification allowance before any affected DV/check issuance; edits retain before/after evidence, reopen impacted readiness, and close in favor of successor/correction workflows after issuance.

### Finance evidence and interview foundation

- Added the F0.1 Finance evidence register and interview kit, including repository-safe authority, transaction, role/signature, actual-step, decision, redaction, and synthetic-replay templates.
- Added an initial COA/DBM official-source and template register, including effectivity/scope cautions for the 2023 LGU Budget Operations Manual, LGU NGAS/RCA materials, deferred 2020 GAM for LGUs, updated documentary requirements, and DV form lineage.

### Complete-cycle Finance information architecture

- Added the F1.1 role/permission, landing/My Work, shared case/timeline/search, notification, accessibility, responsive, and status-vocabulary contracts.
- Added a no-network clickable synthetic prototype with role-shaped queues, a complete-cycle authority chain, append-only timeline filters, authorized-search behavior, and explicit shadow/read-only context.

### GRAND Finance complete-cycle roadmap

- Added a canonical F0–F11 delivery and acceptance roadmap from annual budget preparation through appropriation, allotment, obligation, payable/DV, wet-signature custody, posting, payment, reporting, reconciliation, training, and cutover.
- Reclassified the existing Voucher Workbench as a reusable F5–F8 shadow vertical slice and recorded annual appropriation/allotment/obligation authority as the earliest complete-cycle gap.
- Expanded finance discovery and fidelity documentation to require reconciled budget, registry, ledger, payment, bank, report, physical-custody, correction, and transaction-variant evidence before claiming eGAPS equivalence or official use.
- Aligned Finance Setup, Accounting, Voucher Workbench, TracePoint, project roadmap, and documentation entry points to the same role-shaped complete-cycle destination.

### Standalone GRAND Accounting foundation

- Added a separately routed GRAND finance database with no eGAPS endpoint, credentials, database attachment, or runtime dependency.
- Added native accounting periods, funds, responsibility centers, chart of accounts, journal headers/lines, and append-only workflow events using cross-database-safe identity snapshots.
- Added guided accounting setup, department-scoped journal CRUD, balanced-entry validation, explicit submit/return/post actions, maker-checker posting, and immutable posted history.
- Added a task-first Accounting workspace, journal register/detail, general ledger, and trial balance with permission-aware navigation.
- Added multi-database, authorization, department-isolation, posting-integrity, immutability, HTTP-method, and reporting regression tests using synthetic values only.
- Connected validated Voucher Workbench cases to checksum-backed GRAND posting requests and idempotent draft JEV materialization in the standalone finance database, with controlled account mappings and recoverable handoff reconciliation.
- Added a dedicated Accounting posting queue and source-status guidance that advances Treasury only after independent JEV posting, while preventing posted vouchers from being silently rewritten.
- Added reason-required reversing JEVs that swap the original lines, retain direct correction lineage, preserve the posted source, and pass through the normal maker-checker workflow.
- Extended the synthetic end-to-end suite through Budget, voucher validation, GRAND ledger posting, Treasury advice, and final check release without any eGAPS connection or data.
- Added audited, permission-bound DV date and signatory amendments before check issuance, retaining the same case, DV number, amounts, and posted JEV while creating replacement signature and workbook versions.
- Blocked non-financial amendments after any check issuance and kept JEV dates, accounting periods, allocations, deductions, and amounts outside this convenience workflow.

### Voucher and Disbursement Workbench

- Added one shared Budget–Accounting–Treasury voucher case with explicit, state-versioned stages from OBR allocation through advised check release.
- Added governed supplier/payee and authorized-claimant setup alongside selectable transaction, account, fund, responsibility, tax, document, bank, and signatory data.
- Added atomic OBR/DV numbering, monetary reconciliation, ordered wet-signature rounds, JEV references, multiple checks, cancellation/non-reuse, bank advice, release, returns, and correction history.
- Added explicit financial permissions, segregation-of-duties enforcement, separately approved emergency overrides, idempotent actions, append-only events, and department work queues.
- Added checksum-backed shadow DV XLSX outputs plus Records and TracePoint boundaries that prevent shadow filing and financial-data leakage into physical custody.
- Added end-to-end and regression coverage for authorization, stale submissions, numbering, corrections, payment exceptions, output evidence, and cross-app isolation.

## 0.7.0 - 2026-08-21

### Finance Setup Center foundation

- Added department-bounded, effective-dated finance configuration releases with explicit preparation, separate Accounting approval, scheduling/activation states, supersession, retirement, and append-only audit snapshots.
- Added versioned finance master data and rules, validity-dated signatories, acting assignments, fiscal-year/document numbering policies, and retire-not-delete governance without creating a voucher transaction engine.
- Added stable readiness reason codes for approved templates, transaction checklists, signatories, funds/payment accounts, tax rules, numbering, and activation-date conflicts; incomplete releases cannot activate.
- Added macro-free `.xlsx` intake with controlled voucher named ranges, SHA-256 workbook/mapping evidence, print-area and line-capacity validation, macro/external-link/suspicious-formula rejection, and synthetic-only preview downloads.
- Added Finance Setup Center workspace, department dashboard/navigation entry points, explicit manager/approver/template permissions, cross-department authorization tests, and operating documentation.

## 0.6.6 - 2026-08-20

### TracePoint voucher batches and repeatable checkpoints

- Added stable per-voucher references, expected attachment/page details, and immutable movement ledgers for bundled physical vouchers.
- Added controlled child-packet splits and compatible rebundling while preserving origin, current custody, pending route work, state-version safety, and both packet histories.
- Added repeatable office checkpoints for review, signature, approval, certification, and release, including optional named employees and governed exception skips.
- Changed arrival at the declared destination to an ordinary active receipt by default, allowing temporary signature visits and onward movement.
- Added a deliberate terminal-delivery choice, final-recipient validation, and required-checkpoint enforcement before delivery can close.
- Preserved historical delivered receipts during migration and retained simple packet-level manifests for backwards compatibility.
- Added operational UI for voucher manifests, bundle lineage, checkpoint progress, split/rebundle controls, and plain-language terminal-receipt guidance.
- Added regression coverage for repeated destination visits, premature delivery rejection, active split concurrency, and split/rebundle voucher lineage.
- Updated `sqlparse` to 0.6.0 to resolve the four dependency advisories detected by the release security gate.

## 0.6.5 - 2026-08-16

### TracePoint operations workspace (0.6.5)

- Added a plain-language, department-bounded TracePoint workspace with live draft, in-transit, delivered, and discrepancy indicators.
- Added packet preparation, governed source links, stable printable QR labels, daily employee code display/replacement/revocation, and minimal authenticated scan landing pages.
- Added shared-station receipt screens that visibly separate scanning from the final custody confirmation and record optional physical-count notes.
- Added permission-aware custody timelines, immutable receipt details, delivery/completion controls, holds, discrepancies, resolutions, and append-only custody corrections.
- Added dashboard and employee-navigation entry points, browser-facing authorization and workflow regressions, synthetic custody routes, and portfolio-ready UI captures.

### TracePoint delivery and exception controls (0.6.4)

- Mark packets delivered automatically when a confirmed receipt matches the preparer's declared final employee or department.
- Keep delivery separate from permission-restricted completion and record both with server times and responsible employees.
- Add reasoned hold, resume, and cancellation workflows that invalidate open scans and advance packet state versions.
- Add employee-reported missing-content, wrong-route, damage, and other discrepancies with immutable reports and governed resolution.
- Add supervisor-only current-custody corrections as separate immutable events referencing the affected receipt when applicable; confirmed receipts remain unchanged.

### TracePoint handoff ledger (0.6.3)

- Added five-minute scan sessions that pair a packet with a validated receiving employee while leaving custody unchanged until confirmation.
- Added atomic initial activation and repeated employee-to-employee receipt flows backed by row locks and packet state versions.
- Added immutable, sequenced handoff receipts with employee, position, and department snapshots plus server confirmation times.
- Added idempotency for repeated scan starts and confirmation submissions, one-open-session constraints, stale-session rejection, and self-transfer prevention.
- Revalidate daily credentials at confirmation and record credential usage without weakening replacement, revocation, or expiry behavior.

### TracePoint QR credentials (0.6.2)

- Added stable, opaque packet QR payloads that contain no packet title, employee identity, citizen data, or document details.
- Added random daily employee credentials that expire at the configured Asia/Manila day boundary and store only a SHA-256 token digest.
- Added explicit replacement and revocation, immediately invalidating earlier codes and recording append-only credential events.
- Revalidate account activity and department assignment whenever a daily code is resolved, so departed, disabled, or unassigned users cannot receive packets.
- Added safe QR PNG rendering shared by packet labels and employee daily-code presentation.

### TracePoint packet foundation (0.6.1)

- Added stable physical-packet identities, human-readable tracking references, contents manifests, declared final departments or employees, and separate current-custody fields.
- Added explicit internal, restricted, and confidential classifications plus department-bounded workspace, preparation, printing, completion, exception, credential, and oversight permissions.
- Allowed packets to reference governed department records and department-validated official reports without copying their authoritative files.
- Added model validation for employee assignments, destination membership, source ownership, confidentiality inheritance, custody consistency, and post-activation immutability.
- Added auditable packet creation and draft updates with collision-resistant tracking references and transactional writes.

### TracePoint custody planning (0.6.0)

- Defined the stable packet QR plus daily employee QR workflow for shared LGU receiving stations and optional personal devices.
- Required authenticated review and confirmation before custody changes; scanning a code alone never records a transfer.
- Defined immutable, idempotent handoff receipts, real-route tracking, final-destination rules, and concurrency protection.
- Separated physical delivery from completion of the underlying departmental work.
- Established privacy, department-boundary, credential-revocation, correction, and discrepancy rules.
- Added a one-branch-per-slice `0.6.x` TracePoint delivery train and versioned release gate.

### Department records and document workflows

- Added a reusable, department-bounded Records workspace for Assistance cases, citizen service history, social-welfare programs and activities, approved reports, and separate departmental files.
- Kept operational source files authoritative in their existing modules while recording typed references, file metadata, SHA-256 checksums, and an auditable lifecycle ledger.
- Added explicit permissions for workspace access, management, review, approval, downloads, retention, and restricted/confidential visibility.
- Added draft, review, approval, archival, supersession, and disposition workflows with immutable official metadata, legal holds, retention due dates, and safe department boundaries.
- Allowed department-validated official report outputs to be filed idempotently as records without duplicating generated files or losing report-run evidence.
- Added contextual record actions to Assistance, Citizen Review, Programs, Activities, and Reporting, plus live Records summaries on department dashboards.
- Restored the authenticated employee logo link to the public portal so administrators can inspect public-facing changes.
- Restored the Dev Zone legacy-project footer card and added an in-template maintainer note requiring future redesigns to preserve it.

### Report-template fidelity

- Added versioned paper size, orientation, margins, borders, repeating headers, logos, footer, page-number, and document-control settings for native PDF and XLSX layouts.
- Separated controlled pilot generation from department-validated official layouts and blocked pilot runs from official approval.
- Added evidence-backed fidelity validation after side-by-side comparison with the department's current form.
- Added permission-aware PDF print previews and archived output downloads, hiding actions when the format or employee permission does not apply.
- Added controlled mapped-XLSX generation using reserved named ranges while preserving departmental formatting, formulas, print setup, and fixed row capacity.
- Added exact PDF overlays using reviewed, allowlisted coordinate mappings without replacing the source form.
- Added checksum-backed mapper preflight, mapping invalidation, immutable approved mappings, run snapshots, and format compatibility checks for manual and scheduled reports.
- Kept DOCX and image forms as non-executable intake evidence to avoid desktop-office dependencies in scheduled production jobs.

### Documentation

- Replaced the stale project overview with current setup, architecture, feature, verification, and operations guidance.
- Added a documentation map and expanded reporting onboarding, scheduling, permissions, and existing-template guidance.

## 2026-08-14

### Configurable reporting automation

- Added a reusable, department-bounded reporting platform piloted with MSWD.
- Added allowlisted dataset adapters, configurable fields and filters, grouping, totals, sorting, and period selection without arbitrary SQL or executable template content.
- Added versioned official layouts and safe reference uploads for familiar PDF, spreadsheet, Word, and image forms.
- Added PDF, XLSX, and CSV generation with exact configuration snapshots, checksums, immutable audit events, and archived outputs.
- Added manual and daily, weekly, monthly, quarterly, and annual scheduled runs backed by an idempotent ledger and safe retries.
- Added generated, reviewed, approved, failed, and superseded states with explicit permissions and department boundaries.
- Added five MSWD presets: Assistance volume and status, program accomplishments, aggregate reach, activity schedules, and workload.
- Added reporting indicators to department dashboards and synthetic portfolio screenshots for the reporting workspace and approval flow.

### Citizen profiles and service history

- Added a permission-restricted citizen review queue with search, sorting, pagination, assignment, notes, review states, and audit history.
- Added neutral Assistance usage summaries and duplicate-candidate indicators without treating frequency as fraud, risk, or eligibility evidence.
- Kept `CitizenProfile` as the canonical citizen identity and established an adapter path for future approved government services.

### Professional configurable interface

- Added configurable institutional labels, colors, logos, hero imagery, footer content, service-card labels, links, icons, and ordering.
- Improved public and employee navigation for plain-language, keyboard-accessible, responsive use.
- Updated synthetic showcase data, screenshots, captions, and the portfolio manifest.

### MSWD programs and dashboards

- Reworked the MSWD login landing page as a department workspace with Assistance as a linked processing module.
- Added internal social-welfare programs and activities with ownership, schedules, venues, operational status, aggregate attendance, outcomes, permissions, and audit timestamps.
- Preserved reusable department-dashboard contracts for future offices and modules.

### Maintenance

- Updated and audited Python dependencies, security workflows, Dependabot configuration, and the minimal browser asset bundle.
- Expanded leave-credit policy and adjustment controls while preserving predictable accrual and half-day request increments.

## 2025-08-11

### Changed

- Removed Telegram delivery from the Assistance request workflow and routed status and document updates through email.
- Removed unused bot behavior from the active deployment path while retaining the historical app for compatibility checks.

## 2025-06-27

### Assistance submission workflow

- Added a two-step request flow: personal/request information followed by supporting-document upload through the secure edit link.
- Added asynchronous upload feedback, previews, document-type selection, and approved-file replacement restrictions.
- Added progress indicators and clearer confirmation-email instructions.
- Fixed upload route reversal, template-filter loading, malformed form behavior, and approved-file client-side safeguards.

## 2025-06-26

### Historical Telegram integration

- Added request linking and notifications through a Telegram bot, protected by reference and edit codes.
- Restricted linking to unclaimed requests and added environment-based token configuration.
- This integration was removed from active Assistance delivery on 2025-08-11.

## 2025-06-25

### Profiles and edit history

- Added `ProfileEditLog` with editor, section, note, and timestamp metadata.
- Added role-aware profile editing and restricted HR employment metadata.
- Added government identifiers, hiring dates, department memo uploads, and profile edit-history presentation.
- Fixed missing-slug redirects and log rendering when the editor is unavailable.

## 2025-06-23

### Assistance operations

- Added the original MSWD request dashboard, request status history, staff-facing transparency logs, citizen email notifications, and printable request summaries.
- Added department-aware dashboard selection and corrected template rendering for log entries.

## 2025-06-15

### Assistance foundation

- Added the Assistance request lifecycle, supporting-document review, duplicate-period prevention, secure tracking/edit access, and contextual messages.
- Split people, department, salary, and public-home responsibilities into their own Django apps.
- Standardized the interface on AdminLTE and Bootstrap styling and improved alert readability.
