# Grand portfolio screenshots

This folder contains reproducible, portfolio-ready captures of Grand's municipal services UI. The images use synthetic people, requests, and departments created by `seed_showcase.py`; no production or citizen data is included.

## Highlights

- `grand-public-services.png` - public municipal service discovery
- `grand-assistance-portal.png` - account-free assistance submission and tracking
- `grand-hr-dashboard.png` - live HR metrics, workforce modules, and department team context
- `grand-dynamic-department-dashboard.png` - generic fallback proving that newly added departments receive a useful dashboard without a custom template
- `grand-mswd-dashboard.png` - department-centered MSWD workspace with live Assistance and social-welfare program summaries
- `grand-mswd-programs.png` - internal programs and activities workspace with schedules, aggregate reach, outcomes, and role-aware management
- `grand-mswd-operations.png` - operational assistance-request queue for MSWD staff
- `grand-reporting-workspace.png` - cross-department reporting workspace with five MSWD reports, governance indicators, schedules, pilot/official distinctions, and permission-aware output actions
- `grand-report-run-approval.png` - auditable report-run detail with archived output integrity, print/download actions, template-fidelity evidence, review history, and official approval state
- `grand-report-template-mapping.png` - controlled compatibility workspace for preserving familiar departmental Excel and PDF forms through checksum-backed mapping
- `grand-records-workspace.png` - department records registry with official, review, draft, confidentiality, and retention indicators
- `grand-record-detail.png` - governed record detail with source-in-place links, checksum, approval, retention, and audit evidence
- `grand-tracepoint-workspace.png` - cross-department physical-custody register with live status, responsibility, destination, and exception indicators
- `grand-tracepoint-packet-route.png` - voucher manifest, repeatable office checkpoints, temporary destination visit, and immutable employee-to-employee receipt route linked to a governed official report
- `grand-tracepoint-daily-code.png` - random, day-limited employee QR identity with replacement and revocation guidance

The machine-readable `manifest.json` is the source of truth for portfolio captions, alt text, ordering, and feature descriptions.

## Reproducing the showcase data

Set `DJANGO_SQLITE_PATH` to a disposable SQLite file, run the seed script, and start Django against that same database. The script prints the synthetic login credentials and request reference used for browser QA.

Do not point the seed script at a production database.
