# Receiving and inspection

This is a working operational record, not a generated official COA form or a Finance
approval. No procurement, obligation, payment, recognition or depreciation is posted.

## Workflow and permissions

All receiving users need `inventory.view_receivingreceipt` and the owning GSO office.
Receiving-only staff land on this register without receiving asset-view permission.
An authorized administrator assigns permissions through existing Groups; releases
do not grant roles or migrate operator data.

1. With `add_receivingreceipt`, record supplier, delivery/inspection dates and
   references, inspector label and document reference. With `change_receivingreceipt`,
   add supply lines or one line per tagged asset. Record delivered, proposed accepted
   and rejected quantities with reasons. Supply units must match an active owned
   item. Unknown cost stays unknown; zero is explicit. No account code is inferred.
2. Retain delivery and inspection documents (PDF/JPG/PNG/WebP; 15 MB each, 20 files
   and 100 MB total per receipt). Hash/size checks run again on submission/acceptance.
   Downloads require scoped access. Hashes do not prove documentary authenticity.
   Draft/returned lines can be voided with a reason and re-entered; history remains.
3. With `submit_receivingreceipt`, submit for review. No inventory changes yet. An
   officer with `review_receivingreceipt` may return for correction or accept with a
   review basis. Anyone who created, edited, uploaded, voided or submitted the record
   cannot review it, including administrators. Acceptance additionally needs
   `add_asset` and/or `receive_stock` for the relevant accepted lines.
4. Acceptance atomically creates linked assets/stock movements, checking current
   permissions, office, quantities, files and duplicate identifiers. Stale/concurrent
   acceptance cannot duplicate inventory. Use the existing custody/handoff workflow
   after intake; no acquisition date, account or custodian is invented.

Unaccepted quantities never enter stock. Accepted receipts are read-only. Later
deliveries need their own records and source evidence. [Follow-up inspections](receiving-followups.md)
resolve documented portions of an original unresolved remainder through separate
linked receipts and independent review. Original accepted/rejected quantities stay
fixed. See CONTINUE for validation and publication state.
Accepted quantity correction/reversal is not implemented.
[Reviewed documentary cost amendments](receipt-cost-corrections.md) preserve the
original accepted facts and separately record a corrected source cost.
Investigate mistaken acceptance before using existing adjustment routes; never
rewrite retained source links/history. Separate drafts with the same source-reference
text are not automatically deduplicated; reviewers must check the source packet.

## Recovery and migration

The user-selected [clerical overstatement before use](receipt-quantity-corrections.md)
workflow preserves original delivered/accepted columns and records an independently
reviewed subtraction from both. The receipt screen shows effective quantities beside
the original facts; it does not reopen resolved remainder capacity. Original-lot
adjustments and erroneous-asset entries are distinct from physical returns and disposal.
Any previous Finance support history requires separate reconciliation. Publication
and validation state are maintained in CONTINUE.

Run `python manage.py check_receiving_evidence` during stopped-write maintenance or
against an isolated restore. It reports missing/changed/unsafe/unreferenced files
and changes nothing. Preserve unreferenced files after failed uploads for investigation.
Back up DB and private storage together; see [recovery](security-and-recovery.md).

0013/0014 add receiving records/evidence. 0015 replaces conditional transfer/disposal
uniqueness with virtual generated markers and ordinary constraints, following GRAND's
logical pattern. It refuses duplicate open historical cases before DDL. Apply with
a verified backup during maintenance; never auto-deduplicate. [Native tests](native-testing.md)
cover populated upgrades and races. GRAND integration remains separate; operational
tables belong in `default`, with no cross-store Finance FK or automatic posting.

## GRAND receiving authority

GRAND receiving uses its explicit user/group grant helper for each action, even
for superusers. GSO-assigned Finance UAT viewers with an explicit view grant can
read their scoped receipts and private documents, but cannot create, change,
submit or review them. Services and POST entry points enforce this independently
of hidden controls. Independent review and asset/stock acceptance permissions
remain required. Receiving responses prohibit caching. No existing role grants
are changed by this code; standalone Django permissions remain supported.
