# Reviewed receipt recognition mappings

The optional GRAND adapter records an independently reviewed amount relationship
between approved receipt claim support and a selected posted recognition debit.
It does not assign physical quantities, calculate acquisition cost, capitalize
repairs, alter FIFO, create journals or consume Budget obligation capacity.

## Authority and workflow

The Finance-owning office prepares and independently reviews these relationships.
Both actors need existing case/claim visibility, the explicit ledger-read grant
and the relevant `inventory_finance.propose_receiptjournalmapping` or
`inventory_finance.review_receiptjournalmapping` permission. A view grant permits
scoped history only. Superuser status grants no shortcut; UAT cannot mutate.
The proposer cannot approve or reject their own proposal. No operator grants are
installed by a code release.

From receipt support, inspect the recognition requests, then select the request,
debit line sequence, amount and documentary explanation. The signed preview binds
the actor, claim, selected source, exact evidence and request UUID for thirty
minutes. Confirmation rechecks the evidence. Identical retries retain one proposal;
a reused request UUID with different content is rejected. A second authorized
officer records approval or rejection with a reason. Withdrawal retains the
original approval and adds its own event; never edit or delete the original mapping.

Only posted recognition requests with intact bound journal/source checksums,
posting attribution/totals and owner dimensions are accepted. An asset or expense
debit is selected explicitly; account codes or equal amounts do not imply a match.
Original private delivery/inspection files must still exist and reproduce their
retained hashes and sizes; approved status alone cannot replace those documents.
An active draft, submitted or posted reversal prevents approval. Debit type is
eligibility for documentary review, not a valuation policy or proof of cost.

## Data and transaction boundaries

Adapter migration0004 adds `ReceiptJournalMapping` and its append-only event table
in `default`, with protected claim/request/actor relationships. Journal UUID and
line sequence are retained scalar identities, not cross-store foreign keys. The
proposal retains minimal journal dimensions, request checksums, approved claim
decision and receipt basis. Proposal and event checksums detect inconsistent
retained content; they are not digital signatures or a replacement for protected
database access and backups. Historical rows are not backfilled.

All mappings for a source case serialize on its default-store case lock, followed
by receipt, claim, mapping (review only), posting request and finance journal.
Approvals sum existing approved mappings against both the selected debit and the
approved claim amount. Stale earlier approved mappings in the case must be
withdrawn before new approval. An approved mapping also prevents withdrawal of its
underlying claim support until the mapping is explicitly withdrawn first.

The Finance transaction is an outer **read/lock-only** transaction. The inner
default-store transaction is durable: it commits the mapping while still holding
the original journal lock used by GRAND's `create_reversal`. A caller cannot nest
these mutation services inside a broader default-store transaction that defers the
commit past that lock. Current GRAND does not configure `ATOMIC_REQUESTS`; recheck
that setting on integration. Do not introduce a surrounding default transaction.
Only one database is written. This is not a distributed commit protocol or a
guarantee that Finance can never change after review. A later reversal or changed
claim/receipt makes the retained mapping stale and requires documentary correction.

The detail screen revalidates current evidence and marks stale history; the list
labels statuses as retained decisions rather than current reconciliation. Retained corrupt
proposal/event evidence must be recovered/investigated rather than silently accepted
or overwritten. Review status alone is insufficient proof of current reconciliation.

## Integration, recovery and remaining work

Reuse GRAND's source/access/model implementations at baseline `32ab046`, especially
`accounting/posted_evidence.py`, `accounting/services.py:create_reversal`, and its
retained attribution patterns. No parallel Finance application file is edited.
Before merging into GRAND, recheck its current router, migrations and source-lock
conventions, and apply migration0004 only in the reviewed maintenance window.

Recover the paired stores under GRAND's existing coordinated procedure, including
all existing private receipt/amendment files. This mapping adds no private upload
location. Check proposal/event verification and current source evidence separately;
do not reconstruct lost approvals from current journal values. See
[security/recovery](security-and-recovery.md) and [validation](validation-2026-10-16.md).

This supplies a reviewed amount relationship. Physical quantity splits, freight/tax
cost allocation, Accounting-approved valuation/import, historical reconciliation,
official forms and LGU acceptance remain separate incomplete work. See
[data design](grand-integration-design.md), [claim support](claim-attribution.md),
[journal inspection](journal-source-preview.md) and [roadmap](inventory-roadmap.md).
