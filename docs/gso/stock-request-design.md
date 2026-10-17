# Supplies request and issue trail

Implementation checkpoint2026-10-17. Supplied requisition entry, independent
document review, partial issues, unavailable observations and remainder closure
are implemented. [Original-issue supply returns](supply-returns.md) are implemented
with independent usable-stock acceptance and retained known/unknown cost. This operational
trail does not establish official RIS compliance.

## Verified source boundary

[BIR RMC5-2004, reproducing GAFMIS Circular Letter2003-006 of24 November2003](https://lawphil.net/administ/bir/rmc/rmc05_04.pdf)
includes LGUs among its addressees. Its section3 describes submitting an approved
RIS to the supplies/property unit, releasing available items, and indicating
unavailability on the RIS before returning it to the requisitioning office.
Section2 describes a temporary suspension of SAI use under the manual NGAS and an
alternative availability check. This is historical primary-document evidence,
not proof of the full current municipal process or permission to treat a new
computerized app as exempt from later rules. Both pages' extracted text reviewed;
the web PDF renderer was unavailable. No visual/form-layout acceptance is claimed.

[COA's2021-007 issuance listing](https://www.coa.gov.ph/wpfd_file/coa-circular-no-2021-007-september-6-2021/)
identifies6 September2021 as a deferment of implementation of2020-004's GAM for
LGUs, with publication10 September2021. The indexed listing was accessible; direct
retrieval returned403. Full deferment text, later issuances and local applicability
remain unverified. Do not choose the2020 GAM, NGA or barangay appendices merely
because they are readily downloadable. Retain supplied signed documents while
confirming the municipal form/version and approval authorities.

## Implemented request and issue workflow

The small GSO operational case retains a supplied approved requisition, with private
source evidence, native requesting-department identity, reference/date/purpose,
bounded item lines and explicitly requested quantities. A document review records
what GSO checked; it never fabricates the original requesting office's approval or
signature. Keep the requesting office, physical recipient and issuing GSO distinct.

Each fulfillment links explicit quantities to request lines and existing
`StockMovement` rows. It uses the current quantity/FIFO service under item locks, with
case/line version checks and retained outcomes for unavailable and partial items.
Never deduct requested quantities merely because a requisition was entered. A
reviewed remaining quantity is not reserved stock unless a reservation workflow is
separately designed. Cancelled remainders do not undo completed physical issues.
The return workflow retains explicit original-issue lineage and reviewed quantities;
it does not infer reversal of Accounting expense or reopen requested quantities.

Keep all physical records in GRAND default. Native users/departments and public
inventory UUIDs remain authorities. Do not duplicate GRAND Records, procurement,
Finance parties/accounts, or approval designation infrastructure. Accounting owns
financial treatment and any RSMI recognition. GSO issue/FIFO values alone do not
authorize a journal entry. Recheck actual GRAND source before defining optional
Finance relationships; no new cross-store FK or automatic posting is planned.

## Data, permissions and recovery

Migration0022 adds four default-store tables: `SupplyRequisition`, immutable
`SupplyRequisitionLine`, immutable `SupplyFulfillment` and retained
`SupplyRequisitionEvent`. Header, line and fulfillment UUIDs survive transfer;
the existing stock movement has a protected one-to-one link to its fulfillment.
Unavailable observations have zero quantity and no movement. Stock units and names
are captured with each line; changed units/names block issues. Completed requests
close automatically when all requested quantities have been issued. Otherwise an
explicit reasoned closure retains the unissued remainder and all physical issues.

New explicit grants are `view_supply_requisition`, `record_supply_requisition`
and `review_supply_requisition`, alongside stock view and existing issue authority.
GRAND UAT users cannot mutate; an ungranted superuser cannot bypass this. Read and
download scope is the GSO owning office. No roles are granted by the migration.
The creator cannot perform the independent document review. Review does not
fabricate an originating office signature or validate the legal authority of one.

Creation accepts 1–50 distinct item lines, exact positive three-decimal quantities,
a non-future source date and a bounded private PDF/image. Its signed actor-bound
request UUID permits exact retries. The supplied header, evidence and lines are
retained unchanged; close and record anew for a correction. Subsequent actions
require the current case version. Locks follow sorted item IDs, then the case;
issue, FIFO allocation, fulfillment and history commit atomically. Replayed stale
actions fail with a reload message and never issue twice. This does not deduplicate
independently entered documents with fresh identities or reserve future stock.

Evidence lives under `inventory/requisitions/<request UUID>/`. Include it in the
coordinated default/finance/private-file backup. `check_requisition_evidence`
reports missing, altered, unsafe and unreferenced files without changing them.
History checks reproduce the retained case and issue links before transitions.
Checksums detect drift; they do not defeat a privileged database administrator who
rewrites both data and checksums. Storage is not transactional: orphan uploads
after a database failure remain for investigation, never silently deleted.
Missing/changed evidence blocks review and issue; a reasoned closure remains
possible if history itself is intact. Official outputs, digital requesting-office
approval and Accounting expense recognition remain separate work. Supply return
acceptance now has its own [evidenced workflow](supply-returns.md).

## Published retry prerequisite

Reproduced against the published service: replaying an identical receipt, issue or
adjustment HTTP POST changed stock twice. An issue of3 against10 left4 rather than7.
The fix reuses `StockMovement.public_id` as an explicit optional service request
identity, without a migration or new request registry. Existing internal callers
without a request ID retain their transaction semantics.

The three stock forms carry an actor/item/operation-bound30-minute signed identity.
Exact retries recheck authority and return the same retained movement, even if its
item has subsequently become inactive. Changed content under that identity is
rejected. Item locks serialize retries before balance and FIFO writes. A failure
rolls back movement/lot/allocation together so the same identity can be retried.
A fresh form represents a new operation; textual RIS/DR references are not treated
as globally unique identities. This is retry protection, not duplicate-document
detection, requisition approval or official-form generation.

See [stock counts](stock-counts.md), [source matrix](coa-requirements.md),
[handoff](../CONTINUE.md) and [validation](validation-2026-10-16.md).
