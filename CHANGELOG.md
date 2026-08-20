# Changelog

Material GRAND changes are recorded here. The repository's Git history remains the detailed source of truth.

## Unreleased

No material changes are pending release.

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
