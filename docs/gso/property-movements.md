# Documented property movements and openings

Implemented milestone, 2026-10-17, on `codex/property-movement-records` from
dbd47c0. Schema, reviewed-record services, screens and a source-checked working
projection have passed the local release gates recorded in [CONTINUE](../CONTINUE.md).
Publication status belongs there; no official SPC output is claimed.

## Source and scope

Re-read Annex A.2 form/instructions (pages7–8) of the retained
[COA2024-006 ONAR copy](https://naro.law.upd.edu.ph/storage/01JT2JXVWNE95WHFN0FE53KQC9.pdf)
and reopened [the official index](https://naro.law.upd.edu.ph/issuances/3842).
The card distinguishes receipt and issue/transfer/disposal entries, source references,
item numbers, office/officer and remaining quantity. This engineering design retains
those source facts; it does not establish current legal applicability, local numbering
policy, approval authority, financial treatment or accepted official formatting.
See [COA evidence](coa-requirements.md) and [property design](property-record-design.md).

Actual source inspection: accepted ReceivingLine identifies one registered asset;
AssetTransfer distinguishes acknowledged handoff and independently confirmed return;
completed AssetDisposalCase retains approval/completion facts. Return condition alone
does not establish stock availability; a custody reassignment is not another stock
issue. Legacy pooled Asset.quantity must be reconciled before individual annotations.

## Selected data design

PropertyMovementRecord is an annotation, never a second physical movement. It has a
public request UUID, protected asset/determination/source/predecessor relations,
documented date and within-day order, reference/item number, supplied office/officer,
stock effect, nullable documented unit cost, remarks, one private PDF/image packet,
retained hash/size, recorder, independent decision and immutable checksum events.
The pinned verified property determination supplies historical class/fund/life facts;
a later determination must not silently reclassify old annotations.

One of these source relations is permitted, enforced by database constraints:

| Source | Retained relation | Permitted stock effect |
| --- | --- | --- |
| Opening | No physical-event FK; supported opening packet | Explicit end-of-day quantity0 or1; no delta |
| Receipt | Accepted, nonvoid asset ReceivingLine | +1 |
| Handoff | Acknowledged handoff AssetTransfer | -1 for documented stock issue, or0 for reassignment |
| Return | Confirmed return AssetTransfer | +1 for documented return to stock, or0 when not establishing stock |
| Disposal | Completed AssetDisposalCase | -1 from stock, or0 for an already issued item |

Effects are engineering representation choices requiring source evidence and review,
not automatic conclusions from status/custodian/condition. An opening0 means the
individual item is not in stock; it does not erase its physical accountability.
A receipt delivered directly to an end user still needs its separate documented
issue; do not silently collapse the two events. Source quantities and effects do
not authorize Accounting valuation or journal entries.

Use source keys derived from existing public identities: opening per asset, receipt
UUID plus accepted line sequence, transfer UUID, disposal UUID. Migration0027 adds
new distinct disposal UUIDs without changing earlier events/files. Native FK numeric
IDs still require explicit import remapping; never match them across installations.
All records stay in default. Finance relationships remain in the existing optional
adapter; no cross-store FK or duplicate fund/account/person/department table.

## Workflow to implement before release

- Dedicated explicit view/record/review grants, GRAND owner/UAT checks, no automatic
  grants. One pending annotation per asset uses the established generated-marker
  constraint. Services recheck scope after locking receipt→asset→source→annotation.
- Record against a fresh pinned verified property packet and completed physical
  source. Retain their exact source snapshots and source file manifests. Require
  private evidence for the annotation, even where old handoffs had no source file.
  Missing/changed sources fail closed; legacy disposal unknown hashes cannot become
  verified card support. Source checks must run again at independent verification.
- A source slot may be corrected only with a successor to its latest verified
  annotation; old decisions remain. Reject stale request/version/predecessor data.
  Exact retries reuse the public request identity; different content is a conflict.
- A documented opening is end-of-day, order0. Post-opening physical events must
  have documented entries, dates strictly after opening, and explicit positive
  within-day order. Never use database PK order as physical chronology.
- A working balance requires a reviewed opening and a complete, unambiguous chain
  through the requested cutoff. Detect unannotated eligible events, duplicate
  ordering, stale source snapshots and pending corrections. Refuse negative or
  greater-than-one per-item stock. Show unresolved history rather than guessed zero.
- A later class/fund change needs explicit reconciliation, not automatic transfer
  between card groups. Initial projection must flag such a mismatch. Preserve
  historical labels and source versions; no matching to native Finance by text.
- Unit cost is a nullable supplied documentary fact. Keep unknown amounts explicit;
  do not substitute current register cost, aggregate it as approved carrying value
  or claim physical cost allocation is complete.
- Forms, independent review/history, private downloads, source selection and a
  labelled working projection must be usable before publication. Official SPC
  formatting/local acceptance remains a separate gate, not satisfied by this design.

## Required validation

Schema constraint/populated migration tests; realistic receipt→issue→reassignment→
return→disposal chain with opening0/1; missing/ambiguous/backdated history; corrections
and stale retries; changed/deleted/private source; negative stock rejection; grouped
legacy denial; forged cross-owner IDs; UAT/ungranted superuser denial; no custody or
Finance mutation; native concurrent records/reviews; actual GRAND router/HTTP tests;
visible desktop/mobile workflow; paired database/private-file recovery. Do not release
schema-only work or report these unrun gates as completed.


## Services

`inventory/property_movements.py` now implements explicit movement grants, fresh
receipt/asset/source locks, whole-action evidence validation, exact request replay,
independent verification/rejection/cancellation, retained predecessor/event checks,
and source snapshots. Selected property packets must still match their asset/receipt
basis and have no pending property correction. Changes require reconciliation;
old annotations remain visible as history rather than silently using new facts.

For the first workflow, a movement's date must equal the physical source's retained
receipt delivery, transfer or disposal date. A date discrepancy requires source
reconciliation; allowing an arbitrary annotation date would let an entry disappear
from a cutoff window while its underlying source remains in that window. Source
entry must not relabel receipt delivery as the supplied acquisition date.

The working projection locks the asset while checking the current reviewed
reconstruction through a cutoff. It requires a verified opening, reports pending
annotations, missing/extra eligible sources, duplicate within-day order, source/file
or class/fund drift, stock outside0–1 and disposal leaving stock. An undated legacy
retirement is unresolved. All running/final balances remain unknown when any check
fails. It uses current reviewed corrections, not knowledge-as-of a historical date,
and proves consistency with retained app sources, not completeness of external events.
Documented unknown costs remain NULL; this is not a financial valuation calculation.

`check_property_movement_evidence` reuses the read-only private namespace checker.
Include `inventory/property-movements` in coordinated backup. Interrupted database
writes can leave unreferenced private files; investigate rather than delete them
silently. Native races, real receipt/return/disposal chains, HTTP/UI, browser and
paired restore gates passed for this milestone; see the validation record. Small
service/schema suites alone do not establish those gates.


## User workflow

Per-asset screens select a verified property packet and a confirmed physical event
(or an explicit opening). Signed, expiring form tokens bind actor, asset, selected
source/property version, predecessor and request identity. Physical source dates
are read-only; opening zero and unknown cost remain distinct. Corrections prefill
the prior documentary content but require a new packet and independent decision.
History/private downloads and the working cutoff view use the same owner/action
checks as services. See CONTINUE and validation for completed and pending gates.
The full named receipt/issue/return/disposal chain belongs in the actual GRAND
harness because named employee custody and witnessed returns require its profiles.
No standalone duplicate identity model or bypass is introduced for this test.
