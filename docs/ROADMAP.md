# GRAND product roadmap

This file records agreed future work after the MSWD Programs and Activities phase. Each implementation phase uses a dedicated `codex/` branch, tests, synthetic showcase data, portfolio screenshots, review, CI, and merge into `master`.

## Completed — Professional, configurable civic UI

- Use plain-language, task-oriented public and employee navigation.
- Preserve GRAND's institutional identity while keeping branding neutral across changes in administration.
- Let authorized administrators configure the institution name, portal labels, colors, logo, hero image, optional official media, footer text, service-card labels, icons, links, and ordering.
- Remove fabricated links, campaign-specific content, and shared-template assumptions that every authenticated user is an employee.
- Verify responsive layouts, keyboard navigation, readable contrast, real workflows, and portfolio screenshots.

## Completed — Citizen profiles, review, and service history

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

## Later platform phases

- Records, attachments, retention, review, approval, supersession, and controlled exports.
- Physical-document QR identity, custody, transfer, receiving, and acknowledgement, kept separate from Assistance secure-link QR codes.
