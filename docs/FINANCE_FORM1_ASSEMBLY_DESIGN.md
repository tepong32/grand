# Form 1 whole-source assembly boundary

Local source audit: 2026-10-11. Development branch
`codex/finance-budget-attribution`, base v0.7.153 / `61e690e4`.
This records the implemented draft assembly and retained-preparation boundaries;
independent whole-package decisions and issuance remain incomplete.
Keep the [source contract](FINANCE_FORM1_SOURCE_CONTRACT.md),
[Finance foundation gate](FINANCE_FOUNDATION_GATE.md) and
[current handoff](../CONTINUE.md) authoritative for validation/completion.
Use the [whole-package review/delivery contract](FINANCE_FORM1_PACKAGE_REVIEW_DESIGN.md)
for independent role scope, policy/overlap treatment, source-currentness observations
and the clerk-to-certification/issuance sequence.

## Current printable flow checkpoint - 2026-10-12

Complete flow draft PDF/JSON delivery now retains original account-review decisions,
every source share and all itemized flow columns. It rechecks original export
authority and does not certify source freshness or final issuance. All nine final
synthetic PDF pages and actual desktop/mobile downloads were inspected; bytes
reproduce the server package exactly. Validation and remaining gates are recorded
in the [source contract](FINANCE_FORM1_SOURCE_CONTRACT.md#printable-flow-delivery---local-checkpoint-2026-10-12).
Stock forecasts, PhilHealth, SPA subdivisions, shared-source allocations and final
package certification remain necessary before complete Form 1 assembly.

## SPA source allocation boundary - 2026-10-12

Retained Annex D labels identify development programs/projects (20% Development
Fund), LDRRM programs/projects, debt service, enterprise/public-utility subsidy,
aid to barangays and other authorized SPAs. These are reporting subdivisions, not
new spending authority or inferred percentage compliance. Original class/account,
office/program names and labels do not choose a subdivision.

Partition each original SPA reporting-account share explicitly, preserving its
component key, account selection, signed amount and original source body. Reject
non-SPA shares, omitted/duplicate parts, opposite signs and synthetic zero pieces;
each original zero share has exactly one retained part. An unresolved part remains
visible and prevents complete subdivision amounts for that source column.

Require the whole entity/four source-column/six-subdivision coverage matrix with
explicit complete or missing declarations and basis. No omitted declaration becomes
zero. Missing original SPA coverage cannot become complete via this partition.
A zero SPA total may contain opposing real activity; preserve both signed shares.
Only a complete original column, all resolved parts and complete child coverage can
produce six known child amounts. Those amounts must reproduce the original SPA
control exactly. Current totals derive from known H1/H2 child amounts only.

The detached proposal retains the original account draft and complete partition/
coverage matrix without queries or ledger changes. It supplies no independent
Budget/Accounting review, code authority, legal spending authorization or issuance.
Retained workflow must subsequently pin the original account-review decision and
authority, check original source access/currentness, preserve successor history and
require independent Budget subdivision and Accounting actual-source review before
whole-package certification. Do not rewrite old account-review records or attach
new approval to an unreviewed detached draft. Existing proposal-before-Fund locks,
dedicated source permissions and UAT mutation denial remain required.

## Evidence inspected

### Next printable SPA integration boundary - 2026-10-12

Implementation now joins the exact retained source pair into combined PDF/whole
JSON exports. Eleven synthetic PDF pages and actual desktop/mobile download
controls were visually inspected; deterministic rendering and legacy flow-only
byte preservation passed the private reproduction audit. Thirteen-case output/
HTTP/source-rights regression passed on SQLite and native MySQL without skips.
Use the source contract/current handoff for exact scope/logs and outcomes;
these checks do not establish final Form 1 issuance.

The inspected `budget/form1_flow_output.py` already retains all itemized flow
columns, original account authority/decision and complete signed source-share index.
SPA integration must use the exact original account snapshot pinned by the retained
SPA version, rather than selecting a newer account version while rendering.
Compare complete source-draft bodies, original public identities, proposal/Fund
and owner scopes and account payload/decision checksums. Reproduce the pure SPA
partition and complete coverage matrix before deriving any printable child rows.

Keep original class controls separate from the six subdivision controls and their
reporting-account rows: they describe the same amounts and must never be added
together. Group explicit parts by original reporting selection while retaining
their signed amount, source column and original allocation/component identity;
opposing source activity survives a net-zero account/subdivision control. Unknown
child coverage remains unknown even when the original class control is known zero.
Retain all original source columns and derive current total only from known H1/H2.

Retain the whole original SPA payload and each distinct Budget/Accounting decision,
actor office, verification, authority/note and decision checksum in complete JSON.
Print the actual prepared/partial/approved/returned state without conferring a new
approval. Source-authorized historical downloads remain reproducible after a
successor; neither a historical approval nor printable derivative certifies current
sources. Original flow-only exports must keep their existing meaning and bytes.
Combined draft warnings may describe supplied SPA treatment but must retain the
stock, PhilHealth, shared-source allocation and final signing/issuance gates.

No new posting, source rewrites, model/migration or operator provisioning is needed
for this output boundary. Export authorization must check both the SPA package and
its original account/native/adopted sources, including authorized export-only UAT
readers. Tests must cover actual signed retained history and separate decisions,
prepared/missing/returned/superseded states, whole JSON/PDF source reproduction,
deterministic bytes, rehashed relationship/decision/derived-row tampering, source
revocation, no database queries in pure composition/rendering and unchanged journals.
Inspect every final rendered page and actual desktop/mobile download behavior.
This records the implementation contract; printable integration is not yet done.

The subsequent retained SPA service now implements version/decision/source-access
boundaries above with separate immutable Budget/Accounting decisions and pinned
original account approval/authority. The source contract/current handoff record
validation status; clerk delivery and final certification remain incomplete.

The retained DBM LBM 94 Annex D, PDF pages 20–22, has particulars/account code plus
five amount columns: past-year actual, current H1 actual, current H2 estimate,
current total and budget-year proposal. The current total is H1 plus H2 for period
receipts/expenditures. It separately presents net beginning cash, ending balance,
PhilHealth automatic-appropriation deduction and net ending balance. Preserve the
complete source/group hierarchy and the four certifiers/Chief Executive approval.
One separate form is required for each applicable economic enterprise/public utility;
this does not authorize new enterprise modules or infer the LGU's actual inventory.

The official PDF web fetch again failed because its 19,442,172-byte body exceeds
the fetch limit. The retained official bytes were hash-verified:
`14C63DAA682E695DDE09E0BA68A9E844D029959111A50028318ED23C8720AAAD`.
This audit uses those bytes/extracted instructions and does not claim all subsequent
amendments were checked. [Official reference](https://www.dbm.gov.ph/wp-content/uploads/Issuances/2026/Local-Budget-Memorandum/LOCAL-BUDGET-MEMORANDUM-NO.-94.pdf).

Executed `python .tmp/audit_form1_assembly.py` PASS, exit 0, over both isolated
retained browser rehearsal stores. Result `.tmp/form1-assembly-source-audit.json`.
The audit reproduces the approved forecast, accepted parent, both joint native
actuals projections and their source controls. Current synthetic scope has all
21 receipt leaves/five expense classes, H1 expenditure 100, H2 receipts 30 and
proposed receipts 100; the original two journals are unchanged. The downloaded
forecast JSON still equals the verified original snapshot. No operator DB writes,
source migration, new financial approval or runtime-code change occurred.

## Gaps demonstrated before assembly code

| Boundary | Authoritative evidence | Required handling |
|---|---|---|
| Historical leaf coverage | Existing `summary_actuals.normalize` accepts two explicit zero rows (service receipts/PS expenditure) while 20 receipt leaves/four expense classes are absent | Preserve those originals. Missing leaves stay unresolved; add separately reviewed complete coverage evidence or a genuine successor. Never backfill zero or silently reject historical viewing |
| Native account itemization | `summary_sources.project_native` emits category amount/basis/coverage, with no account fields; complete original native snapshot remains retained | Reproduce itemization from original reviewed source components. Category aggregates cannot be assigned a guessed revenue account or silently flattened |
| Official account codes | All four original account metadata rows in the synthetic forecast fixture have blank `government_account_code` | Explicit code treatment is required for printable itemized rows. Local/internal codes and account titles do not establish a prescribed government code; synthetic blanks are not evidence about the operator chart |
| Entity expenditure ownership | Form 2 schedule identifies office/fund/years but no reporting entity. A detached duplicate-entity probe repeats the exact same office identity | Do not sum one full office/Fund version into multiple entity forms. Require explicit whole-office assignment or independently reviewed source-row allocations; retain original amount caps and exact component identities |
| Entity actuals ownership | Native coverage reproduces a whole Fund cohort under the declared entity; declaration alone does not partition the Fund's financial sources | Compare exact original source component identities across the declared forms. Reject overlapping full-cohort use without retained reviewed allocation; different entity labels do not prove distinct money |
| Future beginning cash | Native and historical cash capture reject future dates; both are actual stock evidence | A budget-year opening estimate must retain an explicit forecast bridge from dated actual stock, not a fabricated future cash certification or opening journal |
| Stock current-total convention | Official column-total instruction does not separately explain semester stock treatment; existing cash contract warns against adding opening stocks | Retain dates, start/end boundary and an explicit stock-column reconciliation. Do not apply flow addition to cash stocks or invent the policy from the form heading |
| PhilHealth overlap | Cash restriction rows have explicit identities/references; receipt category/forecast amounts are separate. No combined deduction allocation exists | Retain a complete per-column source/overlap schedule and independently reviewed deduction authority before final net ending balance |

These probes establish missing assembly contracts, not corrupt approvals in the
existing narrower services. Historical adoption, actuals certification, office
issuance and forecast review keep their original semantics/history.

## Complete package to implement

### Itemized output source audit - 2026-10-12

Executed `python .tmp/audit_form1_itemization.py` PASS over the original downloaded
account-review package from the real isolated clerk rehearsal. The original draft
reproduces without default/Finance queries; 34 components and all 35 explicit shares
reproduce the 104 category/source-column controls. Original package bytes/evidence
remain unchanged. Result `.tmp/form1-itemization-source-audit.json`; execution log
`.tmp/form1-itemization-source-audit.log`. This is an audit, not production rendering.

Grouping the original shares by entity, receipt/expenditure leaf and exact selected
account identity yields two synthetic account rows: service receipts H2 30.00,
proposed 100.00/current total 30.00; MOOE H1 100.00, H2 40.00, proposed 1000.00/
current total 140.00. Original 0.60/0.40 parts are retained as two source shares,
not additional money. Other known category zeros remain separate coverage controls;
they are not fabricated account-free components. Synthetic code applicability is
unproven, including the fixture's single reporting target used across both kinds.

Before runtime rendering, preserve these output contracts:

- Keep every 21 receipt leaf/five expenditure class and all five amount columns.
  Receipt parent rows follow the retained Annex D hierarchy; compute each subtotal
  from its unique leaves, never by summing a parent and its children.
- Itemize each leaf by explicit reporting account identity with original share keys,
  signed amounts, original source accounts and reviewed selection evidence. Keep
  a net-zero account row if it contains real activity. Equal government codes do
  not justify silently merging different original account identities or titles.
- An absent account amount can display zero only when that original category/column
  has complete source coverage and the complete allocation proves no share for it.
  Missing category coverage stays unknown in both account rows and subtotals;
  current total is unknown if H1 or H2 is unknown. An original account-free explicit
  zero is distinct from either missing coverage or an unresolved monetary choice.
- Native actuals retain exact financial lines; adopted summary rows retain original
  declared account/no-account evidence. Office H2/proposed rows retain all original
  contributing centers/proposal lines and account objects. Actual amounts do not
  add the office comparison a second time.
- Annex D's expenditure section also names SPA subdivisions (development, disaster,
  debt service, enterprise subsidy, barangay aid and other authorized SPAs). Existing
  `spa` class totals alone do not establish these subdivisions. Retained expenditure
  components currently carry class/account/center and proposal evidence, without a
  separately reviewed SPA-subdivision allocation. Do not infer one from program
  labels, account titles, department names or the selected reporting code. Complete
  printable assembly needs explicit reviewed whole-source subdivision treatment,
  including coverage for genuine zero/missing subclasses.
- Flow-only drafts clearly identify missing stock, PhilHealth, shared-entity and
  signatory/issuance evidence. They must not render an invented beginning/ending
  balance or an unsigned official certificate. Final whole-package issuance remains
  the required destination; a diagnostic account schedule does not close FG-06.

The audit does not cover real signed corrections/net-zero activity, historical
missing account coverage, multi-entity allocations, official code applicability,
SPA subdivision treatment, stocks/PhilHealth or human acceptance. Those require
real retained fixtures and their corresponding gates during implementation.

One package version covers a proposal/Fund and the complete explicitly declared
entity inventory, with a separate output for each entity. The assembly includes
every entity exactly once and retains original labels, owning Accounting/Budget/
Treasury offices, fiscal year, coverage/designation authority and all source bodies.
The package retains the approved forecast group, every exact accepted reconciliation,
native or historical joint actuals per exact prior/H1 period, issued office rows,
cash stock sources/forecast bridges and PhilHealth coverage/overlap evidence.

Capture under BudgetVersion-before-Fund locks, matching existing forecast/source
version order. Lock the assembly identity before new versions and decisions, using
an unconditional proposal/Fund/version key on MySQL. Check source currentness and
expected latest at preparation and new approval/issuance. Retain prior versions
unchanged after a successor, ordinary posting or mapping change. Fund locks do not
freeze all ledger posting: record the coherent observed cohort and recheck freshness.
Exports check every current source read/export capability independently; a checksum
proves integrity, not authority. UAT denies mutations even with operational grants.

The subsequent `budget/form1_assembly.py` draft joins the exact complete original
account/SPA flow to the stock/PhilHealth flow before any whole-package retention.
It preserves all original entity scopes, receipt categories/account shares and
hierarchy, expenditure classes/account shares, SPA subdivisions, stocks and five
financial columns. Calculation coverage is separate from independent approval,
certification, source freshness, cash authority and issuance. Current selection
uses the original services; retained reads/exports check their original models,
decisions, attachments, policy and cash worksheets without replacing successors.
See CONTINUE.md for actual assembly validation. This calculation service supplies
no persistent version or review; retained preparation is described below.

Before adding independent package decisions, reconcile the existing source access
paths explicitly: stock reproduction uses the Budget-owned forecast snapshot,
while account/SPA reads permit their original Budget/Accounting owner scopes.
Do not pretend an Accounting/Treasury whole-package role already grants all these
source capabilities. Provide narrowly scoped original-package access where
authorized, with independent read/export checks; never grant general Budget editing
or bypass source visibility using a detached envelope. New version/decision capture
must hold the existing proposal-before-Fund locks through source checks and writes;
the ephemeral draft's current selection is not such a persisted review transaction.

The subsequent retained preparation uses `Form1Package` plus immutable binary
`Form1PackageAttachment` rows. Bind the exact original SPA/account/forecast models,
whole assembly and metadata manifest to a proposal/Fund/version; reserve versions
under proposal-before-Fund locks through source checks and writes. No decision or
issuance state is implied. Package-only read/export requires dedicated original
office scope and explicit original planning/account/SPA permissions. Original
actuals and cash source authorities remain separately enforced. Treasury permission
to inspect this retained package does not open generic SPA or Budget editing.
Source histories and copied cash/PhilHealth bytes remain fixed across successors.
Affected/dependent SQLite and native MySQL validation passed, including minimal
preparer permissions, three-office read/export/UAT boundaries and two native
version/successor races. See CONTINUE.md for exact scope and retained logs.

The detached calculation must reproduce all leaf components and source controls
without database reads. Parent subtotals are derived only from unique leaves; never
add itemized leaves and their category totals together. Receipt and expense current
totals add exact H1/H2 flows; signed actual corrections retain their original lineage.
H2/proposed expenditures reuse exact issued office rows after entity allocation;
actual columns reuse certified evidence with accepted office reconciliation, rather
than summing both alternative actuals authorities. A zero leaf requires explicit
coverage; no missing row, missing account or missing source becomes zero.

Stock rows retain explicit source dates/boundaries and gross/restricted/net controls.
Historical adopted stock and jointly certified native stock are alternate routes,
not additive sources. Forecast bridges retain the actual anchor, dated estimates,
separate source changes/restrictions and an explained reconciliation to their
proposed opening. They must not force budgetary expenditure and cash movements to
match by posting an invented journal. Do not infer restrictions from OBR/ARO/earmark
balances; the local earmark-before-ARO rule remains unknown.

#### Next stock implementation source audit - 2026-10-12

The first server source adapter is now implemented in
`budget/form1_stock_sources.py`: exact-scope current selection and original-source
visibility/export checks reuse the services below and retain whole snapshots and
gross/restriction/net controls. Four own SQLite tests and six native cases
(including two dependent joint-cash cases) passed without skips; exact outcomes/
logs are in the handoff.
This adapter does not assemble stock columns, create a new review package, connect
UI/output delivery or establish Form 1 completion. The subsequent bridge draft
below supplies explicit forecast arithmetic, with governed retention/review open.

`budget/form1_cash_forecasts.py` now proposes an ephemeral, unreviewed bridge over
an exact current actual anchor selected through the server stock adapter. It reads
and returns the original PDF/PNG/JPEG worksheet bytes separately for later governed
retention. Every positive cash in/out and restriction add/remove has its own unique
worksheet row, effective date and reconciliation basis. New restrictions retain
distinct identities, references, purpose and coverage; original restriction leaves
remain unchanged. Movements fall after the anchor and within the target start/end
boundary. Restriction positions reconcile chronologically at each day end: a later
addition cannot finance an earlier removal. Same-day changes reconcile as a daily
net, without claiming an intra-day sequence or capacity.

Cash and restriction coverage are separate. Empty complete cash schedules and zero
target restrictions require their own explicit declarations; missing coverage gives
unknown projected controls, while diagnostic arithmetic remains separate. Neither
budgetary income/expenditure totals nor an unchanged actual balance supply a cash
timing forecast. The full original source snapshot, original worksheet hash, every
movement and target scope reproduce the result. Original source read/export rights
are checked again on reproduction, without replacing historical source evidence
when a newer source is prepared. Checksums establish arithmetic consistency, not
authorship or independent approval of an editable ephemeral draft. No new persisted
forecast, model, migration, review, cash availability, posting or issuance is supplied.
Whole Form 1 stock columns, planning-source reconciliation, governed retained
versions/independent decisions, PhilHealth and clerk/output delivery remain required.

The subsequent `budget/form1_stocks.py` connects opening boundaries to the complete
original flow inventory. It requires the explicit draft convention
`annual_boundary_reference` and its reconciliation basis; it does not infer an
issued stock convention from the form's H1-plus-H2 flow instruction. Actual prior
and H1 openings use January 1/start-of-day of their exact years. H2 uses July 1/
start-of-day and may select actual evidence or an explicit bridge estimate. The
proposed January opening requires an explicit forecast. Missing openings retain
their missing-evidence basis and unknown controls. The annual/current opening
references the exact H1 January source, never a second independently chosen source
or the sum of January/July stocks. Independent whole-form review and actual office
acceptance must still settle the issued presentation/convention.

Every selection matches the original flow's three offices, Fund and entity.
Capture checks current original stock anchors and actual worksheet bytes; retained
reproduction checks original approved forecast/flow and current source read/export
authority without replacing successors. Detached verification uses no queries and
compares original stock snapshots, restriction identities and arithmetic. Both
direct and forecast native anchors/targets reject whole-Fund cross-entity reuse
without reviewed allocation. Missing flow or stock controls remain unknown.
The draft resource ending for each column is its selected net opening plus original
period receipts less original expenditures. That budgetary arithmetic never claims
to be a certified actual closing cash balance or forces accrual/period flows to be
cash movements. PhilHealth/net-ending treatment remains explicitly incomplete.
No persisted stock review, role, model, migration, cash capacity, approval or form
issuance is added. Complete package retention, cash-timing/planning links, PhilHealth
overlap, four certifiers/Chief Executive, clerk delivery and office acceptance remain
required. Actual validation is recorded in the source contract/handoff.

Current source inspection confirms two existing authorities to reuse rather than
duplicate: `accounting/budget_cash.py` retains historical gross/restricted/net
controls, signed-document bytes and independent adoption; native
`budget_cash_preparations.py` pins reviewed cash mapping/opening/ledger evidence and
an optional adopted restriction source. `budget_cash_certifications.snapshot`
retains two distinct Accountant/Treasurer decisions over that exact native cohort.
Only a jointly certified native source with restriction evidence can supply a
known net actual stock. Preparation alone supplies neither certification nor zero
restrictions. Both routes forbid future actual dates.

The first assembly adapter must retain the whole original alternative snapshot,
matching Accounting/Budget/Treasury owners, Fund, entity and exact date/boundary.
Use original public identities/version/checksums and original decisions; verify
attachment bytes and source access through the existing services before detached
calculation. Native whole-Fund reuse across multiple entities requires separately
reviewed allocation; different entity labels cannot partition the same ledger.
Historical and native sources for one stock cell are alternatives, never additive.
Reusing an identical stock for an annual and semester display is a linked display
of the same boundary, not another financial amount to add.

The stock column reconciliation must explicitly identify the annual opening and
closing boundaries alongside each semester opening/closing. The annual/current
opening is not the sum of two semester openings. Keep any unknown boundary or
missing restriction coverage unknown. Do not infer an unexplained stock-column
convention from the flow-column addition instruction. An exact end-of-day source
cannot silently become a different start-of-day source; retain any evidenced
boundary reconciliation explicitly.

Future beginning/ending estimates need a separate proposal over a dated adopted
or jointly certified actual anchor. Retain each estimated cash receipt,
disbursement and other explained cash change with an explicit effective date,
scope, amount, source identity and basis, plus whole estimated cash coverage.
Reproduce projected gross from that anchor and these cash movements. Budgetary
expense/receipt forecasts do not automatically prove cash timing; retain their
original links and a separate timing/reconciliation schedule rather than relabel
them or post an invented journal. Restriction forecasts retain original restricted
identities and explicit additions/removals/overlap evidence; missing future
restrictions are not zero. Any later adopted actual must be a new selected source,
not an edit of the earlier forecast or its approvals.

Read, export and mutation remain separate. A combined source package must check
native cash export authority and original restriction-document export authority
where those originals are carried, alongside the existing Form 1 source rights.
The native cash export view already distinguishes snapshot exports from packages
carrying historical documents; reuse those boundaries instead of granting access
from the outer Form 1 role. UAT mutation denial, historical viewing, new-source
freshness checks and original output bytes remain mandatory.

Before adding persistence/UI, reproduce genuine adopted and jointly certified
sources through the adapter, then test wrong owners/Fund/entity/date/boundary,
pending/returned decisions, missing restrictions, whole-Fund duplicate use,
rehashed controls and source-right revocation. Next validate the explicit forecast
bridge and annual/semester reconciliation with retained cash movements and changed
source cohorts. These are implementation requirements, not completed validation;
the completed delivery regression establishes the preceding draft checkpoint only.

Retained browser candidate inspection also confirms that source identity must be
resolved in its actual store, not inferred from exported numeric IDs or labels.
Historical cash `2eb3e9db-da83-4232-9952-7f7ee4cb6928` is an adopted
2026-01-01/start-of-day source in its original office-form rehearsal. Native cash
`a88969a4-b16b-4b5b-94ca-42bb1eeacc3d` is jointly certified at
2026-09-04/end-of-day in a different rehearsal with different owning offices.
Both show Fund ID 1 and entity `general`; those facts do not establish a common
authorized assembly scope or interchangeable dates. This was read-only artifact
inspection, not live-source adoption or an implemented assembly adapter.

Executed original-service audits subsequently PASS/exit 0 for both retained
candidates: `python .tmp/audit_stock_service_sources.py historical` and the same
command with `native`. Each uses its existing isolated rehearsal store, verifies
the original model/document/source evidence through its existing service and
reproduces the entire original downloaded snapshot. Historical gross 2,000.00 less
1,001.00 restricted reproduces 999.00 net; native gross 1,000.00 less 10.01
restricted reproduces 989.99 net with both retained office decisions. Both retain
their original preparation payload and one unchanged journal. Results:
`.tmp/stock-historical-service-audit.log` and `.tmp/stock-native-service-audit.log`.
No source selection, new approval, currentness certification, operator mutation or
Form 1 assembly is supplied by these read-only checks.

PhilHealth coverage must identify original receipt/forecast components, selected
amounts and the exact restriction components already excluded from beginning cash.
Cross-column links distinguish carryover stocks from period receipts. Explicit
splits account for overlap once with complete source caps and basis; differing
labels do not avoid duplicate detection. An applicable evidenced zero deduction
is distinct from absent policy/evidence. The computation retains ending balance,
separate original deduction and reproduced net ending balance; spending capacity
is never derived from the form.
The subsequent `budget/form1_philhealth.py` draft implements signed original-source
partitions, separate SHF/counterpart/carryover treatment and shared overlap-claim
caps over the complete stock/flow inventory. Claims remain pending; no approved
offset, new posting or cash authority is inferred. Independent whole-package
retention/review and clerk/issued output remain required. See CONTINUE.md for actual
validation results and the audit below for policy scope.

The [2026-10-12 PhilHealth source audit](FINANCE_FORM1_PHILHEALTH_SOURCE_AUDIT.md)
visually verifies the official SHF funding/counterpart/Trust Fund distinctions and
reproduces the actual retained source-authorized rehearsal. Its four covered zero
receipt controls do not supply reviewed deduction/overlap authority. Reuse exact
receipt, stock and expense component identities; do not infer an adjustment recipe
from labels or silently net health expenses against period PhilHealth receipts.

Preparation/review, named original actuals/cash decisions, final four signatory
evidence and Chief Executive approval/issuance remain distinct. Retain designation,
actual signer identity, date, reference and original signed-document bytes where
required. Do not convert source approval into physical signature, fabricate signer
names or describe an unsigned draft as issued. Final issued outputs retain original
bytes/checksums, source cohort, approval history and full verified exports.

## Implementation and verification order

The itemized calculation is now implemented separately in
`budget/form1_itemization.py`, over the verified original reporting-account draft.
It retains account/source-share evidence and all original leaves, derives receipt
hierarchy totals from unique leaves and keeps the five-column unknown/zero boundary.
Real clerk-source projection matches the audited 34/35/104 inputs without queries.
Affected/dependent SQLite/native 12-case runs and the late genuine signed-history
case pass on both stores (actual scope/logs in the current handoff);
printable/issued output and the complete package remain open.

The first local implementation is `budget/form1_flows.py`: server capture pins the
latest approved forecast and its exact accepted reconciliations under proposal/
Fund locks, rechecks source currentness and retains the full original envelopes.
Detached composition reproduces all 21 receipt leaves/five expenditure classes and
the five period-flow columns without queries. Missing historical leaves remain null;
the relevant totals and current total remain unknown instead of inventing zero.
Explicit reported source controls remain visible separately. Future stock, official
account itemization, PhilHealth deductions and issuance remain explicitly incomplete.
The composer rejects two entity designations for one whole native Fund/period cohort,
reused historical source rows and repeated whole office/Fund assignments. It does not
implement reviewed shared-source row allocations yet. Seven flow tests include two
genuine approved native entity scopes, query-free reproduction, permissions/staleness,
unknown coverage, mixed native/historical whole-Fund overlap in both source orders
and rehashed derived-control tampering. Office estimate/proposed rows reproduce the
original frozen context during detached verification as well as live capture.
Validation is recorded in
the [source contract](FINANCE_FORM1_SOURCE_CONTRACT.md), not inferred from this design.
`budget/form1_components.py` now retains original native/historical/forecast/office
components and checks every known leaf amount against the flow composition.
It keeps original cash accounts separate from still-unmapped reporting accounts,
retains signed amounts and preserves unknown historical categories. No independent
reporting-account mapping/review is implemented by this inventory.
`budget/form1_account_proposals.py` separately supplies pure draft partitions over
that verified inventory. All components require explicit mapped or unresolved
shares totaling their original signed amount. Selections retain full original
captured account metadata and cannot substitute a local code for a government code.
Actual selections permit retired accounts valid on their source date; forecast
selections require captured active/posting status. Native dates are exact; undated
historical/forecast/office rows require the whole original interval. A partial-date
reclassification needs additional dated source evidence, not a guessed date.
Configured codes are not proof of official applicability. Independent Accounting
review, code-authority approval, retained persistence and access rules stay separate;
the draft never grants Accounting general Budget mutation or rewrites journals.
The subsequent `Form1AccountReview` service retains the draft plus exact authority
attachment and independently designated Accounting decision. Access/freshness and
version boundaries and local SQLite/native/race validation are described in the
source contract/current handoff. Guided account intake, independent review, complete
scoped history and original attachment/full JSON exports are now connected locally.
They preserve every source while paging/searching; source coverage and issued forms
remain separate. See the 2026-10-12 clerk checkpoint in the source contract.

1. Implement complete flow composition and source-identity/itemization controls,
   including historical missing coverage and cross-entity office/actuals collisions.
2. Connect explicit stock selection/forecast bridge and PhilHealth overlap schedule,
   then reproduce all Form 1 rows/columns and cross-controls detached from the DB.
3. Retain whole package preparations, separate independent reviews/signatory evidence
   and governed issuance under the existing role/version/currentness boundaries.
4. Connect guided clerks, truthful paginated retrieval, immutable complete exports
   and printable drafts/issued forms; exercise realistic source reuse and corrections.
5. Run affected/dependent SQLite and native MySQL, named source/version/decision races,
   broad cross-module milestone regression, desktop/mobile/browser downloads and
   physical/local form acceptance. Record unperformed external gates separately.

Tests must include multiple real entity sources, same source used twice, partial
source allocation, absent historical leaves, signed exact corrections, net-zero
activity, explicit zero coverage, missing/changed code mappings, future-stock route
misuse, stock-vs-flow total errors, duplicate PhilHealth deductions, stale successors,
permission/export revocation, UAT mutation denial and immutable issued bytes.
The existing one-entity rehearsal and detached collision probe do not prove those
multi-entity flows or operational acceptance. No new unit/native/browser suite was
required for this read-only audit; runtime behavior was not changed. Full release,
operator migration/provisioning, physical signing and LGU acceptance NOT RUN -
OUT OF SCOPE. FG-06 and production remain open.
