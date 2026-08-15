# GRAND reporting operations

GRAND's reporting platform turns approved application data into controlled departmental outputs. It is cross-department infrastructure piloted with MSWD; new departments add dataset adapters and presets without rebuilding the generation, scheduling, or approval engine.

The employee workspace is available at `/reports/`. Access is department-bounded and requires the reporting workspace permission, department-head/OIC authority, or superuser status.

## Existing government templates

Authorized template managers may attach PDF, XLSX, XLS, DOCX, PNG, or JPEG reference files. GRAND stores them as non-executable references unless an XLSX or PDF version is explicitly configured with one of the controlled mappers below. GRAND never runs embedded queries, scripts, macros, or template code.

Each usable layout is represented by a versioned `ReportTemplateVersion` containing its title, institutional header, certification text, signatory lines, footer, document-control prefix, logos, paper geometry, page-border behavior, and controlled layout settings. Technical approval permits manual or scheduled pilot generation. A separate department fidelity validation is required before a run can be approved as an official output.

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
6. Generate the same period through GRAND and the department's current process, then compare both outputs.
7. Record the comparison and department sign-off as fidelity evidence.
8. Only then validate the template for official report approval and distribution.

Use the [department template-intake checklist](REPORT_TEMPLATE_INTAKE.md) to inventory actual forms. Any coordinate, reserved range, or source-file change invalidates preflight; approved versions are immutable and must be replaced with a new version.

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

Assign permissions through Django groups or individual user permissions. Prefer role-based groups in production so access reviews remain understandable.

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
