# HR-reference GSO custody review

Implemented and validated on `codex/hr-custody-review`, after clean fetched GSO
676bc29 and GRAND32ab046. This is roadmap item4's operational review case, not a
new HR registry, general records registry or clearance certificate.

GRAND still has no typed employee-separation event. Its `EmployeeProfile` provides
current department/identity, while `ProfileEditLog` is not a structured separation
authority. An explicit supplied HR request/reference and private document therefore
start the case. Account deactivation is never treated as termination. GRAND's
`DepartmentRecord` remains the general records authority; its approved association
types do not currently include GSO custody reviews. Do not monkeypatch that list or
duplicate the registry here. A future reviewed integration can file the operational
case through GRAND's records workflow.

Selected workflow: an owning-GSO officer records a request for a native user,
retaining the document and its digest. A draft records findings and coverage of
paper/legacy records. Submission captures named custody, tracked assets and pending
movements. A different officer, also different from the employee and original
source recorder, reviews unchanged findings and source evidence. Returned drafts
retain each earlier submission in events. Cancellation retains history. One open
case per employee/owning office prevents competing open review conclusions.

Outcomes describe outstanding named custody/movement or no current named items in
the reviewed office scope. Neither outcome establishes universal clearance, settles
financial liability or authorizes a salary hold. Legacy labels are not matched to
people automatically, and other offices are not silently included. Scope/coverage
notes are mandatory. New later custody makes the old as-of review stale.

Lock design: select current/pending/tracked asset IDs, lock those assets in order,
then lock the employee (the same target-user lock used by named handoffs), then the
case. Recompute the asset set after locking; reject a changed set rather than
locking a newly discovered asset while holding the employee lock. This preserves
existing asset-before-user order and prevents an incoming handoff from appearing
inside an allegedly empty review snapshot. Existing custody movement services own
all physical changes. Review services do not update HR, assets or Finance.

Private sources belong under `inventory/custody-reviews` in the existing private
storage root and must join coordinated recovery. The new models use protected
native user relationships, portable case UUIDs, generated nullable open-case
uniqueness, exact retained snapshots and immutable checksummed events. Populated
migrations, native lock races, independent review, inactive historical
custody, source-file corruption and recovery are validated; see the handoff.

The implementation includes owner-scoped list/search/create/detail screens,
actor-bound signed request/submission forms, private downloads, findings/submission,
independent review/return, cancellation and retained event history. The
`check_custody_review_evidence` command checks files without modifying them.
The local [employee search pages](employee-custody-design.md#employee-search-pages--2026-10-19)
remove the25-match ceiling while preserving active-profile visibility, explicit
inactive custody links and separate retained-review pages. They change no HR case
or clearance authority; the current handoff owns actual verification/version state.
Published code204df28 uses migration0021 for default-store case/event tables. It does not install
roles or permissions onto users. Current tests/release status remain in CONTINUE;
do not treat this branch as deployed or formally accepted.

The recovery rehearsal uses stopped synthetic paired SQLite stores, not an online
operator backup. Case history hashes detect accidental changes; they are not
cryptographic attestations against a database administrator rewriting all evidence.
General records filing, official clearance forms, unresolved-liability adjudication
and HR separation events remain separate future integrations.

See [custody review](custody-review.md), [named custody](employee-custody-design.md),
[witnessed returns](custody-returns.md) and [roadmap](inventory-roadmap.md).
