# Property records and Finance relationships

## Approved allocation development direction — 2026-10-18

DECISION-FIN-002 authorizes explicit documented asset-cost allocations with
independent authorized Accounting review and an audit trail, including synthetic
development/tests. Retain original source amounts and the allocation basis; do not
silently divide costs or rewrite existing records. Until applicable valuation
policy is confirmed, allocations are not officially approved accounting values
and generate no automatic JEVs. A bounded local documentary worksheet is now
implemented for one accepted registered asset receipt line, with explicit component
amounts and independent Accounting review; current verification is recorded in the
handoff. This does not establish valuation policy or operational acceptance. See
[the allocation contract](asset-cost-allocations.md), the
[decision register](../IMPLEMENTATION_DECISIONS.md) and current handoff.

## Working draft preparation — 2026-10-18

The autonomous mission's local branch `codex/grand-autonomous-workflows` adds ICS
and SPC preparation beside the existing PAR draft in Property records. Current
test/preview evidence and publication status belong to [GRAND's handoff](../../CONTINUE.md).
This is the roadmap's explicitly authorized placeholder slice, not official-form
acceptance or a completed class/fund SPC projection.

Both routes reuse existing native property-document view authority. UAT viewers
may prepare a blank draft because the operation reads no asset/source rows and writes
no operational or Finance records. Unauthenticated/ungranted/non-GSO access is
denied under the existing identity contract. User-entered HTML is escaped,
responses are private/no-store, formsets are bounded to five entries and normal
CSRF protection remains. No permission, model, migration or routing policy changes.

Known values are supplied per sheet; unknown fields stay blank, and explicit zero
stays zero. Numbers/signatory labels remain supplied placeholders. Exact decimal
arithmetic checks a fully supplied quantity × unit cost against its supplied total;
it never invents a missing cost or total. SPC balances are supplied facts, not
calculated or certified quantities. No threshold-based classification, Finance
mapping, signature, document number, custody event or stock movement is created.

The asset-specific ICS entry additionally requires the existing asset-register
export grant and a fresh owning-office lookup on GET and POST. It copies only
register name, quantity and recorded unit cost into editable draft fields. Register
tags are shown as provenance, never relabelled as local inventory item numbers.
No recipient, unit, total, fund, useful life or acknowledgment is inferred. Blank
cost remains unknown and zero remains zero; copied values do not establish reviewed
classification or financial valuation. This reduces repeated entry while preserving
separate export authority, including for UAT viewers. Other-office ownership stays
hidden even when the asset's current custody is assigned to the requesting office.

The sheet is not saved: edit → preview → Print / Save as PDF, then retain locally
in approved office storage. A successful preview collapses the editor; invalid
input remains expanded with a correction message and previous entries. Native
details/summary controls support keyboard editing; wide tables scroll inside a
labelled region on small screens and print in landscape with draft wording intact.

Field references: existing PAR preparation and the previously reviewed SPC Annex
A.2 recorded in [the source matrix](coa-requirements.md). The
[DSWD-hosted 2022-004 copy](https://car.dswd.gov.ph/wp-content/uploads/2023/02/COA-CIRCULAR-NO.-2022-004-May-31-2022.pdf)
is available as an ICS reference, and [ONAR's LGU companion record](https://naro.law.upd.edu.ph/issuances/3842)
was rechecked on 2026-10-18. This session does not claim a new complete annex,
effectivity/amendment or local-form review. These working fields are not asserted
to reproduce an accepted municipal template. Resolve
[DECISION-GSO-001](../IMPLEMENTATION_DECISIONS.md#consolidated-owner-decisions--2026-10-18)
before official output/issuance. Retained movement-source projection, native Finance
links and eventual class/fund reconciliation keep their separate contracts below.

### Reviewed SPC source worksheet

The separate source worksheet selects supplied class/fund labels from the owning
office's latest verified semi-expendable determinations. It requires existing
property-document, property-movement and asset-export read authority. Unknown
class/fund records are excluded explicitly; no empty result certifies zero stock.
Exact Python label comparisons preserve distinct supplied values even under MySQL
case/accent-insensitive collations. Labels never substitute for approved native
Finance identities.

For every matching item, reuse `property_movements.project` unchanged, including
its asset lock, opening checks, retained-history/file verification, current physical
sources, pending-correction checks and running-quantity rules. An unresolved item
exposes no opening, movement quantities or usable balance to the output context.
The selected current class/fund must also match the reviewed opening's original
determination; a successor label cannot silently relabel earlier quantities.

Print the source references, documented opening/stock changes, per-item running
quantities, supplied unit costs and source office/officer. Do not calculate a
group quantity, receipt cost, valuation or journal. Each item is checked when read;
this is not a retained atomic group snapshot or historical-knowledge report.
The worksheet uses every matching item without a silent retrieval cap, includes
unresolved items, repeats its draft/source table header when printing and links
back to existing correction workflows. It is a practical source-preparation aid,
not completion of official SPC parity or a certified class/fund balance. Native
and focused integrity/authorization verification must pass before this checkpoint
is treated as complete; CONTINUE.md owns the actual evidence.

Design decision, 2026-10-17. The supplied-document workflow below is implemented;
native Finance links are implemented separately in the optional adapter; SPC
output and Accounting treatment approval remain separate requirements.
GSO source:25004cc; GRAND source:32ab046. Finance's unpublished work is preserved.

## Evidence and consequence

Re-inspected pages2,3,7,8 of the retained [COA2024-006 official ONAR copy](https://naro.law.upd.edu.ph/storage/01JT2JXVWNE95WHFN0FE53KQC9.pdf).
The [source receipt and wider review](coa-requirements.md) retain its hash and limits.
Sections3.1–3.8 distinguish recognition, acquisition, issuance and historical
transitions. AnnexA.2 specifies a property-unit SPC by class and fund, including
item numbers, useful life, expiry, source references, quantity/cost, custody and
balance. Accounting's SPLC is separate. Publication date, later amendments and
local adoption remain unverified; do not equate filing date with effectivity.

The following choices are engineering decisions. They do not add a tax rule,
recognition recipe, automatic accountability cancellation or local signatory policy.

## Use existing identities; add retained documentary facts

| Fact | Current source | Selected treatment |
| --- | --- | --- |
| Individual physical item | Asset.public_id; new receiving makes one asset per accepted serialized unit | Keep that identity for PPE and semi-expendable property, including after expense recognition. Do not turn the item into consumable stock. |
| Acquired/received value | ReceivingLine and its registered_asset; documentary amendments are separate | Retain original and effective documentary cost separately. Neither is an approved financial carrying value. Unknown stays unknown. |
| Property type | Asset.inventory_class is only a reporting group | Retain a supplied PPE/semi-expendable determination with its source, date and stated authority. Never infer it from cost, item type or account-code text. |
| Useful life and expiry | Not represented | Retain the documented duration with its unit, explicit start basis and supplied expiry date when known. Do not invent defaults, compute release of accountability, or discard custody at expiry. |
| Fund and account | Asset has free-text fund/account labels; GRAND has native UUIDs | Source labels remain labels. A separately reviewed optional adapter link pins Finance owner plus Fund/LedgerAccount UUIDs and content snapshots; no cross-store FK or name matching. |
| Issue/transfer/return | AssetTransfer UUID and retained actors/dates/references | Reuse acknowledged movements. Pending/cancelled requests are not physical issues. Preserve source-document and actual custody-event dates separately. |
| Disposal | AssetDisposalCase and its events/evidence | Reuse completed disposal facts. A missing count or expired useful life is not disposal. |
| Legacy grouped quantity | Asset permits historical pooled rows | Flag for explicit reconciliation; do not silently split identity, cost or custody among invented units. |

The implemented vertical workflow records and independently checks a supplied property
determination for an existing individually tracked asset. Bundle treatment,
documented useful-life/expiry facts, source fund/class labels and reason in one
revision, with one private source packet, public UUID, explicit source date,
recorder, checker, state version and immutable decision history. Correction creates
a successor retaining its predecessor; cancellation/rejection preserves evidence.
This checks a supplied determination, not a new GSO power to approve Accounting
treatment. UI wording must distinguish documentary verification from Accounting
approval. Unknown or missing source facts stay explicit and block official output.

Keep the record in inventory/default with protected Asset/native-user relations.
Migration0024 adds PropertyDetermination and PropertyDeterminationEvent, together
with entry/review/history/private-download screens and scoped asset navigation.
Lock linked receipt first, then asset, then property case; same-version retries must not
produce duplicate effective revisions. Source files and the current asset/receipt
basis must still agree at verification. A changed receipt cost basis requires review,
not silent reclassification. Receipt locking serializes against documentary cost
amendments without reversing receipt acceptance's lock order. Do not acquire
Finance locks from the core workflow.

Only one pending entry per asset is permitted by an ordinary unique constraint on
a virtual generated marker. Verify/reject requires a different recorder/reviewer;
cancel requires the record grant. Dedicated view/record/review permissions plus
owning-GSO asset visibility are checked in services and HTTP. GRAND UAT mutations
and ungranted superusers are denied; no automatic role grants. Source entry uses
signed actor/asset/basis/request identity with a30-minute form lifetime; exact
replays retain the same record. Decisions require the current pending version.

Useful life is an exact positive duration with explicit unit and start basis, or
NULL. Supplied expiry may remain unknown even when duration is known; no date is
computed. Source fund/class labels are documentary text. Receipt-origin assets and
legacy individual assets are supported; pooled quantities are rejected pending
reconciliation. Verified predecessors remain intact when successors are checked.
Changes to retained asset/receipt basis display a review warning. History checks
detect drift but do not authenticate documents or defeat privileged administrators.

Private packets use `inventory/property-determinations/<UUID>/...`, the existing
PDF/image validation and15MB limit. No public media route is created; downloads are
scoped attachments with no-store/nosniff. Include this namespace in paired recovery
and run `check_property_evidence`. Failed database transactions may leave unreferenced
files for that read-only checker to report; they are not silently deleted.

## GRAND authority and dimension link

The [implementation design](property-finance-links.md) now supplies the explicit
GSO-to-Finance request boundary missing from this initial design. The optional
adapter implements it; a ledger grant alone cannot expose a GSO-owned packet.

Inspected accounting/models.py: Fund, LedgerAccount and ResponsibilityCenter have
public UUIDs, owner department, codes and effective/active facts. Used dimensions
have governed edit rules. A code is unique within its ledger owner, not globally.
Inspected inventory_finance/journal_sources.py and journal_mappings.py: existing
recognition mappings already pin fund/account identities from a posted debit.

Reuse an existing current reviewed recognition mapping when it establishes the
relevant dimension facts, retaining that mapping UUID and its source snapshot.
It still does not establish useful life, property treatment or full acquisition
valuation. Do not require a payable/JEV link for donated or legacy property whose
support legitimately follows another documented path; unresolved links stay absent.

For an explicit native dimension association, require the real Finance owner and
existing ledger visibility plus a dedicated mutation grant. A GSO record grant or
ledger-read grant alone cannot approve that association. Recheck actual permission
helpers at implementation. Deny UAT mutations and implicit superuser bypasses.
Never grant permissions on migration. Pin owner/UUID/code/label/effective facts,
and preserve stale/archived source history. Use the established durable default
commit inside the necessary Finance read/lock transaction; no Finance writes.
Native race tests must establish the final lock order before this path ships.

## Output and remaining prerequisites

Migration0025 extends the existing PropertyDetermination with nullable supplied
acquisition_date, acquisition_reference and receipt_item_number. The same private
packet, independent document check, source locks, signed request, version and
successor rules apply. Dates/numbers require a source reference in that packet;
unknown dates remain NULL even if a source number is supplied. Future acquisition
dates are rejected. Existing Asset.purchase_date and property_tag remain untouched.
These fields retain a source's assertions; they neither allocate an annual series
nor validate local numbering policy, quantities, stock opening balances or valuation.
No uniqueness scope or format is invented for historical supplied numbers.

Historical blank acquisition facts are omitted from the snapshot representation
so migration does not rewrite existing event checksums or Finance request bases.
Nonempty new facts join the immutable snapshot and exact replay comparison.
Corrections require a successor; an independently verified successor makes a prior
Finance association stale while retaining its approval history. The working register
shows the supplied acquisition date separately from the register purchase date.
Numbered issue/transfer/disposal source facts and reviewed opening reconciliation
remain required before a class/fund SPC can calculate its stock balance.

The property working register (`property-records/`) now provides a paginated,
owner-scoped preparation view across assets, including retired and undocumented
items. Filters use only the latest verified supplied treatment/class/fund labels;
a pending successor never replaces those labels. Missing documents, grouped
quantities, missing dates/cost/life/class/fund/tag and changed source facts remain
visible for review. Each displayed determination's history and private file are
checked on the read. Invalid filters return errors and no records. No totals,
historical balances, native Finance identity inference or official-form readiness
are asserted. This view performs no mutations or Finance queries and needs the
existing property-document view authority. It is a preparation aid, not the SPC.

The eventual SPC is a class/fund working projection of retained item and movement
facts, not a second quantity ledger. Its property/item numbering must be explicitly
recorded and checked against the applicable source instructions before official
output. A one-asset audit list cannot be presented as the completed class/fund SPC.
Grouping must not net away individual custody. Legacy opening balances, transfers
between funds/classes, unknown source dates and discrepancies need explicit reviewed
entries; they cannot be reconstructed from today's labels or created_at timestamps.

Rechecked retained AnnexA.2 instruction page8 during the working-register slice.
It distinguishes the assigned property number from receipt/issue item numbers.
The latter examples encode acquisition year, annually renewed acquisition order,
and item series. Existing Asset.property_tag must not silently double as all three
identifiers. Next card work must retain explicitly supplied source numbering and
document dates for acquisitions and acknowledged movements before reconstructing
balances. The instruction's balance is received quantity less issues/transfers/
disposals, which is distinct from continuing individual custody after issue.
Therefore neither active asset count nor total named custody can populate that
balance. Opening stock and external transfers require documented reconciliation.

Source trace at9fc6acc, before implementing card movements:

| Existing source | Retained facts | Card implication |
| --- | --- | --- |
| Accepted ReceivingReceipt/Line | Delivery/inspection dates, references, accepted quantity, materialized asset | Keep the physical receipt link; neither timestamp nor an unassigned custodian proves a historical stock opening. |
| Acknowledged AssetTransfer handoff | Transfer date/reference, source/destination office/person and acknowledgment | It may be an initial issue, reassignment or reissue. No existing field establishes a stock decrease for every handoff. |
| Witnessed return | Confirmed custody return, condition and private evidence | Physical return does not itself establish serviceable stock or an accounting reversal. |
| Completed AssetDisposalCase | Completion date/reference/method, approval and completion attachments | Use completed facts only. Pending authorization and retired register status are not substitute source events. Case identity is currently a local PK; imports need explicit remapping. |
| Supplied property determination | Reviewed classification/acquisition facts and predecessor history | Today's verified successor does not retrospectively recategorize earlier card transactions. Preserve the source version attached to each transaction. |

Selected next approach: attach reviewed source facts to existing physical events,
then derive the card from a documented opening and the complete ordered source
chain. Do not maintain a second editable custody balance or subtract every handoff.
Explicitly distinguish movement between end users from stock issue/return, retain
assigned item numbers, and stop a balance projection at missing or contradictory
history. Unknown legacy openings must remain unresolved. Source annotations must
not independently move custody or post Finance journals.

The disposal source trace exposed two prerequisites. Asset-before-case locking is
now explicit for request/review/resubmission, including fresh authority checks.
Migration0026 now supplies new-upload hashes and shared save-service validation
as described below. Legacy attachments retain unknown hashes. A completed case
with unknown evidence must not be presented as verified card support; do not
invent hashes for old uploads as though they were captured at upload time.

Physical receipt cost-component allocation remains a separate unfinished workflow:
documented allocation targets need exact quantities, source amounts, component
basis and rounding/residual treatment. Existing claim/journal support amounts are
not that allocation. Preserve gross consideration, taxes, freight, deductions and
acquisition value separately; Accounting owns inclusion/treatment decisions.

Acceptance for the supplied-document workflow: known/unknown useful life; no guessed
expiry; supplied semi-expendable determination below/above an apparent threshold
without automatic override; stale source rejection; independent review; protected
history and successor correction; forged/stale HTTP posts; owner/UAT denial;
unchanged custody/Finance; populated migration; native competing reviews; paired
restore retaining source bytes and decisions. Official SPC/PAR/ICS parity and local
acceptance remain separate, visible gates. This design does not satisfy them.

Disposal evidence boundary (0026, locally validated): new uploads retain SHA-256
and actual byte count after service-level validation of the whole action. Migration
leaves legacy hashes blank and history untouched. Operational authorization and
completion preserve legacy workflows with explicit unknown hashes, but reject
missing files and detectable changes. `verify_case_evidence` is strict by default
for future card-source consumers; a completed case alone is not verified evidence.
The read-only checker reports unknowns as an investigation outcome, without
backfilling/deleting files. A hash proves consistency with retained bytes, not the
truth, legal sufficiency or malware safety of the supplied document. File storage
and DB transactions remain separate; interrupted writes can leave orphan files,
which the checker reports for investigation. No automatic cleanup is authorized.
