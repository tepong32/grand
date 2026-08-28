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
- One configurable, TraceSync-ready export root with portable department/user/category folders, atomic copies, and adjacent checksum/lineage manifests for requested reports and transaction exports.
- Department-bounded records with source-in-place links, checksum-backed uploads, confidentiality controls, review and approval, audited downloads, retention, legal holds, supersession, archival, and disposition.
- TracePoint physical-paper custody with stable packet labels, revocable daily employee QR codes, individual voucher manifests, split/rebundle lineage, repeatable office checkpoints, explicit terminal receipt, immutable handoff history, and separate delivery/completion states.
- Finance Setup Center with effective-dated releases, versioned master data and rules, separate preparation/approval, signatory and numbering governance, safe macro-free Excel intake, synthetic previews, and structured readiness blockers.
- Standalone Accounting with its own finance database, guided fiscal setup, controlled opening-balance staging/reconciliation/export, balanced journal preparation, independent posting, immutable audit history, general ledger, and trial balance—without an eGAPS runtime dependency.
- Voucher and Disbursement Workbench shadow vertical slice with one shared Budget–Accounting–Treasury case, governed supplier/payee selectors, pilot OBR and DV numbering, wet-signature rounds, JEV references, multi-check controls, bank advice, release, correction history, and checksum-backed outputs. Authoritative annual appropriations, AROs, RAAO/equivalent balances, and complete fiscal-year operation remain roadmap work.
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
| Physical custody | `tracepoint` | QR-tagged paper packets, daily employee codes, confirmed handoffs, exceptions, and completion |
| Finance setup | `finance` | Approved master data, rules, signatories, numbering policies, voucher workbook versions, and readiness |
| Accounting | `accounting` | Separate-database fiscal/opening controls, chart, journals, posting, ledger, and trial balance |
| Voucher operations | `vouchers` | Cross-office OBR, DV, signature, Accounting, check, advice, and release workflow |
| Workforce | `leave_mgt`, `salaries` | Leave workflows and salary-related records |

## Local development

Python 3.11 is the currently verified runtime. From PowerShell in the repository root:

```powershell
py -3.11 -m venv env
.\env\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py migrate --database=finance
python manage.py seed_reporting_presets
python manage.py runserver
```

Local development uses SQLite, the console email backend, and `src.settings.dev` by default. Do not commit local database or uploaded-media changes. Production uses `src.settings.prod`, MySQL, HTTPS security settings, SMTP, and environment-provided secrets.

Set `GRAND_EXPORT_ROOT` to the single local folder synchronized by TraceSync. Every requested export is downloaded and atomically retained there under a normalized department/user/category path with an adjacent SHA-256 manifest. See the [portable export archive guide](docs/EXPORT_ARCHIVE.md); syncing this folder complements but does not replace controlled records and tested backups.

The reporting seed command is idempotent: it creates or preserves the five MSWD pilot definitions without duplicating them. See [Reporting operations](docs/REPORTING.md) before configuring templates or scheduled runs, and [GRAND accounting operations](docs/GRAND_ACCOUNTING_OPERATIONS.md) before assigning finance roles or opening periods.

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
- [Portable GRAND export archive](docs/EXPORT_ARCHIVE.md)
- [Department report-template intake](docs/REPORT_TEMPLATE_INTAKE.md)
- [Department records operations](docs/RECORDS.md)
- [TracePoint physical-custody contract](docs/TRACEPOINT.md)
- [Finance Setup Center operations](docs/FINANCE_SETUP.md)
- [Voucher and Disbursement Workbench](docs/VOUCHER_WORKBENCH.md)
- [GRAND Finance complete-cycle roadmap](docs/FINANCE_ROADMAP.md)
- [Finance process discovery protocol](docs/FINANCE_PROCESS_DISCOVERY.md)
- [Finance evidence register and interview kit](docs/finance-discovery/README.md)
- [Complete-cycle Finance information architecture and prototype](docs/finance-ia/README.md)
- [Finance opening balances and control-total intake](docs/FINANCE_OPENING_BALANCES.md)
- [Finance process-fidelity baseline](docs/FINANCE_PROCESS_FIDELITY_BASELINE.md)
- [Product roadmap](docs/ROADMAP.md)
- [Security maintenance](SECURITY.md)
- [Synthetic portfolio screenshots](output/playwright/grand-portfolio/README.md)
- [Change history](CHANGELOG.md)

## Product direction

GRAND remains the platform identity. GRAND Finance will become one role-shaped, complete-cycle sub-application: requesting offices initiate funded work, Budget governs appropriations/allotments/obligations, Accounting governs payables/books/reports, and Treasury governs cash/payment/reconciliation. TracePoint owns physical-document custody, Records owns retained authoritative files, and Finance Setup owns governed configuration; those domains link to the shared finance lineage without duplicating authority.

The current Voucher Workbench remains in shadow comparison mode. It starts later than the complete LGU cycle because authoritative annual appropriations, allotment releases, and obligation balances are not yet implemented. The delivery order, acceptance gates, and current-position matrix are documented in the [GRAND Finance complete-cycle roadmap](docs/FINANCE_ROADMAP.md).

All showcase records and screenshots are synthetic. Production citizen data, credentials, uploaded records, and generated official reports must never be added to the repository.
