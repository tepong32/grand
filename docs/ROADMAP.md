# GRAND product roadmap

This file records agreed future work after the MSWD Programs and Activities phase. Each implementation phase uses a dedicated `codex/` branch, tests, synthetic showcase data, portfolio screenshots, review, CI, and merge into `master`. See the [documentation map](README.md) for operator and project guides.

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

The `0.6.0` through `0.6.5` train now includes the operating workspace, print labels, daily-code presentation, shared-station confirmation, department dashboard indicators, exception controls, automated regressions, and synthetic portfolio evidence. Production rollout should begin with a small inter-office pilot and written receiving procedure before expanding LGU-wide.
