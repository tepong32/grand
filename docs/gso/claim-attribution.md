# Reviewed receipt claim support

`inventory_finance` is an optional GRAND integration app. It links accepted GSO
receipt lines to documented amounts in existing voucher claim lines. It reuses
GRAND users, departments, case visibility and the pinned Finance owner. It creates
no supplier directory, payment authority, Budget reservation or accounting entries.
The standalone shell does not install this app or simulate GRAND records.

## Workflow and controls

An explicitly authorized GSO officer selects an accessible prepared claim, an accepted
receipt line from their own office, an amount and its documentary basis. Preview shows
the actual receipt/claim content. Confirmation is signed, bound to the actor and case,
expires after 30 minutes and rechecks source freshness and permissions on submission.
Retrying the same request retains one proposal and event.
New proposals also retain the receipt basis: delivery/inspection facts, accepted
quantity, documented unit cost, materialized UUIDs and evidence metadata. Preview
confirmation and approval reject changes on either side of the relationship.
The review screen displays recorded receipt facts rather than today's live values.
See [receipt correction prerequisites](receipt-cost-corrections.md).

A different officer in the case's Finance-owning department reviews the proposal.
Approval checks the source snapshot, receipt status and both amount limits under
case/receipt locks: approved support cannot exceed the claim line, nor can support
across different claims exceed accepted receipt quantity times documented unit cost.
Unknown or zero unit cost is not treated as available capacity. This is a documentary
support ceiling, not an Accounting acquisition-cost calculation. Payment withholding,
freight, tax and valuation are not silently inferred or allocated.

Rejection and withdrawal require a reason. Withdrawal retains the original approval
and its actor/date/note, adds a new event and releases supported capacity. A replaced
DV line remains in historical source evidence; no FK blocks GRAND re-preparation and
no matching description/amount silently retargets it. Changed source evidence blocks
approval. Existing stale approved links must be reviewed and withdrawn before new
support is approved for that case. Historical status remains visible with a warning;
it is not silently rewritten. UAT viewers cannot mutate, including when granted a
review permission. Superuser status does not replace explicit grants or independence.

## Controlled GRAND installation

These are integration instructions, not a record of operator installation. Recheck
GRAND's current migration graph and router before merging. Validation used clean
published GRAND `32ab046`; the parallel Form1 working tree was not modified.

1. Include the `inventory` and `inventory_finance` Python packages. Retain inventory
   migrations and dependencies; do not copy GSO's standalone `src`, `user` or `home`
   apps over GRAND. Keep GRAND's authentication and settings.
2. Add `inventory.apps.InventoryConfig` and
   `inventory_finance.apps.InventoryFinanceConfig` to GRAND's installed apps. Configure
   `DISPOSAL_PRIVATE_ROOT` outside public media/static roots, using protected storage.
3. Include `inventory_finance.urls` under the chosen GSO path, for example
   `path("gso/claim-support/", include("inventory_finance.urls"))`. The route namespace
   is `inventory_finance`. Add a scoped workspace link; server checks remain mandatory.
4. Review the migration plan before applying it during the approved maintenance
   window. Initial attribution migration depends on inventory0015, departments0005,
   vouchers0038 and the actual swappable user model. All attribution rows remain in
   `default`; do not create cross-store FKs or alter the Finance router.
   Migration0002 adds nullable receipt review snapshots. Historical NULL values are
   deliberately not backfilled from current facts. Such links remain readable and
   withdrawable; they cannot be approved or treated as a verified basis for new
   support on the same receipt until reviewed/withdrawn and reproposed.
5. Assign the following explicit grants only to reviewed roles. This package assigns
   none automatically. Preserve existing Finance workbench/case access independently.

| Grant | Scope |
| --- | --- |
| `inventory_finance.view_receiptclaimattribution` | Read links within the actor's receipt/Finance office and existing case visibility. |
| `inventory_finance.propose_receiptclaimattribution` | Propose from accepted receipts owned by the acting GSO office. |
| `inventory_finance.review_receiptclaimattribution` | Independently approve/reject or withdraw under the case's Finance owner. |

Code integration is separate from historical data import. Import mappings must use
receipt UUID/line sequence, case UUID and reviewed source evidence, not coincident
integer PKs. Do not restore the standalone SQLite DB over GRAND or copy role grants.

## Validation and remaining limits

The isolated harness uses actual GRAND models, permissions, routing and migrations.
MySQL tests cover simultaneous approvals, cross-case receipt capacity, duplicate
request/approval races, and source replacement. Enforced-CSRF HTTP tests cover the
signed preview, expiry, tampering and actor/source mismatch. Browser checks completed
clerk preview/submission, independent approval and withdrawal at desktop/mobile sizes.
See [native testing](native-testing.md) and [exact results](validation-2026-10-16.md).

The synthetic offline paired-SQLite restore preserved both stores and attribution
history; it does not establish online MySQL recovery or private evidence completeness.
Use GRAND's coordinated recovery procedure and separately protect evidence files.
Existing GRAND conditional-uniqueness warnings remain an integration gate, not resolved
by these passing tests. See [security and recovery](security-and-recovery.md).

Reviewed documentary cost amendments now preserve the original accepted cost and
provide a separately reviewed effective documentary ceiling. See [cost corrections](receipt-cost-corrections.md).
Adapter migration0003 declares inventory0020 as a dependency without operations.
Unknown effective cost still provides no positive claim-support capacity. The separate
[reviewed recognition amount mapping](receipt-journal-mappings.md) now links selected
posted debit portions. Physical quantity/cost allocation, valuation, official forms
and historical imports remain unfinished.
That mapping must be withdrawn before its approved claim support can be withdrawn.
[Journal inspection](journal-source-preview.md) itself is read-only. No automatic cost
or classification may be invented. This feature is not legal,
Accounting, operator or production acceptance of the whole system.
