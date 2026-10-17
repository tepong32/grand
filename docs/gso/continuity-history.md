# Historical GSO continuation checkpoints

Preserved on 2026-10-17 from the former long handoff. These sections record
historical checkouts, intermediate validation and then-current plans. They are
not the current development state. Use [CONTINUE](../CONTINUE.md), the
[roadmap](inventory-roadmap.md) and [validation](validation-2026-10-16.md) for
current direction and exact evidence. Old pending/next-work wording is historical.

## Disposal lock order — published577c549

Previous turn: progress. Actual VM published9fc6acc/v0.21.0; branchCI38982546339
and masterCI38982680948 PASS. Remote master/tag verified, canonical clean0/0,
operator database unchanged. Fresh sync this turn: GSO9fc6acc clean0/0; Finance
a533482 candidate unchanged except the GSO coordination note, master32ab046.
New branch `codex/disposal-lock-order`.

Tracing SPC movement sources found joined disposal case/asset locking with no
explicit asset-first order, unlike handoffs/maintenance. Review/resubmission now
lock asset then case separately and reject a changed relation; all disposal write
paths recheck scope on fresh locked data. Completion reuses the locked asset.
No schema, role, Finance, file namespace or UI changes. Source map and remaining
SPC facts are in property-record-design; do not infer stock effects from custody.

Focused6 (3 run/3 native skips) PASS0.036s; full shell137 (116 run/21 native skips)
PASS46.387s. Full standalone native137/137 PASS132.057s, exit0; actual
GRAND native134/134 PASS54.937s, exit0, against candidate a533482. The isolated9fc6acc baseline probe reproduced
stale-owner review acceptance (PermissionDenied not raised); current tests pass.
New native tests hold the asset, wait for a competing disposal lock attempt, then
assert its case remains NOWAIT-lockable; review/resubmission and duplicate
completion are covered. Fresh native owner denial has an integration test.
All disposable schemas removed; owned MySQL33317 normal shutdown confirmed.
Actual VM release published577c549; branchCI38983516424/masterCI38983686513 PASS.

Next source prerequisite: disposal attachments have no retained hash, and upload
validation currently lives in forms, not the save service. Add explicit historical
unknown handling and verified-source checks before card support consumes them.
Movement annotations/openings, SPC output, physical cost allocation and operational
acceptance remain unfinished. Overall goal remains active.

## Supplied acquisition facts — published9fc6acc

Previous turn: progress. Working register9acd9b9 was actually VM-published as
v0.20.0; branchCI38981511749 and masterCI38981661383 PASS. Fresh fetch this turn:
GSO clean0/0 at9acd9b9; Finance candidate a533482 unchanged except the preserved
GSO note, origin/master32ab046. New branch `codex/property-acquisition-facts`.

Inventory0025 extends the existing reviewed property record with supplied
acquisition date/reference/receipt-item number, without inventing a new registry,
numbering series or acquisition/Accounting authority. Missing facts remain unknown.
Historical blank fields keep old snapshot representations and checksums unchanged.
New source facts enter immutable history/replay checks; successor verification
requires fresh Finance association review. See property-record-design for limits.

Focused11/11 PASS0.593s; populated migration2/2 PASS1.590s; full SQLite131
(113 run/18 native skips) PASS45.630s; full standalone native131/131 PASS137.186s.
Final affected11/11 PASS0.720s after clarifying register purchase-date wording.
Actual GRAND candidate a533482 full native133/133 PASS55.510s, exit0;
`.tmp/property-acquisition-grand.log`. All disposable schemas removed; owned
MySQL33317 shut down normally.
Populated copied migration preserves prior rows and all Finance bytes, including
valid old property/link history. Native post-migrate adds27 help guides/198 steps
for synthetic departments; existing rows are unchanged. This native effect was
investigated after the initial broad all-row-equality assertion failed.

Browser separate recorder/checker entered and verified the new source facts;
desktop/mobile reviewed,390px no overflow. Preview/browser stopped. Stopped paired
recovery217 default/83 Finance tables/7 packets PASS, retaining new facts and old
unknowns, detecting item-number tampering and stale old association. Backup:
`C:/Users/Administrator/.codex/backups/gsov2-property-acquisition-recovery-20261017-hr44lsyg`.
Actual VM publication completed at9fc6acc; branchCI38982546339 and primary
CI38982680948 PASS. Remote master/tag verified; canonical clean0/0, operator DB unchanged.
Official SPC/movement numbering/openings/cost allocation/operational acceptance
remain unfinished; the overall goal stays active.

## Property working register — published9acd9b9

Previous goal turn: progress. Actual VM published6c1ba3e/v0.19.0, branch
CI38980459629 and masterCI38980624675 PASS; remote master/tag verified. Fresh
fetch this turn: canonical GSO clean0/0 at6c1ba3e; Finance candidate a533482
unchanged apart from the preserved GSO coordination note. New feature branch:
`codex/property-working-register` in the existing isolated GSO worktree.

Read-only working register now shows scoped assets, latest verified supplied
class/fund/treatment, useful life, register cost and current custody. Unknown and
stale documents stay visible; pending successors do not change verified filters.
No schema/mutation/Finance-query/role changes. This is preparation for the SPC,
not its historical quantity ledger or official output. See property-record-design.
Focused shell9/9 PASS0.559s; full shell128 (110 run/18 native skips) PASS45.688s.
Full actual-GRAND SQLite132 (111 run/21 native skips) PASS32.415s; focused
native MySQL3/3 PASS1.760s, both exit0, candidate a533482. Final label refinement
uses register cost rather than claiming original legacy cost; focused9/9 PASS0.566s.
Browser desktop/mobile and filters inspected before that wording-only refinement.
Disposable schemas removed, owned MySQL shut down normally, preview/browser closed.
Actual VM publication completed at9acd9b9; branchCI38981511749 and primary
CI38981661383 PASS. Remote master/tag verified; canonical clean0/0, operator DB unchanged.
Official class/fund SPC, physical cost allocation and operational acceptance remain.

## Property Finance links — published6c1ba3e

Previous turn: progress (design published e9b3c74; branch CI38978070046 and primary
CI38978241661 PASS). Fresh fetch: GSO clean0/0 at e9b3c74; Finance a533482 candidate,
origin/master32ab046, only preserved GSO note untracked. Branch
`codex/property-finance-links` implements adapter0005 PropertyFinanceLink/Event,
explicit GSO sharing, owner-scoped native dimension proposal, independent review,
withdrawal/replacement, signed forms, history, scoped downloads and navigation.
No Finance writes, auto-grants, operator migrations or deployment.

Initial actual-GRAND SQLite service tests7/7 PASS0.688s; shell property tests7/7
PASS0.414s. Initial native12 FAIL with one fixture error (new asset integer cost
versus reloaded Decimal) and one HTTP test still using pre-prefix form names;
fixture refreshed and test payload aligned. Full shell126 (108 run/18 native
skips) PASS46.216s. Full native GRAND, including journal support, populated
migration replay and3 concurrency tests, PASS130/130 in70.080s, exit0:
`.tmp/property-links-grand-full.log`.
Final focused native15/15 PASS14.809s, exit0, adds the governed setup-edit race
(`.tmp/property-links-native-final.log`). Both runs use unique disposable schemas.
The added test changes no application behavior.
Two setup-race assertions were subsequently strengthened to wait for an actual
blocked UPDATE execution window; targeted2/2 PASS2.984s, exit0,
`.tmp/property-links-setup-locks-final.log`. Application code is unchanged.

Browser completed separate GSO requester/Finance proposer/reviewer flow; desktop
and390px mobile inspected, no horizontal overflow or duplicate IDs on approved
page. Fixed duplicate form IDs while proposal and decision forms coexist; office
picker now includes native codes. Preview/browser stopped. Synthetic stopped
recovery retains an approved replacement and withdrawn predecessor,217 default/
83 Finance tables/6 packets; source rows/files unchanged and missing dimension,
link tampering and stale decision detected. Backup:
`C:/Users/Administrator/.codex/backups/gsov2-property-link-recovery-20261017-4_u2xo4w`.

Actual VM publication completed at6c1ba3e; branchCI38980459629 and primary
CI38980624675 PASS. Master/tag verified; canonical clean0/0, operator DB unchanged.
All disposable test schemas were removed; owned MySQL33317 shut down normally.
Official class/fund SPC output and physical cost allocation remain unfinished.

## Property Finance request design — reference checkpoint

Previous goal turn: progress. Supplied property workflow9070496 was VM-published;
branch CI38977539972 and primary CI38977725084 PASS. Remote master/tag verified,
canonical clean0/0, operator SQLite hash unchanged. This turn fetched again:
GSO9070496 clean0/0; Finance candidate a533482 clean except the preserved GSO note,
remote Finance master32ab046. No active Finance work was changed.

Selected [native property-link design](property-finance-links.md) after
checking actual owner/access/models/setup mutation code. The old design omitted
how Finance obtains scoped access to GSO-owned evidence. Use an explicit GSO
request to a selected native department, then Finance proposal and independent
association review; no global property access from a ledger grant. Department
has no public UUID, so installation merges need explicit ID remapping.

Next implement the adapter request/model/services/UI and native tests described
there. Direct dimension and journal-backed paths require different source-lock
prefixes; do not acquire voucher cases after receipt/asset locks. This checkpoint
is design/documentation only, not an implemented Finance link or official SPC.

## Supplied property determinations — published9070496

Branch `codex/property-determination-workflow` started from08b777b after clean0/0
fetch. Prior design publication branchCI38975367167/primaryCI38975483442 PASS.
Finance initially32ab046 fetched0/0 with104 modified/untracked paths preserved.
Its parallel release candidate is now a533482; origin/master remains32ab046 at
this check. Only coordination notes are appended to its active checkout.

Inventory0024 adds PropertyDetermination/Event: supplied PPE/semi-expendable treatment,
source authority/date, class/fund labels, optional exact useful life/start/expiry,
private packet, independent verification, rejection/cancellation and retained
verified predecessors. Core services never change asset/custody/Finance. Lock
receipt (if linked) before asset before case. Signed entry identities, exact replay,
current-version decisions and a unique virtual pending marker prevent duplicates.
See [design and implementation](property-record-design.md).

Initial full SQLite126 (108 run/18 native skips) PASS39.469s; native126/126
PASS124.260s; actual GRAND116/116 PASS43.659s. Then tightened the model's internal
save guard and refined rendered labels; focused9 (8 run/1 skip) PASS1.073s.
Final SQLite126 (108 run/18 native skips) PASS41.953s; native126/126 PASS124.516s;
actual GRAND32ab046116/116 PASS42.772s. Final logs use the `-final` suffix.
Finance candidate a533482 also passes116/116 in40.854s (exit0), tested separately
in clean detached `gsov2-grand-v173-validation`; log `.tmp/property-grand-v173-native.log`.
VM publication completed at9070496; branch CI38977539972 and primary
CI38977725084 PASS. Remote master and tag v0.18.0 were verified at that commit.

Populated copied migration preserves prior inventory/claim/mapping/return rows and
Finance bytes. Browser separate recorder/reviewer verified five years with unknown
expiry; desktop/mobile inspected,390px client/scroll. Preview/browser stopped.
Stopped paired recovery215 default/83 finance tables/6 files PASS; retained history,
asset/custody and all prior rows preserved; stale verification denied, altered
useful life/missing packet detected. Backup:
`C:/Users/Administrator/.codex/backups/gsov2-property-recovery-20261017-onipyxpj`.
No operator migration/grant/deployment or official-form/Accounting approval.
Native Finance dimension association, class/fund SPC and physical cost allocation
remain next work; the overall goal remains active and incomplete.

## Property-record design selected — reference checkpoint

Fresh fetch: GSO25004cc clean,0/0 against remote master. Prior VM publication is
complete: branchCI38974856868 and primaryCI38975011553 PASS; remote master/tag
verified. Finance32ab046 is0/0 with103 modified/untracked paths preserved.

[The selected design](property-record-design.md) maps actual asset, custody,
receipt and native Finance dimensions to the next workflow. Re-inspected retained
COA2024-006 PDF pages2,3,7,8 and ONAR metadata. SPC is a class/fund property record;
do not substitute one asset's audit history or duplicate Accounting's SPLC.
Next implement supplied property determination/useful-life evidence with independent
documentary verification, then separately authorized native Finance dimension links
and class/fund output. No schema/code change or official form acceptance is claimed
by this design checkpoint. Physical cost-component allocation remains separate.

## Receipt-origin asset edit protection — published

Fresh fetch: canonical master clean and synchronized at4a81990 (prior publication
CI38973934215 PASS). Branch `codex/received-asset-source-protection` protects
materialized unit cost, quantity, supplier and PO from ordinary asset edits.
Source inspection found the ordinary edit path could bypass the documented cost
amendment boundary. The service rechecks the receipt link under the existing asset
lock; the form disables these fields. Identical values, descriptions and tags remain
editable; unlinked legacy records retain existing behavior. No migration/backfill,
Finance write or automatic repair of historical divergence.

Focused receiving21/21 PASS; shell117 discovered/100 executed/17 native skips
PASS34.412s; system and migration drift checks PASS. Native shell117/117
PASS109.011s; actual GRAND114/114 PASS38.756s, both exit0. Disposable schemas
removed and owned33317 shutdown requested normally. Remote CI gates publication.
See validation for exact commands and initial test-fixture corrections.

The property assessment confirms inventory_class is a reporting group, not a
reviewed PPE/semi-expendable treatment. Asset lacks useful-life/expiration facts;
free-text fund/account fields are not authoritative Finance dimension links.
Do not derive treatment from cost alone or duplicate Accounting's SPLC. Next:
complete the physical property-record design using the retained COA2024-006 annex
and current Finance ownership, alongside the unresolved receipt allocation gap.
Finance's latest handoff records an executed existing filtered JEV working output,
not new official form acceptance; its unpublished application files remain intact.

## Original-issue supply returns — published

Feature e78c404 is integrated/pushed. BranchCI38973327525 and primaryCI38973485610
PASS; remote master/tag verified ate78c4043386c322bbaef023e46cb1d1f19046a26.
The documentation follow-up corrects the cited presentation's slide range and
records publication; application code and native validation below are unchanged.

Branch `codex/supply-return-lineage` started from2ae5a9e after fresh clean0/0 sync.
Prior requisition milestone2ae5a9e is published; branchCI38972044163 and
primaryCI38972168264 PASS, remote master/tag verified. Finance32ab046 fetched0/0
with96 dirty/untracked files preserved; only the authorized coordination note
was appended there.

Migration0023 adds default SupplyReturn/Event records. Original issue/optional
documented FIFO allocation, condition, quantity, source snapshot and private
evidence now support independent stock acceptance, decline and cancellation.
Acceptance locks item before case, rechecks issue/allocation capacity and creates
a return movement/new FIFO lot atomically with history. Unknown cost stays NULL;
original issue/allocations and requisition fulfillment remain intact. Unlinked
legacy returns require reconciliation. See [workflow](supply-returns.md).

Shell116 discovered/99 executed/17 skips PASS32.523s; native shell116/116
PASS109.832s; actual GRAND114/114 PASS39.941s. Check/drift/diff pass. Populated
upgrade preserves existing operational rows and Finance bytes. Browser recorder
and separate reviewer accept1 unit, stock7 becomes8 at retained cost30; desktop/
mobile inspected,390px page/scroll, no duplicate IDs. Preview8030/browser stopped.
Stopped paired recovery213 default/83 finance tables and5 files PASS; original
issue/requisition retained, stale replay denied, changed return lot/missing source
detected. Backup `.codex/backups/gsov2-supply-return-recovery-20261017-kpt5jkgy`.
Native schemas removed, owned33317 shut down normally; operator DB unchanged.

Next: assess physical receipt cost-component allocation and semi-expendable
property-record gaps against current Finance sources and verified COA annexes.
Official outputs, legacy reconciliation, loss cases and operational acceptance
remain gaps in the full goal. Do not declare the overall system complete or
production-ready. No operator migration/grant/deployment occurred. Release identity
is in VERSION/CHANGELOG/history; remote CI gates primary integration.

## Supplied requisitions and partial issues — validated checkpoint

Branch `codex/supplies-requisition-workflow` started from58f7cfa after fresh clean0/0
fetch. Prior retry milestone58f7cfa is published; branchCI38970761831 and
primaryCI38970881508 PASS, remote master/tag verified. Finance32ab046 fetched0/0
with96 dirty/untracked files preserved; its latest clerk wording follow-up is
acknowledged. Only the authorized GSO coordination note was appended there.

Migration0022 adds four default-store requisition/line/fulfillment/event tables.
Private supplied document, immutable requested quantities, independent document
review, exact partial issues, unavailable observations and reasoned remainder
closure now have services and screens. Sorted item locks precede the case; stale
versions cannot repeat issues, FIFO/history commit atomically, and no Finance
posting or reservation is inferred. See [design](stock-request-design.md).

Shell109 discovered/93 executed/16 skips PASS28.161s; native shell109/109
PASS100.492s; actual GRAND112/112 PASS38.137s. Check/drift/diff pass. Populated
upgrade preserves existing inventory/claim/mapping rows and Finance bytes.
Browser entry, separate document reviewer and partial issue PASS; desktop/mobile
inspected,390px client/scroll widths, no duplicate IDs. Preview8030/browser stopped.
Stopped paired recovery211 default/83 finance tables and4 private files PASS,
preserving request/issue/FIFO/history and detecting tampered request/missing source.
Backup `.codex/backups/gsov2-requisition-recovery-20261017-2xmbbwth`.
Native schemas removed, owned33317 shut down; operator DB hash unchanged.

Next: explicit original-issue supply returns with reviewed quantities and retained
cost/quantity lineage. Official forms/current local applicability, Accounting
valuation and physical receipt cost allocation remain gaps. Cross-installation
data import is not implemented; preserve original audit snapshots when designing
reviewed identity mappings. No operator migration, role grant or deployment.
Release identity is retained in VERSION/CHANGELOG/history; remote CI gates primary
integration. Overall goal remains active and incomplete.

## Stock movement retry safety — validated checkpoint

Developed on `codex/stock-issue-retry-safety` from830a1ec after fresh fetch0/0.
Receipt, issue and adjustment forms now carry signed actor/item/operation request
identities. Exact retries return the retained movement under the item lock;
changed content fails without duplicate quantities or FIFO allocations. Current
permissions still apply. Existing movement UUIDs are reused; no schema changes.
Fresh forms remain distinct operations. See [supplies design](stock-request-design.md).

Standalone SQLite104 discovered/89 executed/15 native skips PASS24.350s; native
standalone104/104 PASS89.120s; actual GRAND110/110 PASS40.463s. Check and migration
drift pass. Browser issue and mobile390px checks pass. Stopped paired recovery
207 default/83 finance tables and3 files preserves retry/FIFO identities without
additional rows; backup `.codex/backups/gsov2-stock-retry-recovery-20261017-ae0mofvh`.
Both native schemas removed and owned33317 shut down normally; preview stopped.
Operator database hash remains unchanged. Full evidence is in the validation log.

Finance32ab046 fetched0/0 with88 dirty/untracked files preserved. Its handoff now
reports both full regressions passing; only the GSO coordination note was appended.
Next: supplied approved requisitions, partial fulfillment and original-issue return
lineage, following the documented design and actual GRAND authorities. This fix
does not implement that workflow. Current municipal form applicability remains
unverified; the COA source matrix records the indexed2021 GAM deferment and limits.
No operator migration, grant, deployment or official-form acceptance occurred.
Release identity is retained in VERSION, CHANGELOG and Git history; remote CI is
verified before integration under the repository release workflow.

## HR-reference custody review — published

Branch `codex/hr-custody-review` based on676bc29 after fresh fetch clean0/0.
Previous documentation release676bc29/v0.14.1 is published; branchCI38966229245
and primaryCI38966414324 PASS. HR feature204df28/v0.15.0 is now integrated/pushed
after branchCI38969039410 PASS. Remote master/tag match204df2842f76ef141ad5e3a83646672e1faee4cd.
Actual GRAND32ab046 rechecked0/0 with87 parallel changes preserved; only its GSO
coordination note was appended. No typed separation event exists there, and its
DepartmentRecord remains the general records authority.

Migration0021 adds default-store review/event tables. Supplied private HR request,
native employee identity, explicit owner grants, findings/coverage, signed custody
submission, independent review, returned drafts and cancellation now have services
and screens. Retained outcomes are office-scoped as-of observations, never clearance
certificates, HR status, payroll holds or Finance liability. Source locks follow
sorted assets → employee → case, rejecting changed asset sets. See
[design and limits](hr-custody-review.md).

Shell99 discovered/85 executed/14 skips PASS28.987s; native shell99/99 PASS84.119s; check/drift PASS. Populated
upgrade preserves inventory/claim/mapping rows and Finance bytes. Browser recorder
submission and separate reviewer decision PASS; desktop/mobile inspected,
390px page/scroll widths and no duplicate IDs. Preview8030/browser stopped.
Stopped paired recovery207 default/83 finance tables and3 private files PASS;
altered findings, missing decision and missing/changed evidence detected/restored.
Backup `.codex/backups/gsov2-hr-custody-recovery-20261017-u2mmahc0`.

Initial focused tests found fixture errors (reading a closed file, then explicitly
closing a download response inside TestCase closed its database); both corrected.
Recovery found a cached-file reopen error after removing evidence; verification
now opens the checked private path afresh, and repeated missing-file coverage was
added. Corrected focused SQLite12 discovered/10 executed/2 native skips PASS1.470s;
final native GRAND109/109 PASS38.242s includes the file fix and both observed races.
Both native schemas removed; owned33317 normal shutdown confirmed after standalone99/99
PASS84.119s. Final diff/checks and operator DB hash pass. Version Manager minor
release updated only VERSION/CHANGELOG as previewed. PrimaryCI38969293198 PASS.
This documentation follow-up records the verified feature publication.
No operator migration, grant or deployment. Overall goal remains incomplete.
Next: physical quantity/cost-component allocation, Accounting valuation and accepted
official outputs remain separate gaps. Recheck actual Finance source/handoff before
designing the next slice; preserve its active uncommitted Form1 work.

## Reviewed receipt recognition mappings

Published code milestone: ba17b63/v0.14.0, integrated/pushed after branchCI38965891940
PASS. Remote master/tag verified atba17b6357f192478a2180ea89b41aa4317d1ff0a.
Primary CI38966060591 PASS. Documentation cleanup676bc29/v0.14.1 is published,
preserving the tested implementation; both branch and primary CI passed.

Developed on `codex/receipt-journal-mapping`, based onbc2fabc after clean fresh
fetch0/0. GRAND32ab046 fetched0/0 with87 parallel dirty/untracked files preserved;
only the authorized GSO coordination note was appended. Adapter0004 creates two
default-store mapping/event tables. Signed proposal, exact source/claim/receipt
basis, private-file checks, independent review, debit/claim ceilings and retained
withdrawal history now relate approved receipt support to selected recognition
debits. No Finance writes, asset valuation, physical quantity split or new roles.
See [mapping design](receipt-journal-mappings.md), especially lock order and
durable default commit inside the outer Finance read/lock transaction.

Initial focused SQLite5 executed/1 native skip PASS1.548s; native94/94 then96/96
PASS39.534s/34.043s before final private-file recheck. Final native97/97 PASS34.530s;
both schemas removed and owned33317 stopped. Shell99/85 executed/
14 skips PASS24.295s. Populated optional migration preserves existing inventory/claim
rows and Finance bytes; drift check passes. Browser60.00 independent mapping against
100.00 source/support passes; mobile375px page/scroll widths, no duplicate IDs.
Preview/browser stopped. Final service fixture includes original delivery/inspection
files. Stopped paired recovery205 default/83 finance tables +2 files passes;
altered amount, missing approval event and missing/changed files detected/restored.
Backup `.codex/backups/gsov2-journal-mappings-recovery-20261017-1jvg_14e`.
No operator migration, grants, deployment or formal acceptance performed.

Next: physical quantity/cost-component allocation and Accounting valuation remain
separate; HR-reference clearance and accepted official outputs remain incomplete.
Overall goal stays active. Check current Finance source before the next design.

## Recognition journal inspection

Current branch `codex/journal-source-preview`, based onf0b20e2 after fresh clean
fetch0/0. GRAND32ab046 fetched0/0; parallel87 dirty/untracked files preserved.
Only its GSO coordination note was appended. Optional adapter now exposes scoped
read-only recognition requests and source-bound posted debit observations from
receipt support. Requires explicit owner-office ledger grant and existing source
visibility; verifies retained source/posting facts and flags active reversals.
No migrations, new grants, persisted allocation or ledger writes. See
[design/limits](journal-source-preview.md).

Focused actual-GRAND SQLite4/4 PASS0.480s; shell99/85 executed/14 skips
PASS31.769s. Drift/dependencies/diff checks PASS. Browser desktop/mobile inspected,
local table scroll and no page overflow. Missing copied GRAND logo/avatar media
is pre-existing fixture setup. Preview8028/browser stopped; operator DB unchanged.
Full GRAND native87/87 PASS30.051s; both test schemas removed and owned33317 stopped.
VM releasebc2fabc/v0.13.0 integrated/pushed; branchCI38963611751 and primary
CI38963770182 PASS. Remote master/tag verified, canonical clean0/0. See validation record for exact scope. Quantity/cost allocation and reviewed JEV
relationships, HR clearance and official outputs remain incomplete.

## Reviewed documentary cost amendments

Started `codex/receipt-cost-amendments` after fresh clean fetch0/0 at83570a2.
Previous releasev0.11.3 integrated/pushed; branchCI38960485867 and primary
CI38960603192 PASS. GRAND fetched0/0 at32ab046; active Form1 handoff inspected,
all parallel implementation preserved. Only its GSO coordination note is updated.

Inventory0020 adds amendments/events with private correcting source, exact nullable
cost, protected predecessor/actors and one pending line constraint. Signed record
screen, independent decision, scoped download and history retain original/effective
facts. Original receipt/asset/stock/FIFO values remain unchanged. Approval increments
receipt version, invalidating prior claim support; new support pins amendment and
uses its documentary ceiling. No Accounting entry, valuation decision or quantity
correction. Optional adapter0003 declares inventory0020 dependency, no operations.

Focused standalone5/5 PASS0.485s; full SQLite99/85 executed/14 native skips
PASS28.913s; native99/99 PASS86.671s. Actual GRAND focused SQLite2/2 PASS0.441s;
full native83/83 PASS27.208s, including actual amendment/claim-approval lock wait.
Populated migration, idempotent submission/review races, scoped HTTP, corrupted
source denial and stale support withdrawal pass. Existing23 non-GSO W036 warnings
remain. Adapter-only migration target and both-app drift checks pass on copied
fixture; no existing receipt/asset rows changed. Dependency check passes.

Browser record/upload then different reviewer approval100→75 passes; desktop/mobile
screens inspected, mobile width375 equals scroll375, no duplicate IDs. Preview8027
and browser stopped. Stopped paired recovery preserves203 default/83 finance tables
and3 private files; original asset100/effective75 and approval history retained.
Missing/changed evidence and removed approval event detected/restored. Backup:
`C:/Users/Administrator/.codex/backups/gsov2-receipt-amendments-recovery-20261017-g1qxchpl`.
Source/operator DB unchanged. Native schemas removed and owned MySQL33317 stopped.
VM releasef0b20e2/v0.12.0 integrated/pushed; branchCI38962084835 and
primaryCI38962259902 PASS. Master/tag verified and checkout clean0/0. See validation record.

Next: financial quantity/cost allocation and journal relationships using GRAND's
existing authorities; HR-reference clearance and official outputs remain incomplete.
Quantity correction/reversal and financial revaluation are not implemented. Overall
goal stays active; code release does not install migrations/grants in GRAND/operator stores.

## Legacy asset authority alignment

Fresh GSO fetch clean0/0 atb232924, branch `codex/asset-authority`. Prior receiving
releasev0.11.2 is integrated/pushed: branchCI38959271074 PASS43s, primary
CI38959384805 PASS; master/tag verified. GRAND fetched0/0 at32ab046 with parallel
unpublished Form1 changes preserved; its handoff still reports full regression.

Actual copied-GRAND probe reproduced seven legacy mutations allowed to both
ungranted superusers and GSO UAT users. All fourteen now deny. Asset create/edit,
legacy transfer/acknowledgment, disposal, verification and audit reads share the
existing GRAND explicit grant policy; no new roles, schema or account authority.
Read-only history uses scoped existing grants; mutation helpers default to denial
for UAT. Navigation uses actual read helpers, including receiving/stock.

Standalone SQLite91/79 executed/12 skips PASS23.725s; native91/91 PASS80.414s.
Actual GRAND SQLite79/68 executed/11 skips PASS13.933s; final native80/80
PASS25.996s including added same-office UAT handoff denial. Existing23 non-GSO
W036 warnings remain. Browser scoped UAT disposal/count history verified without
write controls; mobile count no page overflow. No schema/storage changes.
Preview8026/browser stopped, both native test schemas removed, owned MySQL33317
shut down normally. Operator DB unchanged. VM release83570a2/v0.11.3 integrated/pushed;
branch and primary CI passed. Next: reviewed documentary cost amendments and Finance
quantity/cost/JEV relationships. HR-reference clearance and official outputs remain incomplete.

## Receiving authority correction

Started `codex/receiving-authority` from cbdd0d1 after clean fetch0/0. Previous
notes release master CI38957660920 PASS42s. GRAND source remains32ab046;
parallel Form1 changes are preserved. A copied disposable actual-GRAND fixture
reproduced implicit-superuser access and GSO-assigned UAT write access in receiving.
The corrected helper requires explicit GRAND action grants and blocks UAT writes;
scoped reads/private evidence remain available. POST gates and controls share it,
and receiving responses prohibit caching. No schema or role changes.

Final standalone SQLite91/79 executed/12 native skips PASS28.340s; native91/91
PASS72.475s. Actual GRAND native75/75 PASS25.703s; existing23 non-GSO W036
warnings remain. Initial failures were test assertions (expanded cache header,
prose matched instead of create link), corrected without weakening protection.
Browser UAT scoped reads/control absence visually verified; preview8025 stopped.
No schema/storage change, so prior recovery evidence remains applicable.
Actual VM releaseb232924/v0.11.2 published; branch and primary CI passed.

Next: audit legacy asset/transfer/disposal/verification authority before claiming
consistent GRAND policy across GSO. Documentary cost amendments remain planned;
receipt-side claim snapshots are already published. Overall goal is incomplete.

## Published receipt-side claim review basis

Previous turn published counts3ec09d6 and notes217a4d3/v0.10.1. Final notes primary
CI38955602714 PASS50s; feature primary CI38955372028 passed. Fresh fetch and clean
0/0 preceded `codex/receipt-support-basis`. GRAND remains32ab046, fetched0/0;
its active handoff reports full Finance tests running and all Form1 work unpublished.
No GRAND application/test sources or owned Finance33308 server are changed here.

Source review found claim support pins claim facts but uses live receipt facts and
omits them from signed previews. Implementing retained receipt snapshots before
accepted-cost amendments: optional adapter migration0002 leaves old rows NULL;
new confirmation/review reject changed bases, history shows retained values, and
stale/missing approved receipt bases block further support until explicit withdrawal.
Read receipt lines after acquiring their parent lock. See
[cost correction design](receipt-cost-corrections.md); amendment UI itself is
not implemented and no accepted receipt/asset/FIFO is rewritten.

Standalone91 discovered/79 executed/12 native skips PASS30.089s; adapter migration
drift and dependency consistency PASS. Initial GRAND SQLite71/native72 runs each
failed one invalid test fixture (accepted quantity exceeded delivery); corrected
fixture, kept DB constraint. Final actual GRAND SQLite72/61 executed/11 native skips
PASS12.432s and native72/72 PASS30.325s. Logs`.tmp/receipt-basis-{sqlite,native}-final.log`.
Existing23 GRAND W036 warnings remain outside GSO. Both test schema pairs removed;
owned MySQL33317/session27946 shut down normally. Finance33308 untouched.

Actual GRAND browser preview/confirmation/independent approval passes; simulated
fixture-only cost change100→200 leaves original100 visible with a stale warning.
Mobile390/desktop1440 inspected, no page overflow or duplicate IDs; warning contrast
corrected and verified in restarted preview. All preview8024/browser sessions stopped.
Final paired stopped recovery preserves201 default/83 finance tables, both source
snapshots and original approval; deliberate approval-event loss detected/restored.
Backup`.codex/backups/gsov2-receipt-basis-recovery-20261017-8y_nfx_8`; no attachments
in this fixture. Source unchanged during recovery. Operator DB hash unchanged.
Actual external VM minor release543fef8/v0.11.0 integrated/pushed to master after
branch CI38957280486 PASS36s. Remote master/tag match
543fef8d72a30783923984c02fa4ea71157ba6bd. Primary CI38957393614 PASS42s.
Release notes use separate `codex/receipt-basis-release-notes`, fresh clean fetch0/0.
Overall goal stays active.
Next: reviewed documentary cost amendments, after checking receiving authorization
against actual GRAND explicit grants/UAT controls; then financial quantity/cost/JEV
relationships. HR-reference clearance and official outputs remain unfinished.
Source audit for next step: `require_receiving` still uses `actor.has_perm` rather
than GRAND's explicit helper/UAT check already used by maintenance and stock.
Reproduce ungranted-superuser and GSO-assigned UAT cases before the next amendment
feature; preserve standalone behavior and ordinary granted receiving access.

## Published reviewed physical counts

Started `codex/reviewed-stock-counts` after fresh fetch and clean 0/0 at
8809372/v0.9.3 (primary CI38953114417 PASS39s). GRAND fetched 0/0 at32ab046;
parallel Form1 work is preserved. Migration0019 adds one-item count records,
protected evidence/events, signed staff screens and configured low-stock indicators.
Counts pin today's ledger; stale bases require cancellation/recount. Independent
approval creates one exact existing-ledger adjustment, or no movement for zero
variance. Surplus cost remains unknown. No Finance writes or operator migration.
Historical counts need separate reconciliation; this is not an official RPCI.

Final standalone native91/91 PASS74.794s; SQLite91 discovered/79 executed/12 native
skips PASS28.059s. Migration drift and dependency consistency pass. Initial GRAND65
run exposed a test cleanup error after a successful download; corrected the test,
final actual-GRAND native65/65 PASS19.277s, log`.tmp/grand-stock-count-release.log`.
Both disposable schemas removed; owned MySQL33317/session51174 shut down normally.
Existing23 GRAND W036 warnings remain outside GSO; no GSO system-check warnings.

Actual GRAND browser record/upload/independent approval passes; stock10 to8 with
one adjustment-out2 and minimum8 reminder. Desktop/mobile visually checked, no
page overflow or duplicate IDs. Both browsers and preview8023 are stopped.
Stopped paired recovery preserves201 default/83 finance tables and one count file,
including original actors, basis, adjustment and all three events. Missing/changed
files detected and restored; source unchanged. Backup:
`C:/Users/Administrator/.codex/backups/gsov2-stock-count-recovery-20261017-k6d90rer`.
See [count design](stock-counts.md) and [validation](validation-2026-10-16.md).
Actual external VM minor release3ec09d6/v0.10.0 is integrated/pushed to master after
branch CI38955242812 PASS38s. Remote master/tag match
3ec09d6b6e204759c8e5e33b526fc0662e33e25b. Primary CI38955372028 PASS35s.
Documentation follow-up uses `codex/stock-count-release-notes` after fresh clean
fetch 0/0. Operator database hash is unchanged. Overall goal stays incomplete. Next: HR-reference review cases and
Finance cost correction/allocation/JEV relationships, with official supplies forms
and historical count reconciliation separately verified before implementation.

## Published supplies ledger validation

Previous turn published return notes v0.9.1/e7483a6; branchCI38951646913 and primary
CI38951773610 PASS. Fresh fetch and clean0/0 preceded `codex/stock-ledger-validation`.
GRAND remains32ab046, fetched0/0; unrelated Form1 changes preserved.
Inspection found a direct-service precision gap and implicit GRAND stock authority.
Regression test reproduced acceptance of0.0004 despite three-place storage. Services
now reject invalid precision/nonfinite/negative values, require adjustment reasons,
resolve issue destination labels, validate catalog minimums and preserve omitted FIFO.
GRAND stock permissions reuse explicit grants and deny UAT mutations.
Standalone76 discovered/67 executed/nine native skips PASS14.660s; native76/76
PASS49.834s. Actual GRAND native63/63 PASS19.761s. Both disposable schemas removed
and owned MySQL33317 session61913 shut down normally. See
[stock-count design](stock-counts.md). No schema or operator
data changes. This published integrity prerequisite supports reviewed physical counts;
HR-reference clearance and financial relationships remain in scope.

Actual VM patch releasecbece6c, tagv0.9.2, is integrated/pushed to master after
branchCI38952776429 PASS31s. Remote master/tag matchcbece6c9d2875d1b255be29c03ac29ce72ae23ba.
PrimaryCI38952884082 PASS41s. Documentation follow-up uses separate
`codex/stock-ledger-release-notes`, created after clean fetch0/0. The reviewed physical-count workflow is tracked above; it was not part of this fix.

## Published witnessed returns

Custody-review notes published as v0.8.1 at efbc671; branch CI38947862792 and
primary CI38948007851 passed. Fresh fetch and clean 0/0 preceded branch
`codex/witnessed-custody-returns`; a further fetch found no upstream changes.
[Witnessed returns](custody-returns.md) are published at2a7bb5f, tagv0.9.0.
Migration0018, services, private evidence/checker and signed staff screens are implemented.
Standalone SQLite71 discovered/62 executed/nine native skips PASS17.436s;
populated0017-to0018 preservation PASS1/1. Initial GRAND service SQLite55 discovered,
48 executed/seven native skips PASS5.792s. Standalone native71/71 PASS51.702s.
Initial actual-GRAND native60/60 PASS17.049s. Expanded61-test run had one fixture
error: maintenance closure correctly required recorded work. Corrected the test;
final native61/61 PASS16.937s, log`.tmp/grand-returns-native-corrected.log`.
Both disposable schemas removed; owned MySQL33317 shut down normally.
Existing23 GRAND warnings remain outside GSO.
Browser record/upload/independent confirmation/returned review passes desktop/mobile;
both sessions and preview8022 stopped. Paired stopped recovery preserves198 default,
83 finance tables and one return file; corruption/loss detected and restored with
source unchanged. Backup `.codex/backups/gsov2-return-recovery-20261017-tiw0kkdn`.
No operator database or Finance implementation changes. Clearance remains unimplemented.
Next: HR-reference review cases/unresolved-item decisions, then consumable counts;
Finance cost correction/allocation and recognized-JEV relationships remain separate gaps.

Actual external VM minor release2a7bb5f was pushed on the feature branch. Branch
CI38951280608 PASS before canonical master fast-forward/push. Remote master/tag
match2a7bb5f978ee1747e869472c243312dc6a683dd1. PrimaryCI38951482546 PASS50s.
Release notes use separate `codex/custody-return-release-notes` after clean fetch0/0.

## Published custody review milestone

Previous goal turn made verified progress: custody236c5e1 and release notes55fc7bf
are published. Final documentation branchCI38945566281 and primaryCI38945701870
passed; remote master/tag match55fc7bf and operator DB hash is unchanged.
Fresh fetch0/0 and clean tree, then created `codex/custody-review`. GRAND also fetched
0/0 with its unrelated Form1 changes preserved. Rechecked actual profile visibility,
permissions and absence of structured employee separation in profiles/users.

The [custody review workbench](custody-review.md) is written: personal retained
assignments, owning-office review, separate legacy records and pending handoffs,
minimal current-HR comparisons, GET-only/no-store and bounded search/pagination.
No new schema or clearance decision. Own custody remains visible after HR moves
without granting owner-office write access. GRAND's explicit permission helper still
requires an assigned department; GSO can review retained history when the employee
cannot access it. At that checkpoint, clearance cases, returns and signoff were next.

Standalone4/4 boundary tests PASS0.454s, full shell70 discovered/61 executed/nine
native skips PASS11.670s. SQLite GRAND49 tests had one test expectation failure:
missing department correctly denies the recipient through GRAND's helper. Corrected
the test, not the authority check. Expanded native run37525 PASS50/50 in14.501s, no skips; log
`.tmp/grand-custody-review-native.log`. Both disposable schemas removed and owned
MySQL33317 session82727 shut down normally.
Browser office/legacy and moved-employee personal views inspected on isolated
`.tmp/custody-review-preview-6ypwa4un`, port8021 and browser sessions are now stopped. Mobile390 client/scroll widths match; no overflow
elements or duplicate IDs. Screenshots output/playwright/custody-review-*.png.
Published through the actual VM minor releasefb2eae2, tagv0.8.0. BranchCI38947590308
passed before canonical master fast-forward/push. Remote master/tag match
`fb2eae2c59df7669cb228eb344bc3f1521f1469a`; operator DB hash unchanged.
PrimaryCI38947689210 PASS. Release notes use separate
`codex/custody-review-release-notes`, created after clean fetch0/0.
The subsequent witnessed-return milestone is recorded above. HR-reference review
cases and clearance conclusions remain unimplemented. Overall goal remains incomplete.

## Published maintenance milestone

See [maintenance workflow](maintenance.md). Migration0016, services, staff
screens, private evidence, asset/dashboard links and recovery checker are implemented.
Final standalone MySQL65/65 PASS15.703s; SQLite65 discovered/56 executed/nine native
skips PASS7.048s. Three races cover duplicate starts, handoff versus maintenance and
duplicate closure. Populated0015-to0016 preserves existing inventory history.
Drift/pip checks passed. Actual GRAND SQLite29 discovered/24 executed/five native
skips PASS2.777s; native GRAND29/29 PASS8.430s. Existing23 GRAND W036 warnings remain,
none in GSO apps. Both disposable schemas removed and owned MySQL stopped normally.

Browser login/open/work/upload/complete inspected desktop1440x1000/mobile390x844.
Completed mobile width390 matches viewport and no duplicate IDs. Only favicon404.
Browser and preview port8019 stopped. Synthetic source remains at
`.tmp/maintenance-preview-_g03g7vp`. Stopped DB+private-file recovery reconciled
37 tables and one file, detected/restored corrupted and missing evidence, and left
source unchanged; backup `C:/Users/Administrator/.codex/backups/gsov2-maintenance-recovery-20261017-nzu80ff7`.
Not online MySQL/operator recovery. Actual external Version Manager release3905a74,
tagv0.6.0, was pushed on `codex/asset-maintenance`. BranchCI38941638939 passed before
canonical master fast-forward/push; primaryCI38941747339 passed at the same commit.
Remote master/tag verified and operator DB hash unchanged. No operator migration,
permissions grant or deployment. Finance coordination note updated only.

Documentation releases f6ea69e and60d12af are published; final branchCI38942013769 and
primaryCI38942094327 passed. Remote master/tag verified, operator hash unchanged.

## Published employee custody milestone

Fresh fetch0/0 and clean tree at60d12af, then branch `codex/employee-custody` in
`C:/Users/Administrator/.codex/worktrees/gsov2-receiving-safety`. Read
[employee custody design](employee-custody-design.md). Actual GRAND profiles,
permissions and HR source were inspected. No structured separation/clearance model
was found; disabled login is not employment termination. A minimal read-only
employee-source resolver and migration0017/custody services are written. New nullable
protected employee links/snapshots retain legacy text; transfer UUID migration uses
per-row backfill. Named recipient must personally acknowledge a different initiator's
handoff with unchanged identity/department. Generic edits and office-only handoffs
cannot erase named custody. Partial register edits no longer clear an omitted office.
Asset-first locks unify transfer start/ack/cancel; start checks current locked owner.

Initial source run PASS33 discovered/28 executed/five native skips3.727s (intermediate
source). Expanded actual-GRAND SQLite run60414 ended with one test expectation
error: after HR moved the employee, existing department scope correctly denied
acknowledgment with PermissionDenied before snapshot comparison. Corrected that
expectation and added same-office name-change rejection. Corrected run86403 completed39 discovered/34 executed/five native skips PASS2.927s.
Signed employee search/review/confirm screens and links are now written. Tokens bind
actor, asset, source custody and employee fingerprint; request UUID makes retries
idempotent even after closure. Incoming named handoffs are visible across GSO offices
without granting owner write authority. All three transfer actor FKs now PROTECT.

Latest standalone SQLite69 discovered/60 executed/nine native skips PASS9.882s;
native MySQL69/69 PASS28.912s; drift/dependency checks clear. Logs
`.tmp/custody-shell-release.log` and `.tmp/custody-native-shell.log`.
Actual GRAND HTTP run87126 found three query errors (`__pk` in nested `.only`);
fixed to concrete GRAND `id` and retained profile visibility filtering. Native
run60476 PASS44/44 in12.481s, including the two new races. Final native run35547
PASS44/44 in11.095s after tightened actor/asset binding assertions and UI wording;
log `.tmp/grand-custody-native-final.log`. Both disposable schemas removed; owned
MySQL33317 session88427 shut down normally. No preview/browser/server remains.

Browser requester/recipient handoff passed, desktop1440x1000/mobile390x844 inspected.
Sessions closed and preview8020 stopped. Synthetic paired source remains
`.tmp/grand-source-tests-nhoggi1i`. Recovery PASS:196 default/83 finance tables,
identity snapshot/accepted actor/audit retained, injected loss detected/restored;
source unchanged. Backup `.codex/backups/gsov2-custody-recovery-20261017-nj9xiahl`.
Not online MySQL/private-upload/operator recovery. External VM minor release236c5e1 (v0.7.0) is published. BranchCI38945305792 passed
before canonical master fast-forward/push. Remote master/tag match
`236c5e1e265bc1a63b97a9d3271133e94b598f10`. PrimaryCI38945433056 PASS.
No operator migration, grants or deployment. Release notes follow on separate
`codex/custody-release-notes`, created from a clean fetch0/0 checkpoint.
Clearance/HR separation remain unimplemented. Overall goal is incomplete.

## Published reviewed claim support

Published claim support at`28da3f1`. Optional `inventory_finance` includes
same-store protected receipt/case/owner/actor relationships, source snapshots,
proposal/independent approval/rejection/withdrawal, immutable event saves and
scoped GRAND-base screens. Signed previews bind actor/case/content and expire.

Approval locks the case and receipt, caps claim-line totals and receipt-wide totals
across claims, rejects stale/replaced source evidence, and blocks UAT/self-review.
Unknown/zero receipt cost cannot create claim support. This does not post accounting,
reserve Budget capacity, allocate physical quantities or establish acquisition cost.
Accepted-receipt cost correction and recognized-JEV attribution remain incomplete.
No automatic grants, operator migrations, deployment or parallel Finance edits.

PASS: 26 MySQL8.4.11 actual-GRAND service/HTTP/race tests (7.930s, no skips), including
cross-case receipt capacity and CSRF/signed-preview controls. Log
`.tmp/grand-attribution-capacity-http-native.log`. Existing 23 GRAND W036 conditional
uniqueness warnings remain; none concern inventory or inventory_finance. Both random
schemas removed and owned MySQL server stopped normally.
PASS: standalone49 discovered/43 executed/six native skips (3.370s), actual GRAND
model checks, both app migration drift, pip check and whitespace check.

Browser: real GRAND clerk login, preview/submit, separate reviewer approval and
withdrawal at1440x1000/390x844. Original approval and full history retained; mobile
checks found no horizontal overflow/duplicate IDs. Screenshots output/playwright/claim-*.png.
Isolated media lacks default GRAND logo/avatar (404s). Browser sessions and port8018
stopped. Synthetic paired SQLite preview files remain under
`.tmp/grand-source-tests-i2l7amgw`; no operator data.

Recovery PASS: stopped paired source backed up/restored, all193 default/83 finance
tables reconciled, integrity/FKs valid. Injected loss of an approval event was detected
and recovered; source hashes unchanged. Evidence:
`C:/Users/Administrator/.codex/backups/gsov2-attribution-rehearsal-20261017-011803`.
This database-only rehearsal does not cover private uploads or online MySQL recovery.

Published via actual Version Manager minor release28da3f1, v0.5.0. BranchCI38938855245
passed before fast-forward/push to master. Remote master/tag match and operator hash
is unchanged. MasterCI38939041377 passed at the verified release commit. No branch rulesets/protection found.
Parallel Finance integration note updated without code/migration/shared-handoff edits.

Financial cost-correction, JEV links, stock counts, clearance and wider
general-office records remain open in the roadmap.

## Published receiving milestone

Receiving `7d3547f` and documentation `9ae80c0` are published; primary checks
38932087704 and 38932337771 passed. Migrations0013/0014 provide draft corrections,
protected evidence, independent acceptance and atomic asset/stock materialization.
0015 provides portable lifecycle uniqueness and duplicate preflight. Accepted receipt
reversal and incremental remainder processing remain unimplemented; see receiving guide.

Published native suite: 45/45 PASS, including competing acceptance/asset identifiers,
lifecycle uniqueness and populated upgrades. Synthetic backup/restore rehearsals
preserved data and evidence, including corruption detection. Evidence artifacts:
`.codex/backups/gsov2-receiving-rehearsal-20261017-001404`.
No production deployment, operator migration or human acceptance is claimed.

## Preservation and parallel work

Canonical repo: `C:/Users/Administrator/Desktop/GH/GSOv2`, primary `master`.
Operator DB/photo are ignored and must not be migrated by code release. Backup:
`.codex/backups/gsov2-20261016-before-untracking` (raw DB, backup snapshot, image,
manifest and stash reference). Operator DB SHA-256:
`5c6c3c66e46d8a6f4a95799806ec96f4ef3fda923027adba29d63e9f337a2039`.
Preserve ignored files and historical evidence. This is not complete operator recovery.
Previous published foundation: `e642d9e`, documentation `405f360`; primary CI
38928123403 and 38928528769 passed.

GRAND active worktree: `.codex/worktrees/finance-form1-treatments/grand`, branch
`codex/finance-form1-print-evidence`. Form1 work remains unpublished. Separate
`docs/GSO_INTEGRATION_REVIEW.md` holds GSO notes and populated generated-column
upgrade advice. No Finance code/migrations/shared handoff changed. Do not publish its
parallel work; fetch and inspect its current source before adapter work.

## Next work

1. Check live primary/documentation CI and fetch sync before the next feature;
   preserve operator data and use a separate feature branch.
2. Select the next roadmap workflow on a separate branch. Claim support and basic
   maintenance are published; accepted-receipt cost correction
   and recognized-JEV linkage still need explicit design against current GRAND.
3. All 21 pages of the retained 2024-006 copy are visually reviewed. Establish
   publication/amendments and review relevant 2002-003/2023-004 text before official outputs.
4. Continue maintenance corrections, stock counts, custody/clearance, general-office records,
   accepted outputs, GRAND import/router and coordinated recovery work per roadmap.


## Disposal evidence integrity — local validation complete

Previous turn: progress. Actual VM published577c549/v0.21.1; branchCI38983516424
and masterCI38983686513 PASS. Remote master/tag verified, canonical clean0/0,
operator database unchanged. Fresh sync this turn: clean0/0 at577c549; Finance
candidate a533482 unchanged except coordination note, master32ab046.
New branch `codex/disposal-evidence-integrity`.

Inventory0026 adds a blank-by-default attachment SHA-256; old records and events
are preserved without fabricated historical hashes. Shared save service validates
all upload groups before file writes, captures actual byte counts/hashes. Downloads
check and rewind the same open file; missing/changed files return409. Authorization
and completion check retained files, allowing legacy unknown hashes explicitly
but still rejecting missing/size-changed files. Strict source verification rejects
legacy unknowns; do not treat operational completion as verified SPC evidence.
Read-only `check_disposal_evidence` reports unknown, missing, changed, unsafe and
unreferenced files without modifying them. UI distinguishes retained baselines.

Shell142 (121 run/21 native skips) PASS44.109s. Focused6 PASS0.351s after recovery
caught and fixed a reopened-missing-file ValueError. Full native standalone142 finished with one new test-fixture error: manually
closing an already-consumed streaming response fired request_finished twice and
closed MySQL's test transaction. Redundant close removed in standalone and GRAND
tests. Final standalone native143/143 PASS124.530s; corrected full actual GRAND
135/135 PASS55.812s, exit0. Affected native12/12 PASS1.955s after both fixes.
All disposable schemas removed; owned MySQL normal shutdown confirmed.
Populated actual GRAND copy preserved216 prior non-migration tables and Finance
bytes. Desktop/mobile inspected, table scroll remains contained; browser/preview
stopped. Recovery217/83 tables/9 files PASS at
`C:/Users/Administrator/.codex/backups/gsov2-disposal-evidence-recovery-20261017-wm6udr7g`.
See validation record for limitations and remaining release gates. Overall goal active.
