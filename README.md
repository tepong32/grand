# GRAND

GRAND is a department-aware local-government service platform built with Django. It gives citizens clear public service flows and gives employees workspaces that reflect their assigned department, role, and permissions.

The current MSWD pilot combines Assistance request processing, social-welfare program operations, citizen review, and governed report generation. The same department and permission contracts are intended to support additional municipal offices without duplicating the platform.

## Current capabilities

- Configurable public identity, service cards, icons, media, colors, and plain-language navigation.
- Dynamic employee dashboards with department-specific modules, leadership, team, plantilla, leave, contacts, and announcements.
- Floating, non-modal Internal How-Tos that follow the employee's current department and role, prioritize the current page, retain private progress, and never transfer a predecessor's completion to a successor.
- Assistance submission, secure editing and tracking, document review, status history, notifications, and separate MSWD processing views.
- Internal social-welfare programs and activities for seminars, feeding programs, outreach, distributions, schedules, venues, attendance totals, and outcomes.
- Permission-restricted citizen review with assistance usage history, duplicate-candidate indicators, review ownership, notes, and audit events.
- Leave requests and predictable credit accrual with approval deductions.
- Cross-department reporting definitions, governed Finance statements and notes, signed/redacted reference control comparison, native print layouts, controlled mapped-XLSX and exact-PDF compatibility, recurring schedules, checksums, fidelity validation, permission-aware print/download actions, review, approval, and supersession.
- One configurable, TraceSync-ready export root with portable department/user/category folders, atomic copies, and adjacent checksum/lineage manifests for requested reports and transaction exports.
- Department-bounded records with source-in-place links, checksum-backed uploads, confidentiality controls, review and approval, audited downloads, retention, legal holds, supersession, archival, and disposition.
- TracePoint physical-paper custody with stable packet labels, revocable daily employee QR codes, individual voucher manifests, split/rebundle lineage, repeatable office checkpoints, explicit terminal receipt, immutable handoff history, and separate delivery/completion states.
- Finance Setup Center with effective-dated releases, versioned master data and rules, separate preparation/approval, signatory and numbering governance, safe macro-free Excel intake, synthetic previews, and structured readiness blockers.
- Governed Finance shadow/parallel cycles with source and schema checksums, exact case-to-report comparisons, owned defect gates, independent reconciliation, named seven-party training/UAT acceptance, exact-scope cutover authority, retained rollback, and TraceSync-ready evidence packages.
- Standalone Accounting with its own finance database, guided fiscal setup, controlled opening-balance staging/reconciliation/export, transaction-specific posting-rule snapshots, balanced journal preparation, independent posting, immutable payable/withholding subsidiary detail and control reconciliation, general ledger, trial balance, and TraceSync-ready evidence exports—without an eGAPS runtime dependency.
- Annual Budget preparation with reviewed calls and ceilings, classified department proposals and targets, resource estimates, traceable consolidation, version comparison, and portable exports; approved proposals remain non-spendable until authorization.
- Allotment release control against immutable operational appropriations, with initial/later releases, reserves, deferrals, adjustments, returns/cancellations, exact signed totals, independent posting, live balances, correction lineage, and TraceSync-ready exports.
- Authoritative obligation control with requesting-office ALOBS/ORS/OBR drafts, independent Budget certification, exact appropriation/allotment lineage, immutable RAAO-equivalent balances, guided corrections, and portable registry exports.
- Voucher and Disbursement Workbench shadow vertical slice with one shared Budget–Accounting–Treasury case, governed supplier/payee selectors, authoritative F4.2 obligation/payable intake, typed transaction variants, authority-backed documentary checklists, one-to-many/many-to-one/partial/progress/final relationship controls, recognition/adjustment decisions, independent Accounting readiness review, portable transaction exports, pilot DV numbering, wet-signature rounds, JEV references, multi-check controls, versioned multi-case bank advice and bank acknowledgement, release, returned-payment Accounting/reissue, remittance, bank reconciliation with prior-item carry/clearance lineage, reconciliation-backed cash positions, issue reservations, instrument ageing, correction history, and checksum-backed outputs. Legacy cases retain their pilot OBR history; F5 relationships version authoritative obligation UUID/checksum allocations and do not post a second Budget balance.
- Governed tax evidence from plain-language Finance Setup rules through DV capture, Accounting subsidiary posting/reversal, reconciled source schedules, tax-aware Treasury remittance, and independently reviewed external filing/payment references with amendment lineage and TraceSync-ready exports; GRAND does not perform e-filing or invent current local deadlines/forms.
- Governed Finance accountability packages built from approved cross-office reports, statement notes, signed-reference comparisons, and verified tax-filing evidence, using locally editable package recipes, maker–checker approval, reasoned correction successors, checksum traceback, and TraceSync-ready manifests.
- Governed local Finance form acceptance with human-readable inventories, dynamic required/optional/conditional/repeating sections, independently witnessed data/layout/signatory/overflow/accessibility/print/recovery tests, reasoned successors, and TraceSync-ready evidence.
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
| Finance setup and cutover | `finance` | Approved master data, rules, signatories, numbering/templates, shadow reconciliation, stakeholder acceptance, and explicit cutover authority |
| Accounting | `accounting` | Separate-database fiscal/opening controls, chart, journals, posting, ledger, and trial balance |
| Budget, allotment, and obligations | `budget` | Annual calls/proposals, operational appropriation authorization, posted allotment control, requesting-office obligation certification, and RAAO-equivalent registry |
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
python manage.py seed_internal_howtos
python manage.py runserver
```

Local development uses SQLite, the console email backend, and `src.settings.dev` by default. Do not commit local database or uploaded-media changes. Production uses `src.settings.prod`, MySQL, HTTPS security settings, SMTP, and environment-provided secrets.

Set `GRAND_EXPORT_ROOT` to the single local folder synchronized by TraceSync. Every requested export is downloaded and atomically retained there under a normalized department/user/category path with an adjacent SHA-256 manifest. See the [portable export archive guide](docs/EXPORT_ARCHIVE.md); syncing this folder complements but does not replace controlled records and tested backups.

Production database recovery uses a separate restricted `GRAND_BACKUP_ROOT`. The `backup_databases` command creates one atomically published, checksum-manifested native MySQL logical backup set for both the main and Finance stores. See [database backup and recovery](docs/DATABASE_BACKUP.md); a created backup is not considered restore-tested until an isolated rehearsal restores both stores, reconciles controls, meets locally approved RPO/RTO, and is independently witnessed through the structured F11 record.

The repository also includes a non-root Python 3.11 production Docker image, Gunicorn/WhiteNoise runtime, `/healthz/` probe, `.env.example`, and explicit two-store production settings. The [Docker and Render preparation guide](docs/DEPLOYMENT_RENDER.md) identifies the infrastructure choices and field checks that still block a real deployment.

Before a release or cutover rehearsal, `production_preflight` produces a non-secret configuration or live-environment receipt. Live mode checks both MySQL stores, migration state, and atomic writes across the separate media, export, and backup roots. Passing it does not claim that a restore rehearsal, LGU acceptance, or cutover authorization occurred.

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

Create a complete production database backup set with:

```powershell
python manage.py backup_databases --settings=src.settings.prod
```

This command intentionally refuses local SQLite file copying; use it in the production-compatible MySQL environment described in the recovery guide.

Verify a copied set before restore with the separately retained manifest hash printed by the creation command:

```powershell
python manage.py verify_database_backup <copied-set-directory> --expect-manifest-sha256 <sha256> --settings=src.settings.prod
```

This verifies structure, both gzip streams, sizes, and checksums. It does not claim that a database restore succeeded.

Inspect only the production configuration without connecting to either database or writing storage probes:

```powershell
python manage.py production_preflight --configuration-only --settings=src.settings.prod
```

Run the full environment preflight only inside the intended release environment:

```powershell
python manage.py production_preflight --json --settings=src.settings.prod
```

The command exits nonzero for failed or deferred selected-scope checks. Its receipt always distinguishes preflight from witnessed recovery and cutover evidence.

## Documentation

- [Documentation map](docs/README.md)
- [Reporting operations and governance](docs/REPORTING.md)
- [Portable GRAND export archive](docs/EXPORT_ARCHIVE.md)
- [Database backup and recovery](docs/DATABASE_BACKUP.md)
- [Production Docker and Render preparation](docs/DEPLOYMENT_RENDER.md)
- [Department Internal How-Tos](docs/INTERNAL_HOWTOS.md)
- [Department report-template intake](docs/REPORT_TEMPLATE_INTAKE.md)
- [Department records operations](docs/RECORDS.md)
- [TracePoint physical-custody contract](docs/TRACEPOINT.md)
- [Finance Setup Center operations](docs/FINANCE_SETUP.md)
- [Voucher and Disbursement Workbench](docs/VOUCHER_WORKBENCH.md)
- [Finance controlled DV printing and custody](docs/FINANCE_CONTROLLED_PRINT_CUSTODY.md)
- [Finance cash position and instrument ageing](docs/FINANCE_CASH_POSITION.md)
- [Finance bank advice and returned instruments](docs/FINANCE_BANK_ADVICE.md)
- [Finance shadow operation, UAT acceptance, and controlled cutover](docs/FINANCE_SHADOW_CUTOVER.md)
- [GRAND Finance complete-cycle roadmap](docs/FINANCE_ROADMAP.md)
- [Finance process discovery protocol](docs/FINANCE_PROCESS_DISCOVERY.md)
- [Finance evidence register and interview kit](docs/finance-discovery/README.md)
- [Complete-cycle Finance information architecture and prototype](docs/finance-ia/README.md)
- [Finance opening balances and control-total intake](docs/FINANCE_OPENING_BALANCES.md)
- [Finance process-fidelity baseline](docs/FINANCE_PROCESS_FIDELITY_BASELINE.md)
- [Finance visual template promotion and rollback](docs/FINANCE_TEMPLATE_PROMOTION.md)
- [Finance local-form inventory and acceptance](docs/FINANCE_LOCAL_FORM_ACCEPTANCE.md)
- [Finance accountability-package profiles and assembly](docs/FINANCE_ACCOUNTABILITY_PACKAGES.md)
- [F9 comprehensive review and implementation handoff](docs/FINANCE_F9_REVIEW_AND_HANDOFF.md)
- [Product roadmap](docs/ROADMAP.md)
- [Security maintenance](SECURITY.md)
- [Synthetic portfolio screenshots](output/playwright/grand-portfolio/README.md)
- [Change history](CHANGELOG.md)

## Product direction

GRAND remains the platform identity. GRAND Finance will become one role-shaped, complete-cycle sub-application: requesting offices initiate funded work, Budget governs appropriations/allotments/obligations, Accounting governs payables/books/reports, and Treasury governs cash/payment/reconciliation. TracePoint owns physical-document custody, Records owns retained authoritative files, and Finance Setup owns governed configuration; those domains link to the shared finance lineage without duplicating authority.

The current Voucher Workbench remains in controlled synthetic/pilot comparison mode. F5.1–F5.3 connect requesting-office payables to authoritative obligations, typed documentary rules, versioned allocation relationships, recognition decisions, and portable exports. F6.1 adds editable starter-template intake, checksum/versioned printing, reasoned reprints, mandatory TracePoint packet creation, and returned-wet-signature gates. F7.1 adds locally reviewable transaction/event posting rules and immutable rule-backed JEV requests; F7.2 adds posted payable/withholding subsidiary detail and checksum-backed control reconciliation; F7.3 carries governed payment-release events through Accounting and exports portable payment-register evidence; F7.4 adds human-modifiable close policies, checksummed maker–checker close, and ordered controlled reopen. F8.1 executes controlled cross-voucher deduction/withholding remittances through independent review and liability-reducing posting; F8.2 adds checksummed bank-statement reconciliation; F8.3 adds locally reviewable cash policies, reconciliation-backed positions, issue reservations, and instrument ageing; F8.4 adds retained multi-case advice review/submission/bank response, release acknowledgement gates, and returned-payment reversal/reissue orchestration; F8.5 carries unresolved reconciled timing items into the next statement and closes/reopens their lineage through reasoned matches. Parent F5–F8 acceptance still requires locally accepted rules/forms/thresholds, consecutive redacted replay, paper/printer/accounting tests, and named-office acceptance. The delivery order and gates are documented in the [GRAND Finance complete-cycle roadmap](docs/FINANCE_ROADMAP.md).

All showcase records and screenshots are synthetic. Production citizen data, credentials, uploaded records, and generated official reports must never be added to the repository.
