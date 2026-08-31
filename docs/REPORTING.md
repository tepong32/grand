# GRAND reporting operations

GRAND's reporting platform turns approved application data into controlled departmental outputs. It is cross-department infrastructure piloted with MSWD; new departments add dataset adapters and presets without rebuilding the generation, scheduling, or approval engine.

The employee workspace is available at `/reports/`. Access is department-bounded and requires the reporting workspace permission, department-head/OIC authority, or superuser status.

## Existing government templates

Authorized template managers may attach PDF, XLSX, XLS, DOCX, PNG, or JPEG reference files. GRAND stores them as non-executable references unless an XLSX or PDF version is explicitly configured with one of the controlled mappers below. GRAND never runs embedded queries, scripts, macros, or template code.

Each usable layout is represented by a versioned `ReportTemplateVersion` containing its title, institutional header, certification text, signatory lines, footer, document-control prefix, logos, paper geometry, page-border behavior, and controlled layout settings. Technical approval permits controlled preview generation. Official use requires a retained promotion with golden comparison or first-layout reference review, independent approval, and separate activation.

Three rendering modes are supported:

- **Native GRAND layout** generates PDF, XLSX, or CSV using versioned identity and print settings.
- **Mapped Excel workbook** preserves an uploaded macro-free `.xlsx` and writes only to reviewed workbook-level named ranges. `GRAND_DATA_AREA` is required. Optional anchors are `GRAND_TOTALS_AREA`, `GRAND_HEADER`, `GRAND_TITLE`, `GRAND_PERIOD`, `GRAND_PERIOD_START`, `GRAND_PERIOD_END`, `GRAND_CONTROL_ID`, and `GRAND_ROW_COUNT`. External-file formulas, mismatched columns, and row overflow fail safely.
- **Exact PDF overlay** preserves the uploaded PDF pages and adds allowlisted metadata, selected dataset fields, or configured totals at reviewed page coordinates. Encrypted or rotated source pages and out-of-bounds mappings fail preflight.

DOCX and image files remain intake evidence. GRAND does not depend on desktop Word or LibreOffice for scheduled production rendering.

### Onboarding a familiar office form

1. Create or clone a report definition using an approved dataset.
2. Select only the fields, filters, period behavior, grouping, totals, and ordering that the office needs.
3. Upload the existing form as a reference when it helps reviewers compare the result.
4. Choose native rendering or configure the controlled Excel/PDF mapper.
5. Run mapper preflight, which records a SHA-256 checksum and validated layout summary, then have an authorized approver approve the version for pilot generation.
6. Prepare a promotion using the accepted prior run for the same period and format; GRAND generates the candidate preview and compares data/control evidence automatically.
7. Record the human form, signatory, pagination, overflow, printer, and form-stock comparison plus the schedule-impact choice.
8. A different reviewer approves the locked evidence, and an authorized manager activates or later rolls back the version without a software deployment.

Use the [department template-intake checklist](REPORT_TEMPLATE_INTAKE.md) to inventory actual forms. Any coordinate, reserved range, or source-file change invalidates preflight; approved versions are immutable and must be replaced with a new version.

### Local Finance form acceptance

Budget, Accounting, Treasury, and Finance configuration roles can open **Local form acceptance** from the reporting workspace. Preparers record the familiar form fields and dynamic required/optional/conditional/repeating sections, link one exact activated report template or active preflighted Finance workbook, and upload only a blank or safely redacted reference. Seven practical test categories cover data, layout, signatory/custody route, overflow, accessibility/download, printer/form stock, and rollback/recovery.

A different witness decides each immutable test attempt, and a different reviewer accepts or returns the locked form submission. Failed attempts remain in history. Accepted changes use a reasoned successor and repeat all tests; no financial transaction is edited by this workflow. Accepted and superseded evidence packets are archived in the TraceSync-ready `finance-local-form-acceptance` category. See [Finance local-form inventory and acceptance](FINANCE_LOCAL_FORM_ACCEPTANCE.md).

## Approved datasets

`reporting.datasets.dataset_registry` is the allowlist. Each adapter exposes named columns and builds rows through Django ORM queries. A report definition can select exposed fields, controlled exact/contains/list filters, date periods, grouping, numeric totals, and sorting. Invalid dataset keys, fields, filter operators, or ambiguous grouped columns fail model validation.

The MSWD pilot includes assistance volume and status, program accomplishments, aggregate reach, activity schedules, and department workload. Aggregate attendance remains aggregate and must not be presented as a list of named beneficiaries.

## Generation and governance

Generated outputs begin in `generated` state. Reviewers move them to `reviewed`; approvers may then mark them `approved`. Approving a replacement for the same report period supersedes the earlier approved run while preserving its file, checksum, and audit events.

A reviewed run that uses a pilot template cannot become `approved`. Authorized employees may still print or download it for side-by-side comparison. Print is offered only for archived PDF output; Download is offered for PDF, XLSX, and CSV. Both actions require download permission and remain inside the user's department boundary.

Every archived run records its department, report definition, template version, mapping checksum and validation summary, period, parameters, format, creator, timestamps, row count, output checksum, status, output file, and event history. Generation failures are saved as `failed` and never overwrite the preceding successful output.

Permissions are independently assignable for workspace access, definition management, template management, scheduling, generation, review, approval, download, and department-wide visibility. A permission never bypasses the employee's assigned department boundary. Department heads/OICs receive equivalent authority for their own department by role.

| Permission | Purpose |
| --- | --- |
| `view_reporting_workspace` | Open the reporting workspace |
| `manage_report_definitions` | Create and change controlled report queries |
| `manage_report_templates` | Create and approve layout versions |
| `schedule_reports` | Configure recurring runs |
| `generate_reports` | Generate manual outputs |
| `review_reports` | Mark generated outputs reviewed |
| `approve_reports` | Approve official outputs or superseding versions |
| `download_reports` | Download archived output files |
| `view_department_reports` | View report records across the assigned department |
| `manage_accountability_package_profiles` | Prepare readable Finance accountability-package recipes |
| `approve_accountability_package_profiles` | Independently activate a package recipe |
| `prepare_accountability_packages` | Assemble exact-period packages and reasoned successors |
| `review_accountability_packages` | Independently approve or return assembled packages |
| `export_accountability_packages` | Export approved or historically superseded package manifests |
| `manage_local_form_acceptance` | Inventory and prepare local Finance forms and reasoned successors |
| `witness_local_form_tests` | Independently decide practical form-test attempts |
| `review_local_form_acceptance` | Independently accept or return locked local-form evidence |
| `export_local_form_acceptance` | Export accepted or historically superseded form evidence |

Assign permissions through Django groups or individual user permissions. Prefer role-based groups in production so access reviews remain understandable.

## Finance accountability packages

The Finance accountability workspace connects approved cross-office outputs without copying or weakening their authority. A locally reviewed profile defines required and optional slots in plain language. An Accounting preparer selects only matching approved report, statement-note, signed-reference, or verified tax-filing evidence for the exact package period; submission pins the profile, source UUIDs, approval facts, and SHA-256 checksums for a different reviewer.

Draft and returned selections may be replaced only with a reason, retaining the earlier version. Approved profiles and packages use linked successors. Package correction never substitutes for a source transaction reversal or adjustment. Approved and historically superseded package manifests use the same TraceSync-ready export root. See [Finance accountability-package profiles and assembly](FINANCE_ACCOUNTABILITY_PACKAGES.md).

## Operator commands

Install dependencies and apply migrations before using the workspace:

```powershell
python -m pip install -r requirements.txt
python manage.py migrate
```

Configure the MSWD pilots without duplicating existing definitions:

```powershell
python manage.py seed_reporting_presets
```

Process due schedules safely:

```powershell
python manage.py run_scheduled_reports
```

Production checks for due schedules every ten minutes. The unique idempotency key prevents a repeated invocation from creating a duplicate output for the same scheduled period. Failed runs retain the same ledger identity and may be retried safely.

For production, invoke `run_scheduled_reports` from one scheduler on a frequent interval. The repository's Django cron configuration uses ten minutes. The command determines which schedules are actually due; do not create a separate operating-system job for every report definition.

Generated files live under Django's configured media storage. Back up that storage together with the database: the database preserves parameters, checksums, states, and audit events, while media storage preserves the corresponding output and reference files.

## Release verification

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test reporting
python manage.py test
```

Before deployment, also verify that the media location is writable, only intended groups hold reporting permissions, the scheduler uses the production settings module, and a synthetic scheduled run can be generated, reviewed, approved, and downloaded within its department boundary.

## TracePoint direction

GRAND remains the platform identity in this phase. The generated document-control identity and immutable run ledger prepare outputs for the later TracePoint records and physical-custody layer. TracePoint QR identities will be introduced with records and custody workflows, separately from Assistance's secure-link QR codes.
