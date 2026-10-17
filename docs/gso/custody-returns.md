# Witnessed returns to GSO

Published at2a7bb5f; see [CONTINUE](../CONTINUE.md) for release evidence. This working
physical-custody record is not an official COA form, employee clearance, HR separation
or liability finding.

Reuse `AssetTransfer` with a distinct return kind and the existing single-pending
movement constraint. A GSO receiving officer records a named custodian's return,
date, reference, observed condition, receiving location and witnessed facts. The
former custodian cannot record, upload evidence for, or confirm their own return.
Assignment changes only after a different authorized GSO officer verifies the
receipt and retained evidence. An evidence uploader cannot be the verifier.
Explicit GRAND action permissions and owner-office scope apply at every write;
Finance UAT roles and implicit superuser privileges do not grant these actions.

Inactive accounts and changed HR departments do not erase the retained identity.
Unlinked legacy names require reconciliation before this workflow. A pending handoff
or open disposal blocks a return. Existing maintenance can remain open: physical
possession and serviceability are separate facts. Observed return condition does
not change asset status, maintenance, acquisition cost or Finance rows.

Confirmation clears current employee custody, assigns the owning GSO location and
retains the original identity snapshot, return pointer, actors and audit events.
The workbench separates known GSO returns from unlinked legacy records. Subsequent
assignment uses a named handoff. Pending corrections use cancellation and a new
record; cancellation preserves assignment and evidence. Confirmed returns have no
destructive edit or reversal shortcut.

## Integrity and recovery

Migration0018 is additive: existing transfers remain handoffs; no returns are
invented. Asset-first locks serialize starts and decisions. Versions reject stale
decisions. Signed source tokens bind actor, asset, source custody and request UUID
for 30 minutes. Exact retries reuse the original record even after closure;
different content is rejected.

Private evidence uses established storage and upload validation: at most 20 files,
15 MB each and 100 MB total, recorded SHA-256 and size. Confirmation and download
check integrity and case-specific paths. Downloads are attachments with no-store
and nosniff. Owning GSO officers and the returning employee may read history through
GRAND's explicit view gate. A later custodian does not inherit return evidence.
Service events retain recorded facts and evidence metadata.

Backups must include both GRAND stores and private files, including
`inventory/custody_returns/`. Run `check_custody_return_evidence` after recovery.
The checker reports missing, changed, unsafe and orphan files without deleting
them. Database rollback cannot undo filesystem writes; investigate orphan findings.
Release does not include operator migration, role grants or deployment.

## Integration and remaining work

Tables remain in GRAND `default`, using protected native users and portable movement
UUIDs. No Finance foreign keys or journal entries are created. Accounting separately
owns valuation, repair treatment and liability decisions. HR-reference clearance
cases, unresolved-item decisions, official forms and confirmed-return corrections
remain future work. See [employee custody](employee-custody-design.md),
[COA sources](coa-requirements.md), [roadmap](inventory-roadmap.md) and
[validation](validation-2026-10-16.md).
