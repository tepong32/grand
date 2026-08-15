# GRAND

GRAND is a department-aware local-government service platform built with Django. It gives citizens clear public service flows and gives employees workspaces that reflect their assigned department, role, and permissions.

The current MSWD pilot combines Assistance request processing, social-welfare program operations, citizen review, and governed report generation. The same department and permission contracts are intended to support additional municipal offices without duplicating the platform.

## Current capabilities

- Configurable public identity, service cards, icons, media, colors, and plain-language navigation.
- Dynamic employee dashboards with department-specific modules, leadership, team, plantilla, leave, contacts, and announcements.
- Assistance submission, secure editing and tracking, document review, status history, notifications, and separate MSWD processing views.
- Internal social-welfare programs and activities for seminars, feeding programs, outreach, distributions, schedules, venues, attendance totals, and outcomes.
- Permission-restricted citizen review with assistance usage history, duplicate-candidate indicators, review ownership, notes, and audit events.
- Leave requests and predictable credit accrual with approval deductions.
- Cross-department reporting definitions, native print layouts, controlled mapped-XLSX and exact-PDF compatibility, recurring schedules, checksums, fidelity validation, permission-aware print/download actions, review, approval, and supersession.
- Department-bounded records with source-in-place links, checksum-backed uploads, confidentiality controls, review and approval, audited downloads, retention, legal holds, supersession, archival, and disposition.
- Public and internal announcements, employee/citizen profiles, department records, and organization views.

GRAND keeps operational modules separate: an employee's dashboard summarizes work and links to specialized workspaces instead of embedding full processing screens in the landing page.

## Application map

| Area | Django app | Primary responsibility |
| --- | --- | --- |
| Public portal and dashboards | `home` | Site identity, navigation, announcements, and login landing context |
| People and identity | `users`, `profiles` | Authentication, employee profiles, citizen profiles, and review history |
| Organization | `departments` | Department identity, leadership, membership, and department boundaries |
| Assistance | `assistance` | Citizen requests, supporting documents, staff processing, and request audit trail |
| Programs and activities | `social_welfare` | Internal MSWD program and activity operations |
| Reports | `reporting` | Controlled datasets, layouts, generation, schedules, approvals, and archives |
| Records | `records` | Official department registry, source links, files, review, retention, and controlled retrieval |
| Workforce | `leave_mgt`, `salaries` | Leave workflows and salary-related records |

## Local development

Python 3.11 is the currently verified runtime. From PowerShell in the repository root:

```powershell
py -3.11 -m venv env
.\env\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py seed_reporting_presets
python manage.py runserver
```

Local development uses SQLite, the console email backend, and `src.settings.dev` by default. Do not commit local database or uploaded-media changes. Production uses `src.settings.prod`, MySQL, HTTPS security settings, SMTP, and environment-provided secrets.

The reporting seed command is idempotent: it creates or preserves the five MSWD pilot definitions without duplicating them. See [Reporting operations](docs/REPORTING.md) before configuring templates or scheduled runs.

## Verification

Install the development-only audit tool when performing security maintenance:

```powershell
python -m pip install -r requirements-dev.txt
python -m pip check
python -m pip_audit -r requirements.txt
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```

Run due report schedules safely with:

```powershell
python manage.py run_scheduled_reports
```

Repeated invocations for the same scheduled period do not create duplicate outputs.

## Documentation

- [Documentation map](docs/README.md)
- [Reporting operations and governance](docs/REPORTING.md)
- [Department report-template intake](docs/REPORT_TEMPLATE_INTAKE.md)
- [Department records operations](docs/RECORDS.md)
- [Product roadmap](docs/ROADMAP.md)
- [Security maintenance](SECURITY.md)
- [Synthetic portfolio screenshots](output/playwright/grand-portfolio/README.md)
- [Change history](CHANGELOG.md)

## Product direction

GRAND remains the platform identity. TracePoint is reserved for the later physical-document custody layer: physical document identities, QR labels, transfers, receiving, and acknowledgements. It will build on the governed Records registry and remain distinct from the secure links and QR codes used by Assistance.

All showcase records and screenshots are synthetic. Production citizen data, credentials, uploaded records, and generated official reports must never be added to the repository.
