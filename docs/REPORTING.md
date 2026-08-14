# GRAND reporting operations

GRAND's reporting platform turns approved application data into controlled departmental outputs. It is cross-department infrastructure piloted with MSWD; new departments add dataset adapters and presets without rebuilding the generation, scheduling, or approval engine.

## Existing government templates

Authorized template managers may attach PDF, XLSX, XLS, DOCX, PNG, or JPEG reference files. GRAND stores these as non-executable references only. An uploaded file does not become an official generator and GRAND never runs embedded queries, scripts, macros, or template code.

Each usable layout is represented by a versioned `ReportTemplateVersion` containing its title, institutional header, certification text, signatory lines, footer, document-control prefix, and controlled layout settings. The version must be approved before manual or scheduled generation. This lets an office retain a familiar form while its approved fields are mapped safely.

PDF is best treated as a visual or fixed-form reference. Spreadsheet and Word references are usually easier to map when tables expand. A scanned form can also be retained as a reference, but it needs a reviewed overlay or native layout before use.

## Approved datasets

`reporting.datasets.dataset_registry` is the allowlist. Each adapter exposes named columns and builds rows through Django ORM queries. A report definition can select exposed fields, controlled exact/contains/list filters, date periods, grouping, numeric totals, and sorting. Invalid dataset keys, fields, filter operators, or ambiguous grouped columns fail model validation.

The MSWD pilot includes assistance volume and status, program accomplishments, aggregate reach, activity schedules, and department workload. Aggregate attendance remains aggregate and must not be presented as a list of named beneficiaries.

## Generation and governance

Generated outputs begin in `generated` state. Reviewers move them to `reviewed`; approvers may then mark them `approved`. Approving a replacement for the same report period supersedes the earlier approved run while preserving its file, checksum, and audit events.

Every archived run records its department, report definition, template version, period, parameters, format, creator, timestamps, row count, checksum, status, output file, and event history. Generation failures are saved as `failed` and never overwrite the preceding successful output.

Permissions are independently assignable for workspace access, definition management, template management, scheduling, generation, review, approval, download, and department-wide visibility. A permission never bypasses the employee's assigned department boundary. Department heads/OICs receive equivalent authority for their own department by role.

## Operator commands

After migrations, configure the MSWD pilots without duplicating existing definitions:

```powershell
python manage.py seed_reporting_presets
```

Process due schedules safely:

```powershell
python manage.py run_scheduled_reports
```

Production checks for due schedules every ten minutes. The unique idempotency key prevents a repeated invocation from creating a duplicate output for the same scheduled period. Failed runs retain the same ledger identity and may be retried safely.

## TracePoint direction

GRAND remains the platform identity in this phase. The generated document-control identity and immutable run ledger prepare outputs for the later TracePoint records and physical-custody layer. TracePoint QR identities will be introduced with records and custody workflows, separately from Assistance's secure-link QR codes.
