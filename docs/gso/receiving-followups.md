# Follow-up inspection of delivered remainders

Development branch `codex/receipt-followup-acceptance`, baseline78c19e8.
The local workflow/release checks are complete. Check CONTINUE and Git/hosted
receipts for publication; no operator installation is implied.

## Selected structure

A follow-up is an ordinary receiving header with a protected source-line relation
and retained original physical basis. It has exactly one line. It reuses private
receiving evidence, draft/returned/submitted/accepted states, independent review,
action grants and materialization. Migration0028 adds two fields in default; no
Finance schema, cross-store FK, new registry or new storage namespace is needed.
Adapter0006 explicitly depends on inventory0028 because its snapshots read the new
relation; it has no data/schema operations and rewrites no historical approval.

Only an accepted, nonvoid original line can be followed up. The original delivery
date/reference, supplier, item/unit and known asset identifiers stay fixed. A new
inspection date/reference, explicit accepted/rejected quantities, reason and supplied
cost describe this later inspection. Unknown cost remains unknown. A later delivery
is a separate receipt, not a follow-up. Previously rejected quantities cannot be
accepted through this workflow; rejected-goods reconsideration is not implied.

The follow-up covered quantity equals accepted plus rejected and must be positive.
Original unresolved quantity is original delivered minus original accepted/rejected
minus accepted follow-ups' accepted/rejected quantities. Drafts do not reserve stock
or capacity. Each final acceptance rechecks capacity while holding the original
receipt lock, then its follow-up lock. Recursive follow-ups are prohibited.
Concurrent inspection drafts can coexist; only the still-available quantity can be
accepted. Staff can correct a returned draft's one line, not add unrelated items or
void its lineage. Existing receiving return/review history remains authoritative.

Creating a draft uses a signed actor/source/request/basis token with a30-minute
lifetime. Exact retries reuse the receipt UUID and original created-event payload;
reusing that identity with different facts fails. The original packet must still
match and its retained evidence must pass integrity checks at follow-up review.
Follow-up delivery and inspection documents are retained separately and reviewed
through existing receiving controls. Their hashes establish integrity, not authenticity.

## Downstream facts and GRAND alignment

Original accepted quantities, materialization links, state version and historical
Finance snapshots are not rewritten by a follow-up. Original documentary cost
amendments remain separate from its physical basis; they do not automatically price
a later inspection. A follow-up has its own explicit supplied cost and, after
acceptance, its own single asset or stock-movement link. It uses existing independent
Finance claim attribution with its own accepted quantity/cost ceiling. It never
posts to Finance or approves a claim automatically.

Only new follow-up Finance/property snapshots include retained original lineage;
ordinary receipt snapshot shapes stay unchanged. Source checks detect altered or
missing original evidence. The root relation and original basis must be included
in import mapping and paired recovery; numeric line IDs remain installation-local.
Portable source identity is original receipt UUID plus line sequence.

An item accepted on a follow-up did not become available on the original delivery
date. Its working property movement uses the supplied follow-up inspection date;
the original delivery date remains visible and retained. Ordinary receipt movement
dates remain unchanged. This is operational working reconstruction, not an official
SPC, Accounting recognition date or assertion of when staff knew a fact.

## Release gates

Required before publication: service/HTTP workflow and adversarial cases, actual
GRAND explicit-grant/UAT/scope and Finance-support tests, native competing acceptance,
populated migration preservation, browser desktop/mobile entry/correction/review,
paired database/evidence restore, full appropriate regressions and hosted checks.
The current handoff records actual results; this list does not claim they passed.
No operator migration, grant, deployment or accepted-quantity reversal is included.
