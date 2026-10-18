# Supplies ledger and physical counts

Ledger prerequisite published at cbece6c. See [CONTINUE](../CONTINUE.md)
for release evidence. Reviewed current-day counts are published at3ec09d6;
CONTINUE records release and CI evidence.

## Existing ledger controls

The [request/issue trail design](stock-request-design.md) describes remaining
requisition lineage and the immediate signed retry prerequisite. Stock POST retries
reuse an explicit movement UUID rather than deducting/receiving stock again; they
do not establish a requisition approval or official RIS/RSMI output.

Supply catalog, movements and optional FIFO lots remain in GRAND `default`.
Quantities have three decimal places; optional unit costs have two. Service writes
now validate field precision/range before balance comparisons, ledger insertion or
FIFO allocation. They reject non-finite numbers and negative costs instead of relying
on database rounding. Adjustments require a nonblank reason. Issues require a valid
department and recipient, and retain the department label resolved from the actual
directory rather than a caller-supplied label. Catalog minimums are validated and
partial catalog edits preserve an omitted FIFO setting. Existing history is unchanged.

GRAND stock actions use its explicit user/group grant helper and assigned-department
gate. Finance UAT viewers cannot create/change catalogs or receive/issue/adjust stock.
Their scoped read/export grants remain usable. Implicit superuser privilege is not a
GRAND stock action grant; the standalone shell retains its existing access adapter.
Item-owner checks still run after locking the current item row. These changes do
not write Finance, infer accounting valuation, grant permissions or migrate data.

## Reviewed count workflow

Migration 0019 adds one-item StockCount records, immutable decision events and private
evidence without changing existing ledger rows. A shared count-sheet reference can
group observations for staff search; there is no duplicate stock ledger or general
workflow engine. Protected native user links retain the recorder and deciding officer.
The source pins item UUID/name/unit/owner/FIFO/active state plus movement count,
latest movement UUID and quantity balance. Movement ordering uses occurrence time
and UUID, not a new installation's integer key. Signed previews bind actor, item,
basis and request UUID for 30 minutes; exact retries reuse the original record.

Only the owning GSO can read count records/evidence. Recorders need stock view and
`record_stock_count`; independent approvers need stock view, `review_stock_count`
and `adjust_stock`. GRAND requires explicit grants and denies UAT writes. Neither
the recorder nor any evidence uploader can approve. A recorder or authorized reviewer
can cancel an incorrect count without changing stock. Reviewer-only cancellation
does not require upload authority. No role is granted automatically.

Item-first locks serialize counts and stock movements. Pending versions reject
stale decisions, and the database permits only one pending count per item. Approval
checks the current item/ledger against the source. Any movement, even offsetting
receipts/issues, invalidates the basis: cancel and recount rather than overwriting
the live balance. An approved difference creates one protected-linked append-only
adjustment through the existing stock service. Zero variance retains the review
without a fake movement. Failure writing the audit event rolls back the adjustment,
FIFO allocation and decision together. Closed records are not edited or deleted.

Keep ordinary supplies quantity-only. Where FIFO was explicitly enabled, use the
existing allocation service; a count surplus must not invent a financial unit cost.
Do not conflate consumables with semi-expendable equipment requiring named custody.
The register flags active items at/below a positive configured minimum; a zero
minimum leaves the reminder unset. No notification service is introduced. Direct adjustment
history remains distinguishable from reviewed count adjustments.

Count evidence follows established private PDF/image validation, bounded to 20 files,
15 MB each and 100 MB total. Review and scoped downloads verify case paths, hashes
and sizes; downloads use attachment/no-store/nosniff. Include `inventory/stock_counts/`
with both GRAND stores in recovery, then run `check_stock_count_evidence`. The checker
reports missing/changed/unsafe/orphan files without repairs or deletion. Filesystem
writes do not roll back with database transactions; investigate any orphan finding.

## Movement-history preparation

The bounded retrieval slice joins existing retained movement rows across
supply items, with optional recorded-date and movement-type filters. Reuse the
current stock read/export grants and item ownership; department readers see only
their own movements of otherwise visible items. CSV selection must match the
screen selection across all pages, while export continues to require its separate
existing GSO grant. Invalid filters must not silently produce an unfiltered export.
Selections read current history, not an immutable group snapshot; newly recorded
movements may appear on refresh/export. The history page's brand and Supplies links
return to the authorized stock list rather than require unrelated asset access.

Dates describe GRAND's recording timestamp in its configured local timezone, not
a supplied requisition, delivery or historical physical-event date. Keep quantities
per item and unit, original references and public source identities; do not sum
unlike units or turn optional recorded costs into an Accounting valuation. Returns
and adjustments remain distinct rows rather than silently netting original issues.
This working history does not generate an official RSMI, financial recognition,
signatures, numbering, custody changes or any new stock movement. Current
implementation and actual validation belong to the root handoff.

## Limits and remaining work

The adjusting workflow accepts today's count against the current ledger basis.
Historical count sheets need a separate reconciliation path because entry timestamps
alone cannot prove the physical balance on a past count date. It does not retrospectively
adjust a date's stock or replace a signed annual report. Observations up to nine whole
digits and three decimal places follow the existing per-movement quantity limit.
Approved-count corrections require a new observed count; no destructive reversal
shortcut is supplied. Quantity/cost allocation and Accounting valuation remain separate.

These are selected engineering controls, not asserted COA form requirements.
Applicable supplies-count forms and signatories still need primary-text and local
validation before official output. HR-reference clearance cases and Finance
cost/allocation/JEV relationships remain separate work in the [roadmap](inventory-roadmap.md).
