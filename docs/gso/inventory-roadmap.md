# GSO inventory roadmap

This roadmap prioritizes practical controls for equipment, vehicles, and consumable supplies. Each feature is developed on its own branch, documented, checked, and merged before the next begins. Accounting decisions and official forms remain subject to confirmation by the LGU Accountant and relevant COA auditor.

## Immediate sequence

2026-10-18 autonomous resumption: the [working doctrine](../../AGENTS.md#working-doctrine--2026-10-18)
permits coherent local feature batches on isolated GRAND branches. ICS/SPC working
draft preparation is implemented locally beside PAR; see
[scope and boundaries](property-record-design.md#working-draft-preparation--2026-10-18)
and [current validation](../../CONTINUE.md). This does not authorize merging or
publishing the batch, certify an official form or complete a class/fund SPC.
The earlier integrate-then-pause instruction was fulfilled by v0.7.176 and is
superseded for local development by the current mission.

User direction2026-10-17: reviewed [integration readiness](grand-carryover-checkpoint.md),
VM checkpoint, then actual carry-over and parallel GSO/Finance branches of GRAND.
Do not keep developing two independent shells indefinitely. Preserve remaining
system requirements while separating development integration from production acceptance.

## Current foundation

The app supports an asset register with department scope and permissions, optional FIFO for consumables, asset handoffs, disposal requests with protected evidence, and GSO physical verification rounds with immutable check history. The physical-count reconciliation baseline (`64e458a`) includes count dates, unregistered findings, private Accounting CSV snapshots, variance review, and a working reconciliation export. Official RPCPPE form generation remains out of scope until the LGU Accountant validates the local format and sign-off process.

## Alignment checkpoint — 2026-10-16

The user expanded the goal to a practical LGU inventory and general-services records
system, aligned with GRAND's parallel Finance work. [The data design](grand-integration-design.md)
maps actual GRAND records, separates implemented prerequisites from proposals and
defines the next receiving slice. [The COA matrix](coa-requirements.md) records
verified sources and incomplete primary-text review. [CONTINUE](../CONTINUE.md)
owns immediate state; [validation](validation-2026-10-16.md) owns test evidence.

The first prerequisite supplies portable inventory UUIDs, GRAND-matched runtime
versions, production settings checks, stock-owner enforcement and runtime-data
exclusion from Git. The optional GRAND Finance adapter and reviewed claim-support
workflow are implemented; operator installation remains pending.
Receiving/inspection is now implemented as described in [receiving operations](receiving.md).
An optional GRAND claim-support workflow now provides reviewed amount attribution;
see [claim support and limits](claim-attribution.md). Reviewed documentary receipt
cost amendments and [reviewed recognition amount mappings](receipt-journal-mappings.md)
are implemented; physical quantity/cost-component allocation and valuation remain
incomplete. The [recognition source preview](journal-source-preview.md) inspects
existing posting evidence without allocating or changing it. Continue the
maintenance/clearance/stock-count sequence alongside these financial integration gaps.
Later general-office records should use
GRAND's records/custody/HR capabilities where available instead of duplicating them.

## Placeholder output direction — 2026-10-17

The user authorizes fill-in LGU, local-form, numbering and signatory placeholders.
PAR preparation is implemented as a nonpersistent form/print preview; unknowns
remain blank and the draft label remains visible. Use Property → Prepare PAR with
placeholders. No auto-number, signature, custody or accounting event is created.
Proceed to ICS/SPC preparation with the same clear unknowns; local official-form
acceptance is separate from development of these drafts. Routine checks stay focused;
broader tests are reserved for critical data/security/integration/release checkpoints.

## Planned features, in order

The [completion audit](completion-audit.md) separates remaining engineering work
from local policy, data and operational acceptance. Linked follow-up acceptance
of delivered unresolved quantities is implemented; see [its design](receiving-followups.md)
and CONTINUE for validation/publication. The user selected clerical overstatement
before use as the first accepted-quantity correction case. The
[selected workflow](receipt-quantity-corrections.md) traces custody, stock/FIFO and
Finance support. The correction workflow is published at33cd899; CONTINUE records validation. Changed inspection decisions, returns after use and
Accounting reversals remain distinct cases, not automatic extensions of this one.
Do not expand conditional vehicle/general-office scope without a concrete use case.

The [property-record workflow](property-record-design.md) now retains supplied
treatment/useful-life evidence and independent documentary verification through
migration0024. Native Finance association now has an explicit GSO request and
independent Finance review in adapter0005, published at6c1ba3e. A scoped property
working register now exposes latest supplied class/fund facts and documentation
gaps across assets; official class/fund SPC output remains planned. Keep physical
cost allocation as a distinct gap.

Migration0025 now retains supplied acquisition dates, references and receipt-item
numbers within the existing reviewed property packet, preserving preexisting
history and unknown values. This is an SPC source prerequisite; numbered movement
documents, opening reconciliation, historical balances and accepted output remain.
Source tracing found disposal lock-order/fresh-authority gaps; these are now fixed
before card movement integration. Disposal0026 evidence integrity and service-level
upload validation are implemented with local validation complete. Reviewed movement annotations/openings are now published atce845fc, preserving
historical evidence unknowns; see the movement design for reconstruction limits.
See property-record-design for the actual receipt/handoff/return/disposal mapping.

Supplies follow-up: [request and issue design](stock-request-design.md) records
implemented supplied-approved-requisition entry, independent document review,
partial issues, unavailable observations and remainder closure. Migration0022
links explicit request lines to existing stock movements in default. Migration0023
adds [reviewed original-issue returns](supply-returns.md) without erasing fulfillment.
Accepted official outputs and legacy return reconciliation remain future work; no Finance posting
or reservation is inferred. Stock form retry protection remains in place.

### 1. Annual physical count reporting and reconciliation — implemented

Extend verification rounds with an explicit count/as-of date, a way to record items found during the count that are not in the register, and a discrepancy follow-up process. Produce a reviewable comparison between the GSO register, physical findings, and Accounting's asset records. Begin with controlled import/export and manual review; do not update Finance records automatically.

Physical-check follow-up now requires fresh review after each new observation;
previous decisions remain in history, and signed stale reviews are rejected.
This does not adjudicate losses or change asset custody. See CONTINUE for validation.

The working comparison distinguishes found and matched, differences in serial/department/account/cost/date, not found, register-only, Accounting-only, ambiguous tags, and items found outside the register. It keeps the original private Accounting CSV and normalized snapshot, records review history, and exports a working reconciliation CSV. It does not generate the official RPCPPE form; validate its fields and sign-off process with the LGU Accountant before creating that output.

COA's published guidance describes an annual PPE physical count presented on RPCPPE (Appendix 71) as of December 31 and submitted to the auditor by January 31. DBM's LGU Internal Audit Manual also recommends periodic physical counts reconciled with Accounting and GSO records. The local process and current form instructions must be confirmed before relying on an app-generated report.

### 2. Asset receiving and tagging — initial workflow implemented

Draft/returned corrections, protected evidence, independent acceptance, stock/asset
materialization and native duplicate protection are implemented. Official forms,
accepted-receipt reversals remain future work. [Linked follow-up inspection](receiving-followups.md)
implements unresolved-remainder acceptance; see CONTINUE for validation/publication.
[Reviewed documentary cost amendments](receipt-cost-corrections.md) now retain
correcting evidence and independent decisions without rewriting accepted inventory
or Finance values. Original/effective cost and stale support remain visible.
Quantity reversal, valuation/allocation and official outputs remain future work.
Finance integration has not been installed.
Ordinary receipt-linked asset edits now retain accepted cost, quantity, supplier
and purchase-order facts; documentary corrections use the existing amendment
workflow. Historical divergence is not automatically repaired.

Add a guided GSO intake for newly delivered equipment and vehicles. Capture delivery/inspection date, quantity accepted, supplier and purchase references, the receiving/inspection reference, and the person or office taking custody. Assign or record a property tag and check for possible duplicates by tag, serial, or chassis number before the asset becomes part of the active register. Keep Accounting's official classification and account mapping reviewable; the intake flow must not invent those values.

Follow the [receipt header/line design and acceptance examples](grand-integration-design.md).
Include supplies, partial/rejected deliveries, independent acceptance, retained
evidence and duplicate-submit protection. Do not attach a single voucher ID to an
asset or auto-post from a receipt. Add reviewed Finance attribution only after the
physical workflow works and its current GRAND integration dependencies are checked.

### 3. Maintenance history

Implemented on `codex/asset-maintenance`; see [workflow and limits](maintenance.md)
and [GRAND handoff](../../CONTINUE.md) for release status. Local development now
adds attributable notices beside unchanged closed records; applying authoritative
corrected values remains DECISION-GSO-003. Native concurrency, browser,
populated migration and synthetic evidence recovery pass. No operator deployment
or installation in GRAND is implied.

Add a simple repair/work record attached to an asset: reported problem, date, service provider, work performed, cost/reference, current status, and supporting documents. Let authorized GSO users record when an asset enters and leaves maintenance. Preserve history and avoid turning this into a full procurement or work-order planning system in the first version.

### 4. Employee movement and exit clearance

Named employee custody is published at236c5e1; see
[verified HR boundary and selected relationships](employee-custody-design.md).
GRAND currently provides employee identity/current department, but no verified
separation event. Named-custody migration, services and signed staff screens are implemented;
official clearance remains unimplemented. The [custody review workbench](custody-review.md)
is published atfb2eae2 as the next prerequisite. No operator migration or deployment.

[Witnessed returns](custody-returns.md) are published at2a7bb5f:
independent GSO confirmation, protected receipt evidence and retained former custody,
with no HR clearance or Finance decision. See CONTINUE for validation evidence.
The [HR-reference review case](hr-custody-review.md) is published at204df28: supplied private request, office findings, retained
as-of custody and independent review. It does not create HR separation events,
universal clearance, financial holds or duplicate GRAND's general records registry.
Unresolved-liability decisions and accepted official outputs remain future work.

After GRAND HR integration is available, show assets assigned to an employee when their department changes or an exit is initiated. Let GSO and the employee's office record return, acknowledged handoff, or a documented unresolved item. The process must use HR as the source for employee status, preserve the asset transfer trail, and avoid blocking unrelated HR actions automatically.

### 5. Consumable stock counts and low-stock reminders — initial workflow implemented

The [ledger and count design](stock-counts.md) records the implemented current-day
workflow: one-item observations with shared sheet references, private evidence,
independent review and exact linked adjustments through the existing stock service.
Stale ledger/item bases require cancellation and recount; zero variance creates no
fake movement. Active items at/below a positive configured minimum are flagged.
Historical count sheets and official supplies reports remain separate reconciliation
and acceptance work. See CONTINUE for validation/release status. HR-reference
clearance remains separate; never derive employment status from account activation.

Let GSO record a dated physical count for consumables, compare counted quantity with the movement-ledger balance, and record a reasoned adjustment after review. Add a clear low-stock indicator using the existing minimum-stock value. Keep ordinary supplies quantity-only by default; FIFO remains optional per item. Validate any official supplies count report with the LGU Accountant before adding a form export.

## Receiving authority alignment

Receiving now shares GRAND explicit action grants and read-only UAT restrictions,
with service/HTTP/control parity and no caching. This prerequisite precedes reviewed
cost amendments. Legacy asset, transfer, disposal and verification checks are now aligned with
explicit GRAND grants and UAT write denial; read-only history remains scoped. See CONTINUE
for current validation and publication status.

## Deliberate boundaries

The [native Finance link request and review](property-finance-links.md) is implemented
and published at6c1ba3e. It resolves the distinct GSO/Finance ownership boundary
before class/fund output. See CONTINUE for actual publication state.

- Use GRAND's shared users, departments, and Finance interfaces when integrating; do not create duplicate user or finance systems in this module.
- Keep Finance reconciliation reviewable and traceable. Do not automatically post journal entries, depreciation, write-offs, or accounting corrections from GSO workflows.
- Do not promise COA compliance based only on an export. Keep the applicable signatories, source records, and approved local procedures visible in the workflow.
- Defer public portals, AI classification, broad procurement management, and complex warehouse features until staff have validated the core register, custody, count, and reconciliation workflows.

## References

- [COA: When to submit the Report on the Physical Count of PPE](https://www.coa.gov.ph/FAQS/when-should-the-inventory-report-of-property-plant-and-equipment-be-submitted/)
- [DBM: Internal Audit Manual for Local Government Units, 2023 edition](https://www.dbm.gov.ph/wp-content/uploads/Issuances/2023/Local-Budget-Circular/IAM-for-LGUs-2023-Edition.pdf)
- [DBM-COA: Joint Circular No. 2024-01, Revised Manual on the Disposal of Government Properties](https://www.dbm.gov.ph/index.php?catid=342&highlight=WyJkaXNwb3NhbCJd&id=2627%3Ajoint-circular-no-2024-01-dbm-coa&view=article)

Disposal source integrity prerequisite has passed local validation on
`codex/disposal-evidence-integrity`:0026 preserves legacy unknown hashes, validates
new uploads in services and adds read-only reconciliation. This does not supply
movement numbering/openings, official SPC output or Accounting valuation.


The documented movement/opening workflow is implemented on
`codex/property-movement-records`; see [its design](property-movements.md).
Foundation0027, reviewed records, source-checked projection and entry/review/history
screens passed native GRAND, browser and recovery gates. See CONTINUE for actual
publication state. Official SPC layout, complete imported history/local numbering
and accepted office procedures remain separate work.


General office filing entry: `codex/gso-office-records-entry` reuses GRAND Records
from the GSO dashboard with native permission and actual assigned-office checks.
See [scope and existing native authority](office-records.md). No duplicate registry
or unsupported inventory association is introduced; official outputs and governed
operational source integration remain distinct gaps.
