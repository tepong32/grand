# Clerical receipt overstatement before use

Implementation checkpoint: 2026-10-17, baseline ad8b348. The user selected **clerical
overstatement before use** as the first accepted-receipt correction case. The
feature branch now implements the workflow below; [CONTINUE](../CONTINUE.md) owns
validation and publication status. No operator migration, role grant or deployment
is implied by the code checkpoint.

Inventory0029 adds protected correction/result/event records and the distinct
asset `entry_void` state. Adapter0007 has only a dependency on this schema.
`receipt_correction_sources.py` checks locked source eligibility;
`receipt_quantity_corrections.py` owns record/review/cancel, result integrity,
effective quantities and pending-operation guards. Signed forms and private
downloads reuse the receiving scope. Exact replay returns the retained request;
approval cannot create a second result. Only verified prior corrections to the
same source are excluded from adjustment/use checks.

## Meaning and boundaries

The first operation corrects a quantity entered too high in both delivered and
accepted columns. For example, an original entry of delivered10, accepted6,
rejected2 can have a documented overstatement of2: effective delivered8,
accepted4, rejected2 and unresolved2. Preserve the original columns and acceptance
event; show original, approved correction and effective figures together.

This is not a change of inspection decision, a physical return, loss, disposal or
Accounting reversal. If10 were actually delivered but only4 should have been
accepted, that case needs its own documented disposition of the other quantities.
Do not silently classify them as rejected or pending. The reviewer must explicitly
confirm the clerical case from the retained correction packet.

Use the original accepted line as the protected source. Initially refuse a
follow-up source or a line already referenced by any follow-up, including a draft:
those records already rely on its physical facts. A later follow-up after an
approved correction can use the corrected source basis; subtracting the same
quantity from delivery and acceptance does not increase unresolved capacity.
Existing child history must never be rewritten.

## Source tracing and selected write behavior

| Existing source | Required behavior |
| --- | --- |
| `receiving.accept_receipt` creates one asset or stock movement per accepted line | Keep that link and original materialization. Check original acceptance evidence and current linked facts before proposing and approving. Missing or divergent history requires reconciliation. |
| `services.record_stock_movement` sends every FIFO outbound movement to `_allocate_fifo`, which consumes oldest lots | A correction must select the original receipt lot explicitly. Do not use the generic oldest-lot adjustment with a descriptive reference and assume it corrected the right delivery. Retain a protected correction-to-adjustment link and an allocation against that exact lot. |
| `StockLotAllocation` and supply-return lineage retain original issues | Any use of the target lot excludes the first case, even if goods were returned. Returned quantity does not erase use. Prior approved corrections to the same source are the only correction-owned allocations that may be excluded from this check. |
| Non-FIFO movements have no receipt allocation | Any intervening outbound history makes receipt usage ambiguous. Refuse the shortcut; do not infer unused stock from the current balance or a later return. Check counts, adjustments and unlinked returns for possible prior reconciliation. |
| Assets have active/maintenance/transferred/retired states, but no erroneous-entry state | Add a distinct retained erroneous-entry state for a wholly mistaken one-unit entry. Never call it disposal or delete/reuse its tag/history. Exclude it from new operational actions and physical count selection; keep it visible as corrected history. |
| Asset transfers, returns, maintenance/disposal cases, verification records/findings and property packets record downstream facts | Refuse the first shortcut when downstream evidence exists, even if a case is now closed. Check current assignment and source materialization too. Do not clear custody, remove documents or cascade corrections into these workflows. |
| `ReceiptCostAmendment` records documentary cost separately | Preserve original stock/asset costs. Approved quantity corrections affect the documentary support quantity, not Accounting valuation. Pending competing amendments need resolution or an explicitly stale-basis failure. |
| Optional `ReceiptClaimAttribution` and property links live in default | Any Finance support history excludes this initial before-Finance case, including withdrawn history. Withdrawal is not proof of journal reversal. Do not query or write Accounting to manufacture eligibility. |

For supplies, a positive exact correction quantity cannot exceed effective accepted
quantity or available quantity in the original lot. Retain unknown cost as unknown.
For an individually tracked asset, the correction quantity is exactly1; preserve
the asset row and source evidence. A positive original receipt may consequently
have effective delivered/accepted zero without violating or rewriting the original
positive-delivery database constraint.

## Minimal retained workflow

Reuse the established record / independent review / reject pattern, adding recorder
cancellation so a bad pending record can release its hold. Each proposal needs a
public UUID, protected original line and approved predecessor, exact quantity,
source basis, reference/reason, private bounded PDF/image packet, retained filename,
SHA256 and size, actor/reviewer identities, decision note, version and events.
Use a generated nullable pending-line marker for one pending proposal per source,
as in existing GRAND-compatible workflows. Add default-store tables only.

Approve atomically with the source-linked stock adjustment or asset state change.
Keep a protected result link; never infer it later from free-text references.
Exact request replay must return the original result without another adjustment.
Review must be independent of preparation/upload, authorized for the actual owning
GSO and checked again on locked rows. Neither a public UUID nor a superuser fallback
provides cross-office mutation authority. Reject/cancel must remain available when
source files become unavailable; these actions do not approve the correction.

## Locks and pending holds

Use receipt -> item/asset -> correction order, refreshing links and authority after
locking. Existing stock services lock the item; they must check a pending correction
under that lock without acquiring a receipt lock afterward. Block stock mutation
for the affected item while the proposal is pending. Likewise guard asset mutation
and new downstream property records. Permit only the correction service's own
validated atomic result; do not expose an HTTP/API bypass flag.

Claim support already locks case -> receipt -> attribution. Inspect support history
under the receipt lock without locking a Finance case from the correction path.
New attribution proposal/approval must reject a pending correction and use effective
accepted quantity after approval. These changes must serialize on the same receipt
lock; a read-only preview is never authority to commit later.

Snapshot consumers need a conditional correction extension containing approved
identity/checksum and effective quantities. Preserve the existing serialized shape
for uncorrected rows. Recheck evidence and current basis at decisions. A later
follow-up must retain that extension and cannot allow a further original correction
while its dependent history exists. Keep old Finance snapshots as history, not a
silently recomputed representation.

## GRAND integration and evidence gates

No Finance schema, cross-database FK, posting, payment or authority change is needed.
The optional adapter migration should depend on the inventory correction migration;
it must not install Finance in the standalone shell. Import/recovery must preserve
source and result links, UUID/predecessor mappings, original and correction packets,
events and retained snapshots. Installation-local identities still require explicit
reviewed mappings into GRAND.

Before releasing the complete workflow, demonstrate:

- Partial supply correction with an older unrelated FIFO lot: only the source lot
  changes, original receipt stays intact, and independent review/retry are enforced.
- Non-FIFO prior use, returned issues, prior reconciliation, follow-up dependencies,
  asset custody/history and any Finance support prevent the before-use shortcut.
- Pending correction versus issue, count adjustment, asset action, follow-up and
  Finance support races on native MySQL; no deadlock, double write or stale approval.
- Scoped service/HTTP access, signed requests, bounded private uploads, tampered or
  missing evidence, stale source and independent actor checks in actual GRAND.
- Effective quantity/cost consumers, unchanged snapshots for untouched sources,
  populated migration preservation and no Finance writes.
- Desktop/mobile recording and review, exact retry, rejected/cancelled hold release,
  and paired restored-copy recovery of original/correction/result history.

This is a user-selected operational control, not a claim that COA mandates this
exact correction form. The [COA matrix](coa-requirements.md) retains verified-source
limits; official form, effectivity/amendment and local signatory acceptance remain
separate. [CONTINUE](../CONTINUE.md) owns implementation/publication state.
