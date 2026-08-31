# Finance payable relationships, recognition decisions, and transaction exports

F5.3 extends the governed F4.2 obligation-to-payable handoff without creating a second Budget authority ledger. It implements synthetic controls for valid one-to-one, one-to-many, many-to-one, partial, progress, final, and full-claim relationships; Accounting recognition/adjustment routing decisions; exact claim-to-allocation reconciliation; and portable transaction exports.

This is an implemented UAT control, not proof that every relationship or recognition treatment is locally accepted for every transaction variant. Public COA/DBM material is an official-requirement source only within its stated scope and effectivity. A reviewed local applicability decision, accepted form/schedule, named process-owner replay, and parent F5 exit-gate evidence are still required before official use.

## Authority and data boundary

- `ObligationRequest`, its correction lineage, and `ObligationMovement` remain the authoritative Budget record in the isolated Finance database.
- `PayableObligationAllocation` records versioned claim-capacity relationships against the certified original at the root of that lineage. It is a relationship/control ledger, not a second appropriation, allotment, or obligation balance.
- Every active relationship pins the obligation UUID, controlled number, current corrected amount, lineage checksum, claim relationship type, allocated amount, case UUID/reference, actor, reason, and version.
- A database constraint permits only one active version for the same obligation/case pair. Services lock the authoritative obligation while checking remaining capacity, so a concurrent duplicate or over-allocation cannot silently succeed.
- The Voucher Workbench `BudgetObligation` and classified lines are explicitly labeled compatibility projections for the existing DV path. A single-obligation case keeps its F5.1 compatibility label; a consolidated case carries the relationship-projection label. Neither projection can replace F4.2 authority.
- The earlier single `linked_voucher_case_public_id` is retained only as a first-case compatibility pointer. Active relationship records are authoritative for multi-case downstream issuance checks.

## Relationship rules

The requesting office selects one certified original with available claim capacity when opening a case, then may add other obligations while the case remains in payable preparation.

- **One-time/full** consumes the exact remaining capacity of that obligation.
- **Partial** allocates less than the available obligation capacity and retains a balance for a later supported claim.
- **Progress** does the same while identifying a locally accepted progress-billing route.
- **Final** consumes the exact remaining capacity. If the supported final claim is smaller, Budget must first post a governed pre-DV obligation adjustment.
- Multiple active cases may consume separate portions of one obligation, producing a one-to-many relationship.
- One case may aggregate active allocations from several obligations, producing a many-to-one relationship.
- Submission is blocked unless active allocations equal the payable claim control exactly. The case page and export show claim total, allocation total, and difference.
- A required documentary checklist still applies independently; relationship reconciliation does not imply document completeness or Accounting acceptance.

## Modification allowance and guided correction

The convenience modification window is intentionally narrow and reasoned.

1. While the case is in requesting-office payable preparation and no DV/check exists, the user may revise the claim control, add an obligation, or create a successor allocation version.
2. Entering zero on an allocation revision creates a retained cancelled successor instead of deleting history.
3. Accounting may return an accepted case from DV preparation to the same requesting-office preparation stage before a DV exists.
4. Budget may post a governed obligation adjustment, return, or cancellation before downstream DV/check issuance. Existing payable allocation snapshots then become stale and cannot advance.
5. The requesting office uses **Reconcile obligation link** to version stale allocation snapshots after reviewing the corrected capacity. The claim/allocation difference must return to zero before resubmission.
6. Once a DV exists, payable claim/allocation editing closes. Once a DV or check exists, Budget obligation-only correction also closes. Users must use the later coordinated voucher, JEV, and payment reversal/cancellation route rather than rewrite earlier facts.

Every guided change produces append-only Voucher events plus retained Budget-side allocation versions. Idempotency keys and case state versions protect double submission and stale pages.

## Accounting decisions

Independent Accounting review now records two separate, reason-backed routing decisions before accepting a payable:

- recognition through the governed DV/JEV route, accrual before settlement, settlement of an existing payable, or a liquidation/non-payment recognition decision; and
- no obligation adjustment required, a governed pre-DV adjustment reflected, or an intentionally retained partial/progress balance.

These are pinned F5 routing decisions for later transaction-specific F7 posting policy. They do not themselves post a JEV, establish a ledger mapping, or prove that a treatment is locally accepted. A returned intake clears the decisions so resubmission receives a fresh independent review.

## Portable transaction export

Users with voucher-audit authority can export the case from its detail page. The CSV includes:

- shared case identity, stage, office, payee, transaction variant, claim reference, and control totals;
- every active obligation UUID/number, relationship type, allocation amount/version, corrected-amount snapshot, and checksum;
- recognition and obligation-adjustment decisions and bases; and
- pinned documentary rule, decision, evidence reference, and reviewed authority reference.

The browser receives the same bytes atomically retained below `GRAND_EXPORT_ROOT` using:

`department / user / finance-payable-transactions / year / month / artifact.csv`

The adjacent `.manifest.json` records SHA-256, byte length, source case/state, claim/allocation totals, department, exporting user, and the explicit non-official-form boundary. Copy or synchronize the entire export root so TraceSync and ordinary offline safekeeping retain artifacts beside their manifests.

## Internal How-Tos

The floating non-modal `?` window now publishes successor versions for:

- requesting-office relationship selection, exact control reconciliation, guided pre-DV revisions, stale-handoff recovery, and portable export;
- Accounting review of relationship shape/freshness plus recognition and adjustment decisions; and
- DV preparation, including return to requesting-office correction before DV creation.

Guide visibility remains live from the employee's current department and permission. Private step checkmarks remain a learning aid only: they are not transaction status, approval, attendance, performance evidence, or history assigned to a successor.

## Validation evidence

The F5.3 synthetic test matrix covers:

- undersized final-claim rejection and exact remaining-capacity rules;
- one obligation shared by multiple cases and one case supported by multiple obligations;
- duplicate-active allocation database protection and capacity-locked service writes;
- immutable/successor-only allocation history and reason-required claim revision;
- governed pre-DV Budget adjustment, stale payable rejection, and snapshot reconciliation;
- claim/allocation zero-difference submission, independent recognition/adjustment decisions, and DV preparation;
- modification closure after DV issuance and downstream Budget-correction blocking; and
- byte-identical TraceSync-ready CSV archive/manifest evidence.

The repository validation gate additionally runs Budget/Voucher regressions, the full project suite, migration-drift detection, Django system checks, Git whitespace checks, local Markdown-link validation, and database-file change checks.

## Remaining acceptance work

F5.3 does not close the parent F5 exit gate. Each enabled variant still needs a redacted completed replay, accepted document/applicability rules, official/local form comparison where applicable, exception paths, named-office sign-off, and exact control-total reconciliation. F6.1 remains the next software dependency for controlled print/version/reprint state, mandatory finance custody linkage, and returned wet-signature packet gates.
