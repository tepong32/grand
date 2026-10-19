# GRAND department records operations

GRAND's Records workspace registers the official files and governed references that a department must retain. It is a cross-department capability available at `/records/`; it does not replace Assistance, Programs, Citizen Review, or Reporting as the system where operational work is performed.

## Reference in place

Existing operational objects stay authoritative in their original app:

- Assistance requests and reviewed request documents remain in Assistance.
- Citizen service profiles remain in the canonical `CitizenProfile` register.
- Programs and activities remain in Social Welfare Programs.
- Approved report outputs remain in Reporting with their exact template snapshot, parameters, checksum, and run ledger.

The Records registry stores a typed association to these objects. It does not copy their files. A new `RecordFile` is created only when an employee uploads a genuinely separate department file. Each new file is validated, size-recorded, and assigned a SHA-256 checksum.

This split prevents two “official” copies from silently diverging while still giving records custodians a department-wide register.

## Lifecycle

1. An authorized employee registers a draft and links an operational source or uploads a supporting file.
2. The draft is submitted for review.
3. An authorized approver confirms it as an official record. Identity and descriptive fields become immutable; corrections require a new record version.
4. A retention manager may move the record to the archive.
5. An approved replacement may supersede an approved or archived record. The old record, files, and audit history remain intact.
6. An archived record can be marked disposed only after its disposition date and when no legal hold is active. Disposed metadata is immutable and its files cannot be downloaded.

Approved Reporting outputs can be filed directly from their run page. Only department-validated official outputs qualify, and repeated filing is idempotent.

## Confidentiality and department boundaries

Every record belongs to one department. A permission never grants access across an employee's assigned-department boundary. Restricted and confidential entries are excluded from lists, searches, and object routes unless the employee also has `view_restricted_records`.

| Permission | Capability |
| --- | --- |
| `view_records_workspace` | Open the assigned department registry and internal entries |
| `manage_department_records` | Register drafts, attach allowed sources, and add files before approval |
| `review_department_records` | Review and return submitted entries |
| `approve_department_records` | Approve and supersede official records |
| `download_department_records` | Download active files through an audited endpoint |
| `manage_record_retention` | Update retention controls, archive, and record disposition |
| `view_restricted_records` | See restricted or confidential records in the assigned department |

Department heads/OICs and superusers receive equivalent authority within the same department-scoped access contract. Production roles should still follow least privilege and separation of duties.

## Controlled download and audit behavior

Downloads do not expose media paths directly. GRAND checks department, confidentiality, download permission, active-file state, and disposition status, then records the actor, time, record state, file/source identity, and checksum where available.

For separately uploaded `RecordFile` documents, the download also requires the
retained SHA-256 and size, a safe path beneath the configured filesystem storage
root, and the owning record's UUID namespace. The original department folder is
retained across department-slug renames; it does not grant cross-office access.
The shared `src.file_integrity` function checks and rewinds the same open handle
that is passed to `FileResponse`. Inventory's existing strict row API remains
compatible. No integrity baseline is invented for legacy or altered metadata.

Missing, modified, unsafe or unverifiable uploads return an unavailable-document
404 before any successful-download event. A valid response retains attachment
filename/type/length handling and adds `Cache-Control: private, no-store`. The
existing event describes a verified download starting, not proof of delivery or
client receipt. Verification or audit failures close the opened file. Approved,
archived and superseded records retain the same visibility rules; disposed records
remain denied. No permission, retention, approval or financial workflow changes.

This checked-upload path requires a qualified local filesystem storage root.
Other storage backends fail closed pending their own integrity/recovery design.
Reading and streaming one handle prevents an unchecked reopen; it does not make
storage immutable against concurrent in-place writes. Protected storage and
production recovery qualification remain operational requirements. Linked
operational-source downloads are a separate existing route; this upload fix does
not establish a security audit or change export policy for Reports, Vouchers or
Assistance. No Finance readiness or formal acceptance follows from these tests.
Uploads still use the existing `MEDIA_ROOT`; the development URL configuration
serves media when DEBUG is enabled. This endpoint check does not protect a known
file URL served directly by a web server. Excluding confidential Records uploads
from unauthenticated media serving and qualifying their storage/recovery remain
explicit production blockers; no deployment configuration or file migration is
performed by this change.

The append-only event view records creation, file additions, review transitions, approvals, retention changes, downloads, archival, supersession, and disposition. Database administrators should protect this history with the same backup and access controls as the source records.

## Retention governance

Retention years, the governing basis, start date, computed or assigned disposition date, and legal-hold state are explicit fields. GRAND enforces chronology and blocks premature disposition, but it does not invent a legal retention schedule. The responsible office must enter the schedule required by applicable National Archives, COA, DILG, agency, or local rules.

Disposal in this phase records the governed lifecycle decision and blocks future download in GRAND. Physical destruction, transfer, inventory, and acknowledgement belong to the later TracePoint custody phase and require separate policy and implementation review.

## Verification

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test records
python manage.py test
```

Before deployment, verify group permissions, department assignments, restricted visibility, storage backups, retention schedules, legal-hold handling, and a full draft-to-disposition exercise using synthetic records.
