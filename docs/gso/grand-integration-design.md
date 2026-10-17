# GSO and GRAND data design

The [clerical quantity correction](receipt-quantity-corrections.md) extension adds
inventory0029 in default and adapter0007's dependency only. Its protected source,
predecessor, stock-result/asset-audit and actor links reuse existing authorities.
The optional support ceiling uses effective accepted quantity and retained
conditional correction evidence; untouched receipt snapshots retain their prior
shape. Any previous support history excludes the initial before-use shortcut.
Pending corrections serialize with support on the existing receipt lock, with no
reverse case lock, cross-store FK, journal or valuation write. Event checksums bind
installation-local references: cross-installation imports still need reviewed
identity mapping and retained source evidence, not an automatic numeric-ID rewrite.
The restored-copy checks prove same-installation recovery, not historical import
acceptance. CONTINUE records actual validation/publication state.

Design checkpoint: 2026-10-16, Asia/Singapore. Recommended approach selected under
the user's instruction to align the projects and avoid speculative architecture.
Receiving is published through `7d3547f` with documentation at `9ae80c0`.
Reviewed claim support is published at28da3f1; see [claim support](claim-attribution.md).
Maintenance is published at3905a74. [Employee custody](employee-custody-design.md)
is published at236c5e1 with protected user relationships and signed handoffs.
Official employee movement/exit clearance remains unimplemented. The
[HR-reference case](hr-custody-review.md) records qualified GSO findings using native
users and private supplied evidence, without changing HR or Finance. It adds only
default-store case/event tables; see CONTINUE for validation/publication status.
GRAND's existing DepartmentRecord remains the authority for general office filing;
GSO is not yet among its supported association types, so no association is invented.
The [witnessed return design](custody-returns.md) extends the same custody movement
and native user relationships in default. It preserves Finance and maintenance
authority; see CONTINUE for validation/publication status.
The [supply-count workflow](stock-counts.md) adds migration0019 in default with
protected native actors, item/count/movement UUIDs and one explicit adjustment
link. A reviewed count establishes physical quantity only. Unknown surplus cost,
historical reconciliation and Accounting valuation remain separate; no journal or
cross-database foreign key is created. Include its private evidence in paired recovery.

## Source of truth inspected

GSO baseline: `64e458a` (physical-count reconciliation release). GRAND published baseline:
`32ab04669da05b868f6c8b8ff37e0f71b3805555` (v172), verified against fetched
`origin/master`. GRAND's active checkout is
`C:/Users/Administrator/.codex/worktrees/finance-form1-treatments/grand`, branch
`codex/finance-form1-print-evidence`; its ongoing Form 1 edits are unpublished.
The canonical GH/grand checkout is older; its CONTINUE points to this worktree.
Read the active handoff on every continuation; these paths are discovery evidence,
not a permanent dependency of the application.

Examined `src/database_routers.py`, `finance/models.py`, `vouchers/models.py`,
`accounting/models.py`, `budget/models.py`, and GRAND docs
`FINANCE_PAYABLE_RELATIONSHIPS.md`, `FINANCE_TRANSACTION_POSTING_RULES.md`,
`FINANCE_PAYABLE_CLAIMS_2026-09-10.md`, `DATABASE_BACKUP.md`. Older feature documents
describe their historical slices; current model definitions take precedence for
the mapping below. No GRAND application code or migrations were changed here.

## Existing records and ownership

Inventory0025 adds only supplied acquisition facts to PropertyDetermination in
default. It creates no new identity, Finance relation, role or write to finance.
Historical blank facts preserve the earlier serialized snapshot representation;
existing Finance links remain valid through migration. A subsequently verified
property successor needs a new association review. Importers must preserve these
document facts and snapshot/event bytes alongside existing UUID/predecessor maps;
do not substitute a delivery date or generate receipt-item numbering from IDs.

The optional [recognition journal preview](journal-source-preview.md) now exposes
source-bound posted debit observations to explicitly authorized owner-office ledger
readers. It creates no cross-store relationship or retained allocation. Documentary
receipt cost amendments are implemented atf0b20e2; Accounting valuation remains separate.

[Reviewed recognition mappings](receipt-journal-mappings.md) add protected default-store
claim/request relationships and retained journal UUID/sequence evidence in adapter0004.
Only default is written; the existing Finance journal lock is held through that
commit. No Accounting model, journal or authority is duplicated.

| Information | Existing authority | GSO relationship and boundary |
| --- | --- | --- |
| People and offices | `users.User`, `profiles.EmployeeProfile.assigned_department`, `departments.Department` in default | Use existing actors and employee/office directory after migration. Keep shell IDs in a reviewed import map; do not reuse them as GRAND IDs. |
| Supplier/payee | `finance.FinanceParty` in default | It is versioned by department/code/version and release; it does **not** currently have a public UUID. Preserve that composite identity plus label/release evidence. Resolve an existing party through Finance; do not create a second supplier authority or auto-match by name. |
| Payable case | `vouchers.VoucherCase.public_id`, `state_version` in default | Link by case UUID and reviewed version. The requesting office, current processing office, Finance ledger owner and GSO custody owner can differ. |
| Receipt-related payable evidence | `PayableIntake` and `PayableDocumentEvidence` in default | Existing procurement, delivery and inspection/acceptance references are text; present/waived/reviewed status is governed by Finance. A GSO receipt can be supporting evidence; it must not silently mark Finance's checklist present/approved. |
| DV lines | `DisbursementVoucher` / `VoucherLineItem` in default | A line has a local PK, description, account code and amount; it is not a physical-item register and has no portable line UUID today. Do not invent one in a contract. A future adapter must retain a reviewed local-to-source mapping. |
| Obligation | `budget.ObligationRequest.public_id`, `state_version`, `snapshot_checksum` in finance | Preserve authoritative UUID and correction lineage. Do not substitute voucher compatibility `BudgetObligation`. `PayableObligationAllocation` already owns obligation-to-claim capacity. GSO must not consume that budget capacity again. |
| Ledger dimensions | `accounting.Fund`, `LedgerAccount`, `ResponsibilityCenter`, fiscal year in finance | Codes are scoped to Finance owner, not globally unique. ResponsibilityCenter has an explicit core `office_id` snapshot. Pin the reviewed identities/codes and retain labels; do not use physical custodian department as ledger owner. |
| Financial posting | `VoucherPostingRequest.public_id`, kind/version, payload/rule checksums, accounting-entry UUID in default | Reuse this governed path when an eligible voucher transaction needs recognition. Do not introduce GSO journal writes, alternate recipes or a second posting-request queue. |
| Posted amounts | `accounting.JournalEntry.public_id`; `JournalLine.sequence` within entry in finance | Link to entry UUID + line sequence + source/checksum/state evidence, not a database PK alone. Keep reversal/origin lineage. Liability claim-credit lines and asset/expense debit lines serve different purposes. |
| Physical stock/assets | `inventory.Asset`, `ConsumableItem`, `StockMovement` in default | GSO owns accepted quantities, item identity, physical condition and custody. Financial valuation and posting remain Accounting decisions. |

## Receiving structure and remaining extensions

Use a receipt header and receipt lines, alongside the existing register. Do not
embed a single DV foreign key in `Asset`: a delivery can be partially accepted,
cover several assets/supplies, or be paid in several claims.

**Receipt header:** public UUID, GSO owner office, supplier reference/label snapshot,
delivery reference/date, inspection/acceptance reference/date, recorded actor,
review status/version and retained evidence. Start with draft, submitted, accepted,
returned. Only a separately authorized reviewer can accept another person's entry.
Acceptance records inspection evidence; a button cannot stand in for a physical
signature. Accepted-receipt correction/reversal remains a future extension and must
retain the original and reason; current accepted records are read-only.

**Receipt line:** receipt + stable line number, description/specification/unit,
delivered/accepted/rejected quantities, rejection reason, acquisition source
(purchase/donation/transfer/found-at-station/legacy as supported), and documented
cost facts. Enforce accepted + rejected <= delivered; keep unresolved quantity
visible. Rejected/uninspected goods do not enter available stock.

**Register outcome:** accepted serialized equipment produces one asset per unit;
accepted ordinary supplies produce a receipt movement on an existing supply item.
Keep explicit receipt-line-to-asset/movement links and unique posting identity so
double submit cannot duplicate stock. Preserve existing legacy pooled assets until
reviewed splitting; do not split historical values automatically. Serial/chassis
matches require review; property-tag uniqueness needs legacy duplicate preflight.
Do not auto-generate official property numbers until the LGU numbering rule is known.

Only add these tables/fields when implementing the corresponding tested workflow.
No generic document, warehouse or procurement engine is needed for this slice.
See [implemented receiving and explicit limits](receiving.md); the acquisition-source
classification and incremental remainder processing above are not yet implemented.

## Claim source review - 2026-10-17

Re-fetched both repositories: GSO `9ae80c0`, GRAND `32ab046`, each 0/0 against its
remote master. GRAND's local signed Form1 work is still unpublished and was not
changed. Inspected actual `vouchers/access.py`, `case_exports.py`, `services.py`,
models and router, not only earlier design documents.

`vouchers.services.prepare_voucher` deletes/recreates voucher lines on re-preparation.
Therefore a PROTECT FK to `VoucherLineItem` would block an existing Finance workflow.
Use the stable case relation plus reviewed line-local-ID/version/content evidence;
on replacement, retain history and require review. Do not assign a fictional line
UUID or silently retarget by matching amount/description. Same-store case PROTECT
is appropriate for the eventual installed adapter; the numeric line ID alone is not
a portable import identity. Recheck the source before any allocation write.

The new optional `inventory.finance_sources.resolve_claim_line` is read-only, has
no route or tables, and refuses lookup in the standalone shell. In GRAND it calls
the existing `can_view_workbench` and `visible_cases_for_user`, scopes the line to
the selected case, and reads under the existing default-store case lock. It retains
case UUID/version/stage, actual Finance owner, party composite identity, DV and
line content in a hashed snapshot. It does not expose tax identifiers/bank details
or write to Finance. A snapshot is an observation, not approval or capacity.

Four pure payload/standalone-disabled tests and five tests against actual GRAND
models/settings/router pass. The latter use isolated SQLite default/finance schemas
and cover source visibility, UAT read access, line replacement and version changes.
A subsequent six-test run also installs GSO schemas and creates a receipt/audit
record using GRAND identities in default, with no Finance query or inventory table
in finance. This is fresh SQLite compatibility, not populated import or native
concurrent re-preparation proof.
Seven native MySQL integration tests also pass, including a source reader observed
waiting on the preparation case lock and rejecting the old line after replacement.
Reviewed receipt-line attribution is now implemented below. Read authority does not grant mutation authority:
UAT viewers must be rejected on writes, and independent Finance review must respect
the pinned owner even when GSO custody belongs to a different office. No default
role grants or permission-copying from the prototype are allowed.

## Receipt-side review evidence and corrections

The [cost-correction design](receipt-cost-corrections.md) records actual materialized
cost copies and the selected amendment boundary. Claim support pins receipt facts
as well as the Finance claim source. The optional
adapter's migration0002 adds nullable receipt snapshots without inventing old review
evidence or altering approved amounts. Current development/release evidence belongs
in CONTINUE. Reviewed documentary amendments are implemented atf0b20e2, and
reviewed recognition amount mappings atba17b63. Physical quantity and cost-component
allocation, financial valuation and official outputs remain incomplete.

## Financial relationships (adapter after physical receiving)

Implemented initial workflow on `codex/reviewed-receipt-claims`: optional
`inventory_finance` app, installed only with GRAND. Its initial migration depends on
inventory0015, departments0005 and vouchers0038 from the inspected graph. Same-store
PROTECT relations retain the receipt line, case, Finance owner and actors; replaceable
DV lines retain local identity and source snapshot instead of a foreign key.
The initial service proposes and independently approves a documented claim
support amount, with explicit permissions, owner checks and stale-source rejection.
It does not allocate physical quantities, determine acquisition cost, reserve Budget
capacity or post accounting entries. Quantity/cost-component attribution remains
later work; recognized-JEV amount mappings now use the separate adapter0004
workflow. Rejection/withdrawal retain events and
original approval evidence; stale or replaced source lines can still be withdrawn.
Scoped reads require both attribution permission/office scope and existing case
visibility. Actual-model service, native capacity races and integrated HTTP tests pass; browser
clerk/reviewer/withdrawal flow was inspected. GRAND-base screens and signed-preview confirmation are included, with HTTP/native
and browser validation recorded in the validation document. Approved support is capped both by the
claim line and, across claims, by accepted quantity times positive documented receipt
unit cost, including an independently reviewed documentary amendment where present.
Unknown/zero effective cost fails closed. This ceiling is documentary support, not Accounting valuation. The app
is not enabled in the standalone shell. See [claim support](claim-attribution.md).

The implemented relationships are many-to-many through explicit reviewed amounts:
one receipt line may support parts of claims; one recognition debit may support
several receipt claim links. Claim support retains receipt/line identity, case UUID,
financial owner, source/receipt evidence, amount, basis and reviewed actors. The
separate [recognition mapping](receipt-journal-mappings.md) retains posting-request
identity, journal UUID/line sequence and independently reviewed amount, capped by
both debit and claim support. Physical allocated quantity remains unimplemented;
never infer it from money or equate delivery value with payment net.

Keep gross invoice amount, recoverable/nonrecoverable tax, deductions, freight,
discounts and approved acquisition cost distinct. A source allocation cannot exceed
its approved amount or accepted quantity. Totals are checked in exact Decimal
arithmetic. GRAND uses 18-digit, two-decimal money; new financial amount fields
must match that capacity. Existing GSO unit-cost fields are narrower (13,2) and
quantity uses three decimals for supplies. Widen only with its own migration/test;
define rounding and residual allocation before a cost split is accepted. Unknown
legacy cost is NULL, not zero. Optional FIFO is physical lot allocation, not a
decision that Financial inventory valuation uses FIFO.

No automatic PPE/semi-expendable threshold or depreciation calculation is selected.
The [property-record design](property-record-design.md) selects retained supplied
determinations, individual custody and a separately authorized native Finance
dimension link. Supplied determination/useful-life evidence is implemented in
inventory0024/default with protected Asset/native-user relations and retained
successors. Native dimension association and class/fund SPC remain unimplemented;
Accounting's SPLC is separate. No Finance writes or cross-database FK are added.
Accounting must pin treatment, fund/account, applicable policy release and evidence.
Keep physical custody for semi-expendable items after expense recognition; never
delete an asset because its carrying value reaches zero. Corrections, impairments,
disposal derecognition and recoveries use the existing reviewed Finance workflow.

Use same-database protected relations to GRAND records when the adapter is installed
and migration dependencies are known. Across default/finance, use UUID/composite
identity + retained snapshots, explicit scoped resolution and currentness checks;
no Django cross-store FK. On failure, leave the physical receipt accepted with a
visible unresolved Finance link; do not fake posting or roll back a physical fact
because a later Finance operation failed. Follow GRAND's existing request/recovery
pattern when a real cross-store write becomes necessary. No new sync framework.

## Migration and merge plan

1. **Implemented prerequisite:** additive `0012` assigns distinct public UUIDs to
   existing assets, supply items and stock movements, retaining all integer PKs and
   links. Nullable expansion, per-row backfill, then unique/not-null. Use a write
   pause when applying it; retries cannot assign one shared UUID to historical rows.
2. Preserve migration history `0001`–`0011`; never fake-apply or renumber it during
   merge. GRAND currently has no `inventory` app in the inspected tree. Recheck its
   migration graph at integration time. All inventory migrations route to default.
3. Integration of code and import of data are separate steps. Start GRAND schema
   from its own migration graph, then dry-run a reviewed import keyed by source
   installation + entity + public UUID. Existing users/departments/parties need an
   explicit mapping. Do not move the standalone database over GRAND's default DB.
4. Import assets, supplies, events, lots, allocations, transfers, verification and
   disposal evidence in dependency order. Some historical entities still have local
   PKs only: map source installation/table/PK and retain source hashes. Reconcile
   row counts, quantities, money and evidence checksums before accepting a batch.
   This importer is planned, not implemented. Do not import standalone passwords
   or grant privileges merely because a source user had them.
5. Native MySQL validation is required before GRAND merge. GSO0015 replaces inherited
   conditional uniqueness with generated markers and duplicate preflights, following
   GRAND's pattern. Standalone MySQL tests pass, including races and populated upgrades;
   Actual-GRAND router/two-store native suites now pass (latest114/114 at25004cc).
   This does not prove operator installation or historical import. See [native tests](native-testing.md).
6. Use GRAND's coordinated default/finance backup and restore procedure, separately
   capturing private uploads and exports. Keep pre-import backup, source package,
   import mapping and reconciliation receipt. Rehearse restore before cutover.

## Acceptance examples for the adapter

- Ten ordered computers: six accepted now, two rejected and two pending; only six
  asset identities result. Later delivery has its own evidence; no duplicate stock.
- One receipt split across two claims; one claim consolidates two receipts and
  several obligations. Existing Budget allocations remain authoritative and are
  neither duplicated nor inferred from receiving quantities.
- One voucher contains equipment, freight and services; only reviewed allocations
  attach to assets. Payment withholding does not reduce acquisition cost silently.
- A posted recognition is reversed or its mapping superseded: GSO retains the old
  linkage and shows review needed; no automatic rewrite of an audit snapshot.
- Department A cannot discover B's vouchers via a GSO link. GSO visibility alone
  does not grant Finance source access; apply original-source and mutation checks,
  including GRAND's UAT-viewer denial rules.
- A retry after interruption resolves the same receipt/allocation identity and
  checks payload/version equality; a different payload cannot reuse that identity.

Production remains unaccepted. Human legal/accounting acceptance cannot be supplied
by choosing the recommended engineering approach.

## Reviewed documentary cost amendments

See [cost corrections](receipt-cost-corrections.md). Inventory0020 is operational
`default` data only; optional adapter0003 declares that prerequisite. Preserve
amendment UUID, receipt-line mapping, predecessor, original/effective basis, source
hash/size, native actors and decision events when merging/importing. Local foreign
keys are not portable identifiers. No asset/stock/FIFO value or Finance posting is
rewritten. New claim support pins the accepted amendment identity/checksum and uses
its documentary cost ceiling; stale approved support requires explicit withdrawal.
No new Finance party, ledger, posting or cross-store relationship is introduced.

## Supplied requisition lineage

Inventory0022 adds default-store request headers, lines, fulfillment and events;
see [workflow](stock-request-design.md). Retain public UUIDs and remap protected
local item/user/movement keys when merging installations. Requesting-department
IDs resolve through GRAND's native directory; their retained labels are historical,
not identities for automatic matching. A physical issue links exactly one stock
movement to a requested line. Neither the issue nor FIFO cost is an Accounting
expense posting. Reuse this lineage for future reviewed returns/RSMI support;
do not create duplicate Finance accounts, journal lines or approval authorities.
An installation-to-installation importer is not implemented: retained audit
snapshots also contain source-local IDs. Any later import must preserve original
snapshots and document reviewed identity mappings, rather than silently rewriting
history/checksums. Code/migration integration into GRAND is tested separately from
that unimplemented data-import operation.

Inventory0023 supplies reviewed return lineage in default: original issue UUID,
optional original allocation identified through its source receipt UUID, return
UUID, new movement and optional return lot. The cost is retained only from an
explicit documented allocation; otherwise it stays NULL. This is operational
stock history, not a Finance expense reversal or a replacement valuation policy.
Both requisition fulfillment and original issue remain unchanged after a return.

## Property dimension requests

Adapter0005 adds default-store PropertyFinanceLink/Event; see the
[implemented workflow and locks](property-finance-links.md). An explicit GSO request
shares one verified record/packet with a selected native department; Finance
proposes and independently approves UUID-based Fund/account/optional-center links.
Optional recognition support must identify an approved mapping whose receipt line
materialized exactly that asset. Legacy/donation paths need no voucher.
Finance remains read-only to GSO services. Preserve request/predecessor/event UUIDs,
property and dimension snapshots, source packet and explicit Department/user key
remappings in any future installation import. This code does not implement that
import or deploy the module into the operator GRAND instance.

## Historical authentication exclusion

The [historical-data audit](security-and-recovery.md) confirms authentication and
session records in old prototype database blobs. Future imports must exclude
credentials, sessions, tokens and privileges; source business actors need reviewed
mapping to native GRAND identities, with original evidence retained. This is an
acceptance requirement for the still-unimplemented importer, not a claimed filter
or completed remediation. Existing same-installation recovery tests do not prove
safe cross-installation import.
