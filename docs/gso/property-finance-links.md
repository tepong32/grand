# Property links to native Finance dimensions

Selected design and implementation, 2026-10-17. Local validation passed; see the
handoff for publication state.
Build on the supplied property workflow published at9070496 and the
[property-record design](property-record-design.md). This is an engineering
association workflow, not a new Accounting recognition or valuation procedure.

## Verified source and ownership

Inspected clean GRAND candidate a533482: accounting/models.py,
accounting/access.py, accounting/views.py, accounting/services.py,
vouchers/access.py and departments/models.py. Its current remote master is
32ab046; do not call the candidate a published primary revision.
The existing GSO adapter models/access/services and journal mapping path were
also inspected at9070496.

Fund, LedgerAccount and ResponsibilityCenter live in finance. Each has a public
UUID, a numeric department owner, effective dates and active state. Fund/account
codes are owner-local. Department itself has a numeric key and slug, but no
public UUID. GSO Asset and property determinations live in default. The native
user's assigned department determines ledger visibility; a ledger permission
does not grant arbitrary GSO property visibility. Neither a superuser flag nor
matching text establishes an owner relationship.

The earlier design specified Finance review without defining how that office
receives a GSO-owned record. Implement an explicit request, rather than widening
the core property queryset or requiring a fictional common GSO/Finance owner.

## One request and its retained decisions

Migration0005 adds PropertyFinanceLink and immutable events in inventory_finance/default.
Reuse protected FKs to the property determination, native Department and users.
Retain public UUID, source/property snapshot, source checksum, selected Finance
department, request reason/date, actors, state version and event checksums.
Keep Fund/LedgerAccount UUIDs and their observed snapshots as scalar data;
there must be no cross-store foreign key or duplicate dimension table.

1. An explicitly authorized GSO recorder requests association of the current
   verified property determination with a selected native department. Display
   exactly which property facts and source packet will be shared. The directory
   selection is explicit, not inferred from department names or fund labels.
   The request itself grants no financial authority and cannot select dimensions.
2. A user assigned to that selected department needs the existing explicit ledger
   read grant and a dedicated propose-link grant to select a Fund and LedgerAccount
   from that department's finance store. Retain an explicit effective/as-of date
   and documentary reason. Snapshot UUID, owner, code, name/title, relevant account
   attributes, effective dates and active/posting state. No automatic match or
   classification based on asset value, property class or account code.
3. A different authorized Finance reviewer approves or rejects that association.
   Approval requires current property/evidence and dimension snapshots. The
   reviewer must differ from both requester and proposer. This approves a link,
   not useful life, carrying value, depreciation, posting or payment.
4. GSO can withdraw its request; the selected Finance office can reject or
   withdraw its association with a reason. Retain all prior facts and decisions.
   A replacement is a new request with an explicit predecessor; never edit the
   selected owner/dimensions of a reviewed link in place.

States: requested, proposed, approved, rejected, withdrawn. One nonterminal link
per property determination (requested/proposed/approved) via the established
virtual nullable marker and ordinary unique constraint. A stale approved link
remains historical, but cannot supply current output; explicit withdrawal is
needed before replacement. A successor property determination requires its own
request. Use signed actor/property/source/request identities, exact replay and
state-version checks. Permission grants are operational, never migration data.

Explicit permissions are inventory_finance.view_propertyfinancelink,
request_propertyfinancelink, propose_propertyfinancelink and review_propertyfinancelink
(all four in the inventory_finance app). GSO request/read also needs the existing
asset/property read authority and actual owning department. Finance read/propose/
review also needs accounting.view_general_ledger and the selected native owner.
Journal support additionally retains existing claim/mapping visibility checks.

Only the source GSO office and explicitly selected Finance office may read this
case. Finance readers additionally require the ledger grant plus a link view or
action grant. Do not expose other GSO records, asset lists or unrelated packets.
Scope a private download through the link, validate the retained packet bytes,
and reuse the existing attachment/no-store/nosniff behavior. UAT viewers may read
only where those same explicit grants permit; all mutations deny UAT. Core GSO
property URLs retain their existing owner restriction.

## Dimension semantics and existing journal evidence

For a new association, require dimensions active and effective on the supplied
as-of date, and a posting-enabled asset or expense account. These are picker
eligibility rules, not proof that Accounting selected the correct account.
Do not infer an accounting responsibility center from physical custody or an
employee's office. Add a center only when a supplied source calls for one, using
the same native owner/UUID/effective checks; absence is explicit.

Existing reviewed receipt-journal mappings remain the source for posted
recognition facts. If used as support, bind an exact approved mapping UUID whose
receipt line actually materialized this asset; verify its current claim/journal
basis and owner. Retain that identity and snapshot, not an inferred amount match.
Do not copy a stale mapping's dimensions into a new approved link or assert a
receipt support amount equals the asset's full acquisition value.
Donated and legacy individual property must work without a voucher/JEV link;
the supplied determination packet and explicit request form their evidence path.

## Transactions, drift and recovery

Implemented direct mutation order: linked receipt, asset, property determination, link,
then Finance Fund, LedgerAccount and optional ResponsibilityCenter. Acquire no
voucher case/journal locks after these: a journal-backed operation must instead
use the existing case-before-receipt mapping order, with a dedicated tested path.
Do not hide that extra ordering inside the direct dimension selector.

Finance read/lock transaction surrounds a durable default transaction, so the
default association commits while dimension locks remain held. GSO writes only
default. Reject calls nested in an unrelated default transaction. Locking is
required even when Finance setup does not explicitly call select_for_update:
its UPDATE must wait on the row lock. Re-read selected rows after locking.

Native setup editing has default-store issuance boundaries followed by Finance
writes and readiness updates; the link must not acquire those issuance boundaries
or fiscal-year/readiness locks. Test the actual interaction, not just two GSO
reviewers. Setup may change/archive a dimension after association commit; that
does not rewrite history. Compare current facts at every current-use boundary
and show a stale warning. No automatic replacement or background sync is needed.

Paired recovery must retain default links/events plus Finance dimensions and the
existing private property packet. Source Department numeric IDs must be explicitly
remapped when merging installations; retained slug/label is provenance, not an
automatic match. UUID conflicts or missing target dimensions require reconciliation.
The new adapter migration must leave existing records and grants untouched and
must not add inventory_finance to the standalone shell.

## Required implementation evidence

- Distinct GSO and Finance departments can complete request, proposal and review;
  ledger-only users, unrelated owners, ungranted superusers, UAT mutations and
  revoked permissions are denied in services, POSTs, downloads and controls.
- Donation/legacy path works without a voucher; journal-supported path verifies
  exact asset lineage, current mapping and the established lock order.
- Reject mixed-owner, inactive, out-of-date, nonposting and invalid-type dimensions;
  never guess unknown identity, source date or responsibility center.
- Exact replay is harmless; changed payload/version and competing reviews fail
  without duplicate events. Changed source packets/property predecessors/receipt
  basis/dimensions prevent approval and current-use claims.
- Native MySQL tests cover setup edit/archive versus approval, withdrawal versus
  review, property successor versus approval, and default rollback/event failure.
  Prove Finance tables unchanged by GSO operations.
- Replay populated migrations, inspect recorder/proposer/reviewer browser flows,
  and rehearse paired restore with an approved link and a retained predecessor.
  Run full actual-GRAND regression on its then-current source before VM publication.

Entry from the verified property page shares exactly one record/packet; the
adapter workbench lists only scoped requests. Finance proposal has a signed
30-minute preview; decision forms have distinct field prefixes and current
versions. The department picker shows native office codes to distinguish names.
GSO sees retained Finance history without an unsupported claim of current ledger
validation. Authorized Finance readers recheck current dimensions and optional
mapping support. A stale association stays historical and can be withdrawn even
when its Finance source is no longer available.

Services are in inventory_finance/property_links.py; views/templates remain in
the optional adapter. The standalone shell imports them only when installed.
The journal-backed path prefixes receipt/asset/property/link locks with the
voucher case, then locks claim/mapping/posting request/journal before dimensions.
Rejection/withdrawal need no current Finance source and acquire no journal locks.
No new private-file namespace or duplicate packet is created.

See [validation](validation-2026-10-16.md) for completed and pending gates.
Official class/fund SPC output, local signatory
acceptance and physical cost allocation remain subsequent requirements; this
workflow does not mark any of them complete.
