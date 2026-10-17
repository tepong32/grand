# GSO general office records in GRAND

2026-10-17 implementation checkpoint, `codex/gso-office-records-entry`, baseline
ce845fc. Publication and validation status: [CONTINUE](../CONTINUE.md).

## Selected approach

Reuse GRAND's existing `records.DepartmentRecord`, files, events and workflow.
The GSO dashboard links to `records:workspace`; it neither creates records nor
queries their contents. The target uses the employee's assigned department and
native Records authorization, confidentiality and workflow. Inventory grants do
not grant Records access. Native Records currently permits relevant grants,
department heads and superusers within its assigned-office scope; the GSO entry
does not rewrite that policy or claim Finance UAT rules govern Records.

The entry is shown only for an authenticated active user actually assigned to a
GSO department, with native Records workspace access and an available named route.
A superuser's inventory fallback office is not used to select a different Records
registry. No link appears in the standalone shell, with an absent app/route, or
when native workspace access is revoked. Existing native actions still authorize
every destination request; a visible navigation link is not a permission grant.

## Existing native workflow and limits

Inspected actual GRAND candidate a533482 (remote primary32ab046):
`records/models.py`, `access.py`, `forms.py`, `services.py`, `views.py`, `urls.py`
and tests. DepartmentRecord already supports general office records, report filing,
classification, internal/restricted/confidential visibility, custodian, review/
approval, replacement, retention and legal-hold metadata. Keep those records and
files in their existing default-store/managed media backup, with native users and
departments. This change supplies no new schema or import identity mapping.

Do not duplicate the registry in GSO or pass arbitrary model references through
its generic relation. `RecordAssociation.ALLOWED_MODELS`, source ownership and
native filing views do not currently support inventory sources. Therefore this
entry carries no asset/receipt ID, automatically files no GSO output and adds no
association. A future governed source integration needs explicit native support
and authorization/retention/recovery review; matching free text is not a link.

Use the registry for correspondence and general departmental documents through
its native workflow. It does not certify the legality of a retention schedule,
loss/relief decision, COA form, or official signature. Native filing and production
media/recovery acceptance remain GRAND responsibilities; navigation tests do not
claim a full security audit of that module. Finance production remains NO-GO as
stated by its own handoff. No Finance code or deployment changed here.

## Validation scope

Verify absent standalone route, current native grant/revocation, no cross-office
superuser fallback, confidentiality and foreign-owner denial, and real native
creation from the linked workspace without inventory or Finance writes. Run the
existing native Records suite alongside these integration cases. No GSO migration,
new storage namespace or data transform is involved; the previous paired recovery
is not presented as a new Records-specific recovery result.


Local acceptance for this entry passed: standalone fallback, actual GRAND SQLite
and native MySQL17-test runs (3 GSO integration plus14 Records tests), and browser
GSO dashboard→native registry→draft creation at desktop/mobile sizes. See the
validation record for commands, original harness cwd failures and final results.
