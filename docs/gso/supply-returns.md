# Supply returns linked to original issues

Implementation checkpoint2026-10-17. This is an operational return-to-usable-stock
workflow, not an official return form, disposal decision or Accounting reversal.
Start from Document return on an original issue in the supply item's history.

## Retained observations and acceptance

Inventory0023 adds default-store `SupplyReturn` and `SupplyReturnEvent`. The case
retains its public UUID, original protected StockMovement issue, quantity, person
returning the goods, observation date, condition, reference, private evidence,
source snapshot and cost-basis explanation. A signed actor/issue/source-bound
identity permits exact entry retries. Incorrect cases are cancelled and recorded
anew; supplied facts/evidence are not edited in place.

A different explicitly authorized receiving officer must check the goods and
confirm suitability for usable stock before acceptance. Review also requires the
existing receive_stock grant. The new explicit grants are record_supply_return,
review_supply_return and view_supply_return. No migration assigns them.
GRAND UAT users cannot mutate, and a
superuser flag alone supplies no grant. Pages and private downloads stay within
the owning GSO office. Observation dates cannot precede the issue or be in the future.

Acceptance locks the item before the case, rechecks original issue/lot facts,
retained history and evidence, and caps accepted returns at the original issue
quantity. A selected allocation has its own quantity ceiling. Competing pending
cases do not reserve capacity: the acceptance transaction must recheck it.
Prior return histories are verified before computing capacity. Changed/stale case
versions cannot repeat acceptance. Return movement, optional new FIFO lot, decision
and event commit atomically. The original issue and allocations remain unchanged.

Decline records why goods cannot enter usable stock and where they are held or
referred; it creates no stock movement. Cancellation retains an incorrect request.
Neither action disposes of goods, provides a quarantine inventory system or removes
physical accountability. A subsequent reconsideration uses a new evidenced case;
previous decisions remain visible. Accepted cases cannot be cancelled to erase stock.

## Costs and lineage

One case may identify one original FIFO allocation if documents/physical markings
support that identity. Mixed documented lots use separate quantities/cases. The
return retains the selected source lot's original nullable cost; it never computes
a weighted average or selects a lot merely because it was first issued.
Unidentified lots explicitly return at unknown cost, including where an original
issue cost was never captured. Unknown is not zero. Overall issue quantity remains
bounded even when allocation identity is unknown; unknown returns do not assert a
particular original lot. Accounting must resolve any valuation uncertainty separately.

A FIFO return creates a new lot at the actual acceptance time through the existing
stock service. This is the existing operational FIFO sequence, not an assertion of
LGU financial costing policy. Original allocations are not reopened or backdated.
Further issues can draw from the new lot, preserving its known or unknown cost.
The case links original issue, optional allocation and accepted return movement.
An issue originating from a requisition retains that relationship; return does not
reopen its requested quantity or rewrite fulfilled/closed historical status.

Unlinked legacy return movements block this workflow for the item until their
lineage is reconciled. Matching a name, date or reference does not establish which
issue they reversed. No automatic historical association or legacy repair tool is
implemented. Quantity/cost attribution to Accounting entries also remains separate.

## Evidence and recovery

Private files live under `inventory/supply-returns/<case UUID>/`. Include this
namespace with the default/finance pair. `check_supply_return_evidence` reports
missing, changed, unsafe and orphan files without deleting or changing anything.
Storage is not transactional; a failed DB transaction can leave an upload for
reconciliation. Acceptance validates file hash/size, source and prior history.
Missing evidence still permits reasoned decline/cancellation if case history is intact.
Checksums detect retained-data drift; they are not tamper-proof against a privileged
operator rewriting both rows and hashes. Preserve source snapshots and UUIDs in
future data imports; native foreign keys need an explicit reviewed identity map.

## Source boundary

The [COA matrix](coa-requirements.md) and [request design](stock-request-design.md)
remain the authority register. No verified current municipal return-costing rule
was found in this follow-up search. The stock limits, review and unknown-cost
handling above are engineering controls, not claimed COA-prescribed form rules.
A [15 May2024 PHALGA-hosted presentation](https://www.phalga.org/assets/downloads/19thANC/Download/Updates-Latest-Guidelines-and-details-on-the-COA-Circular-2020-004.pdf)
discusses the GAM deferment on slides8–11 and labels later enhancements as proposed;
extracted text was read. It is a dated corroborating research lead, not proof of current
reinstatement, complete circular text or accepted municipal forms. Do not substitute
NGA, barangay, private study notes or proposed changes for applicable municipal authority.

See [validation](validation-2026-10-16.md), [handoff](../CONTINUE.md) and
[GRAND integration boundaries](grand-integration-design.md).
