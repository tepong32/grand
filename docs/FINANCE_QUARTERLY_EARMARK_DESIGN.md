# Quarterly planning and earmark semantics — investigation checkpoint

Implementation follow-up: [checkpoint 3A](FINANCE_QUARTERLY_PLANNING.md) now provides
the quarterly schedule and ARO connection. The investigation below records the
starting evidence; unresolved local certificate/reserved-column semantics remain open.

2026-09-18. This records the required investigation before implementation under
[FG-04/FG-05](FINANCE_FOUNDATION_GATE.md). No new planning or certificate lifecycle
is implemented by this document. The supplied eGAPS audit is evidence of observed
screens, not proof of their posting rules. eGAPS was not reopened or modified.

## Existing GRAND relationships

| Business fact | Current authoritative object | Established behavior |
|---|---|---|
| Proposed annual budget | BudgetVersion / BudgetProposalLine | Independently reviewed; not spendable |
| Approved appropriation | AppropriationAuthorization / AuthorizedAppropriationLine | Retained ordinance and immutable classified schedule |
| Released allotment | AllotmentReleaseOrder / AllotmentMovement | Independent posting changes released amounts |
| Withholding / deferral | Typed AllotmentMovement | Holds already released allotment; separate release/lift histories |
| Obligation | ObligationRequest / ObligationMovement | Exact source lines and dated certification; connects to payable route |
| Quarterly financial/physical plan | Only local-form starter 5A | No operational schedule, version or approval found |
| Procurement-specific earmark certificate | None located | Current holds have no certificate identity or obligation consumption link |

`budget/services.py:allotment_line_balance` computes executable allotment as released
less reserves and deferrals. Posting refuses a hold that exceeds released allotment
or undercuts certified obligations. This is not evidence that a procurement certificate
exists. Reuse this ledger for its actual purpose; do not rename it into a missing concept.

## Primary-source evidence and its limits

DBM's [2023 BOM, LBE Form 5A, printed page 193](https://www.dbm.gov.ph/wp-content/uploads/Issuances/2023/Local-Budget-Circular/Budget%20Operations%20Manual%20for%20LGUs%2C%202023%20Edition.pdf)
identifies quarterly financial allocations and separate physical targets for office
PPAs, grounded in the approved budget, prepared by the Department Head and approved
by the LCE. Its indexed form excerpt was readable; full direct retrieval timed out.
The repository's alternate 2024-reprint URL returned 404 during this investigation.
The newer barangay manual is not a substitute for municipal scope.

[Marilao's municipal Accounting charter, page 3](https://marilao.gov.ph/wp-content/uploads/2026/03/ACCOUNTING-CITIZENS-CHARTER.pdf)
was directly retrieved. It requires a Budget-issued appropriation/earmark certificate
alongside procurement support before Accounting issues a funds certificate. This
establishes that the two certificates can represent different workflow facts. It
does not establish Bocaue's numbering, capacity basis, expiry or correction policy.

No Bocaue-specific certificate procedure was located in the public searches. Absence
from search is not evidence of absence. Existing user authorization permits public
research and modular development; unavailable local paperwork must remain an explicit
acceptance gap rather than an excuse to abandon ordinary functionality.

## Minimum quarterly planning direction

Model a versioned schedule against exact immutable appropriation lines, with explicit
Q1–Q4 amounts and separate performance indicators/units/targets. Display annual
authority, planned sum and unplanned remainder. Display dated released, withheld,
deferred and obligated context separately. Do not divide the annual amount by four,
treat missing targets as achieved, or identify an unplanned remainder as a legal reserve.

Submission retains the source/control context. Independent approval does not create
allotment or obligation movements. A successor preserves prior approved schedules;
serialize successor approval on the existing authority parent so an older review
cannot displace a newer approved plan. Keep historical AROs and obligations unchanged.

Expose the approved plan in the ARO workflow to explain intended timing and any
documented deviation. A plan is not a new spending authorization. Do not silently
impose a quarterly legal cap without an established rule. Continue to enforce the
existing annual authority, release, withholding and obligation controls.

Tests must cover scope, explicit zero versus missing, negative/excess allocations,
independent review, UAT denial, retained versions, concurrent successor approval,
unchanged financial balances, exports and the ordinary browser workflow.

## Earmark decisions still required

The user confirmed on 2026-09-18 that the local capacity basis is **not yet confirmed**:
approved appropriation before ARO versus already released allotment. Preserve this
as an unresolved business rule, not an instruction to select either basis. Continue
ordinary Finance work while gathering evidence; do not let a guessed basis alter
certificate availability or obligation balances.

Additional primary evidence: [Pulilan's Budget charter, pages 1–2](https://pulilan.gov.ph/wp-content/uploads/2023/09/Budget.pdf)
separates a procurement appropriation certificate from the later obligation request.
It describes account charging, Budget preparation/review/signing and a retained log,
but its availability check names appropriation/allotment together. It therefore
supports a distinct lifecycle without resolving Bocaue's exact capacity rule. No
procurement thresholds or timings from that other LGU are adopted into GRAND.

Establish whether the certificate reserves appropriation, released allotment or a
distinct procurement envelope; which office certifies it; and its exact procurement
reference and numbering. Establish partial obligation consumption, unconsumed release,
correction dates, successor identity and history. Do not fabricate expiry, signatures,
cash availability or an automatic link from a generic reserve. The smallest eventual
adapter must reuse existing authority and obligation locks, consume a hold once,
and preserve original certification and correction evidence.

FG-04 now has the operational planning lifecycle linked above, with a supported planning
meaning; local reserved-column semantics remain unknown. FG-05 is a confirmed missing
certificate lifecycle with local policy details still unresolved. Neither is complete.
