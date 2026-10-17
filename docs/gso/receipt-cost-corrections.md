# Receipt cost correction and retained claim evidence

Source review: 2026-10-17, GSO baseline217a4d3 and fetched GRAND32ab046.
The active GRAND Form1 work is unpublished and has its own running full tests;
no application/test source there is changed by this work.

## Current implementation boundary

Accepted receiving records cannot be edited through the receiving service.
Acceptance copies documented unit cost into an asset acquisition-cost field or a
stock receipt and optional FIFO lot. Those materialized facts are not a safe target
for a later invoice correction: stock may have been issued and asset custody may
already have changed. A separate reviewed documentary amendment now records corrected source cost;
no financial revaluation workflow is claimed.

The ordinary asset editor now protects receipt-origin unit cost, quantity,
supplier and purchase-order reference in both the form and the locked service.
Previously an authorized register editor could overwrite those materialized facts
without the receipt amendment process. Identical values and descriptive/tagging
updates remain allowed. Unknown cost cannot be changed to zero through this path.
No historical rows are rewritten: any existing divergence needs explicit review.
Unlinked legacy entries keep their existing audit-backed editing workflow.
The guard reads the receipt link after locking the asset without taking a receipt
lock, preserving the established receipt-to-asset order used during acceptance.

Claim support previously retained the Finance claim source but used the receipt's
live quantity and cost. Its signed preview also omitted receipt facts, and the
review page displayed the current delivery description as historical evidence.
This is a missing prerequisite for an amendment workflow. Current authorized UI
does not edit accepted receipts; tests model future amendment locks or deliberate
out-of-band changes, not an existing public-UI exploit.

Published receipt-basis change543fef8 adds a nullable JSON receipt snapshot to
the optional default-store attribution table. New signed previews, proposals and
events pin receipt UUID/version/owner, delivery and inspection facts, line sequence,
description/unit/quantities/unit cost, original materialized UUIDs, acceptance actor
and time, and retained evidence metadata. Local user/department IDs remain labeled
as local identities. There is no cross-store FK or new Finance authority.

Confirmation compares the signed receipt basis with current facts under the receipt
lock. Approval compares retained receipt facts as well as the claim source. Read the
line again after acquiring the lock; a pre-lock ORM instance may be stale. Approved
links with a missing or changed receipt basis must be explicitly reviewed/withdrawn
before new support on that receipt can be approved, including across different claims.
Preserve case → receipt → attribution lock order. Do not add reverse case locking
inside a receipt amendment service.

The detail screen shows the retained receipt facts. Unknown legacy snapshots stay
NULL on migration, with a visible historical-basis warning. Existing amounts,
statuses, actors and events remain unchanged. A legacy proposal cannot be approved;
reject or withdraw it and make a newly reviewed proposal. Old approved support is
not silently erased or retargeted, and withdrawal retains its original approval.
Evidence metadata snapshots do not establish file authenticity or replace the
receiving private-file integrity checker and coordinated backup.

## Implemented documentary amendment workflow

1. Retain an explicit amendment to a selected accepted receipt line, with its own
   UUID, original/effective documented unit cost, reason, source document, actor,
   review decision and predecessor identity. Do not edit the original receiving
   event, asset, stock movement or FIFO allocation to make totals appear consistent.
2. Have the owning GSO record the documentary correction and a different explicitly
   authorized reviewer verify it. This verifies a source-document fact; Accounting
   still owns acquisition-cost treatment, recognition and journal corrections.
   Recheck the actual GRAND role/owner boundary before assigning any reviewer grant.
3. Make the accepted amendment identity part of the effective receipt-support basis.
   Unknown cost remains NULL; zero is a documented zero, not unknown. Quantity and
   money limits remain explicit, with no invented taxes, freight, discounts or cost
   allocation. Preserve original and effective values visibly side by side.
4. Serialize amendments with support approval on the existing receipt lock. Existing
   approved links remain historical and become visibly stale; they must be reviewed
   and withdrawn/reproposed rather than silently recalculated. A lower corrected
   value does not retrospectively change an approval or authorize a journal reversal.
5. Validate retained predecessor facts, duplicate submission, concurrent amendment
   and approval, evidence loss/corruption, populated upgrades and paired recovery.
   Record/upload/review/history screens and private downloads accompany the service.

These are engineering decisions, not asserted COA valuation rules. Before financial
allocation or official output, verify applicable primary texts and the LGU's actual
Accounting workflow. See [GRAND design](grand-integration-design.md),
[claim support](claim-attribution.md), [COA sources](coa-requirements.md) and
[validation](validation-2026-10-16.md).

## Storage and integration details

Inventory migration0020 adds ReceiptCostAmendment and retained decision events in
`default`, with protected native actors/line/predecessor links, public UUID and a
virtual pending-line marker with an ordinary unique constraint. It creates no
historical amendments and changes no existing rows. Optional adapter migration0003
has no operations: it declares the inventory0020 prerequisite for adapter-only
migration targets. Existing migration history is unchanged.

The first version retains one required private correcting document per proposal
(max15 MB, existing PDF/image validation). Submitted content has no edit route;
reject and submit a replacement to correct it. One pending amendment per line,
request identity replay checks, receipt locking, content checksum and source-file
checks protect normal service writes. Checksum evidence detects changes; it does
not authenticate documents or defeat privileged database/file administrators.
Pending and rejected amendments do not change the effective cost. Unknown remains
NULL and zero remains zero; neither establishes positive claim-support capacity.

Recording/review require separate explicit `record_receiptcostamendment` /
`review_receiptcostamendment` grants, existing receiving view permission and the
owning GSO department. No grants are installed automatically. GRAND UAT users
cannot mutate. A proposer cannot review their correction. Approved documentary
costs may differ from stored asset/stock values, visibly and deliberately; Accounting
must resolve financial treatment separately. Receipt version changes conservatively
invalidate older support bases, including other lines on that receipt.

Backup both stores and all private evidence. Run
`python manage.py check_receipt_amendment_evidence` alongside receiving evidence
checks on a stopped-write backup or isolated restore. The checker changes nothing
and reports missing/changed/unsafe/unreferenced files. See CONTINUE and validation
for native, browser, migration and recovery outcomes. Operator installation, local
legal/Accounting acceptance, quantity correction/reversal, taxes/freight allocation
and financial revaluation remain outside this implemented slice.
