# RPCI and RSMI working preparation

Development 2026-10-19 adds Supplies → Prepare RPCI / Prepare RSMI → editable
preview → browser Print / Save as PDF. These are supplied, unsigned
preparation sheets under the owner's existing placeholder direction, not accepted
municipal forms, issued archives or complete certified reports. Actual validation
and local checkpoint/publication state belong to [CONTINUE](../../CONTINUE.md).

October21 development extends the original five-line entry to up to50 supplied
lines. Add5lines retains all posted values, including invalid amounts awaiting
correction, and requires a fresh preview before printing. Exclude a line with
the explicit checkbox; values remain in the editor for undo. Every included line
still passes the original exact-amount validation. Controls use ordinary form
submission and work without JavaScript. The50-slot bound limits request size;
it is not a completeness certification or official report size. Larger cohorts,
archival issuance remain separate work. The source starters below now supply
bounded RPCI count and RSMI issue cohorts.

## Start RPCI from reviewed counts — 2026-10-21 development

Supply counts → Reviewed → search by item/count-sheet reference → Start RPCI
draft from these reviewed counts. The starter loads every matching reviewed
observation across list pages in count-date/public-identity order, up to50. Empty,
invalid-status and larger selections fail explicitly; narrow the search instead
of silently losing records. Pending/cancelled records cannot start this workflow.
Repeated counts remain separate observations, never an inferred latest-item list.

The editable lines start with pinned item name/unit, the ledger quantity recorded
at count time and actual observed quantity (including zero). Today's balance is
not substituted. Count date/reference are copied to remarks. Unit value, monetary
difference, official stock number, report date and accountable-officer/signature
placeholders remain blank. Different dates do not establish a common as-of date.

Current GSO stock-read and separate stock-export authority are checked on GET and
every POST, including Add5. The selected source IDs and complete count-content
digest are signed for the actor for eight hours; current item ownership and exact
source contents are rechecked before preview. Later matching observations do not
expand the opened cohort. Changed/unavailable sources, missing/altered/expired
selection or actor mismatch block preview while retaining posted entries. Return
to Reviewed counts to start again; this is not a persisted draft/recovery store.

Starting count records remain separately visible and printed with original dates,
quantities, references, public identities and review versions. Editing, adding or
excluding draft lines never rewrites this source appendix. It is expressly a list
of starting observations, not an attestation that editable rows still match them.
Evidence files are not included/reverified; their governed source workflow remains
required before official use. No count/stock/Finance writes, new permissions,
models, migrations, archival issuance or completeness certification are introduced.

## Start RSMI from recorded issues — 2026-10-21 development

Movement history → choose Issued → filter recording dates and/or supply item/source
reference → Start RSMI draft from these issues. The new search is shared by history,
CSV, printable working copy and draft start; malformed filters fail closed. The
starter selects all matching original issues in the existing chronological order,
up to50. Empty/larger selections fail explicitly. Narrow the filters rather than
silently cap or net the output. Receipts, returns and adjustments cannot start it.

Copy item name/unit, original issue quantity, retained reference, department label,
recipient and optional recorded unit cost. Zero cost stays zero; missing stays
unknown. The receiving-office/recipient draft field now holds both existing160-
character source fields plus their separator without truncation. No inferred line
amount, stock number, issue date, report period, signatory or approval is populated.
GRAND recording timestamps remain labelled as recording facts, never source-event
dates. Copied costs are documentary data, not approved Accounting valuation.

The same actor-bound eight-hour selection guard is shared with the count starter,
using a distinct signing salt. GSO read/export, current ownership and original
content are rechecked on every POST. Source changes, access loss and invalid or
cross-workflow tokens block preview; no authority is encoded by an editable field.
Later matching issues do not expand an opened selection. Returns remain separate
movements and do not change the copied original issue quantities.

The original issue appendix remains printable after edits, additions or exclusions.
It identifies initial source facts separately from the supplied draft; it is not a
certification of current net stock, actual issue dates or complete monthly output.
The existing complete history/CSV remains available for larger cohorts. This adds
no movement, FIFO allocation, Finance entry, source correction, permission or schema.

## Access and data boundary

Require the existing explicit stock-read grant and current GSO scope on GET and
POST. UAT read remains allowed; ordinary-office stock readers, ungranted implicit
superusers and asset/export-only grants cannot prepare these drafts. No asset-read
or export grant is necessary for purely supplied drafts because no stored
asset/count/movement data is copied there. The count starter additionally requires
stock-export authority as described above, as does the issue starter.
The Supplies entry and new pages link to GRAND home without asset-dashboard access.
Existing scoped movement/count copies and CSV exports retain their separate grants.

Entries are nonpersistent, private/no-store and protected by the existing login/
CSRF/method boundaries. No inventory, count, evidence, custody, HR or Finance source
is changed. No new model, migration, permission, financial recipe or archive is
introduced. A saved browser PDF belongs only in approved office storage.

## Supplied facts and arithmetic

RPCI accepts inventory type/as-of and officer placeholders, stock references,
descriptions/units, supplied unit values, card/count quantities, signed difference
values and remarks. Count minus stock card is calculated only when both quantities
are present. Zero is explicit; blank physical quantity stays unknown. Do not infer
counted zero from a missing finding or take today's ledger balance as a past count.
The existing RPCPPE line validation is reused with stock terminology; its default
property-card behavior remains unchanged and has dependent regression coverage.

RSMI accepts supplied report/control number, period, source dates/RIS references,
stock descriptions/numbers/units, receiving office/recipient, issue quantities,
unit costs, line amounts and remarks. A stated period cannot end before it starts.
Source dates are entered facts, not inferred GRAND recording dates; no source
cohort is declared complete. The separate issue starter copies only the explicitly
filtered original movements described above. Returns/adjustments are not
silently netted into original issues.

Amounts remain supplied rather than calculated. When all corresponding quantities
and monetary inputs are known, check exact Decimal arithmetic, including explicit
zero, without inferring a rounding rule. Leave unresolved values blank for review.
No unlike-item/unit total, approved valuation, classification/account mapping,
official stock/report number, signature, journal or certification is generated.

## Source and acceptance limits

The previously retained [QC examples](coa-requirements.md#count-output-example-reviewed--2026-10-18)
and [SSMI/procedure review](coa-requirements.md#supplies-output-example-reviewed--2026-10-18)
were rechecked byte-for-byte and visually inspected. Their fields inform a bounded
working preparation, not target-LGU adoption. The QC SSMI grid, printed names,
approval roles and annex label were not copied as municipal policy or represented
as an accepted RSMI layout. No new applicable issuance/effectivity claim is made.

Larger complete reports, qualified inventory/monthly source coverage, archival issuance,
exact local fields/layout/revision/numbering/signatories, rounding/valuation and
formal acceptance remain separate requirements. Supplied lines do not prove
a complete inventory or monthly issuance report. The original five-line browser example fits one
A4 landscape page; longer supplied content may need additional pages. Synthetic
layout evidence does not qualify a local printer, production storage or recovery.
Finance remains NO-GO; no deployment or production operation is authorized.
