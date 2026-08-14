# Changelog

Material GRAND changes are recorded here. The repository's Git history remains the detailed source of truth.

## Unreleased

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
