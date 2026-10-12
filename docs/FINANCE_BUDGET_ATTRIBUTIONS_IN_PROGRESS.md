# Native Budget attribution — implementation in progress, 2026-10-11

Branch `codex/finance-budget-attribution` starts at v0.7.153,
`61e690e4eb22c8cc3c9fe1d39c9389e2b5e81ac3` ([draft PR #114](https://github.com/tepong32/grand/pull/114)).
Unpublished work; no accepted printed forms, Budget adoption or LGU acceptance is claimed.
This continues the [source audit](FINANCE_BUDGET_NATIVE_SOURCE_AUDIT.md) and
[validated ledger capture](FINANCE_BUDGET_NATIVE_CAPTURE.md).

## Current implementation

### Historical summary evidence implemented (2026-10-11)

See [the dedicated checkpoint](FINANCE_SUMMARY_ACTUALS_IN_PROGRESS.md) for Accounting
migration 0036, historical joint certification/independent adoption, scoped register,
successor history, exact document exports and SQLite/native/browser validation.
This extends source evidence; it does not turn resource estimates into receipts or
implement native Form 1/cash certification and issuance.

### Form 1 source audit and next implementation (2026-10-11)

The [source/reconciliation contract](FINANCE_FORM1_SOURCE_CONTRACT.md) now traces
existing collection, charge, bank, refund, redemption, trial-balance, cash-flow and
office-form sources. It establishes the next dedicated fund/entity summary evidence
boundary, separate original joint certifications/adoption, explicit receipts and
cash restrictions, complete office reconciliation and issuance acceptance cases.
Period trial-balance movement cannot establish opening cash; collection-kind alone
cannot classify new receipts. Missing stock-column conventions require retained
schedule evidence, not guessed arithmetic. The official retained PDF hash and source
reads pass; runtime tests are out of scope for this documentation-only audit.
This is concrete implementation direction, not completed Form 1 or new acceptance.

### Proposed resource retention prerequisite (2026-10-11)

Inspection before Form 1 found that submission retained expenditure context but
read resource estimates live. Consolidation also copied live resources and prefixed
office names to a description limited to 220 characters. Resource capture now pins
amount, description, basis and funding-source/fund identity in the existing context.
Missing optional fund remains missing. No schema migration is needed.

Create/revise uses BudgetVersion-first locking, current state tokens, prepare/UAT
controls and before/after audit evidence. Model saves recheck the locked proposal
state and reject reparenting; deletion is rejected. Approval and consolidation check
retained resources against current evidence. Submitted displays/CSV use frozen
evidence after setup renaming; legacy resources without a snapshot require an
explicit return/resubmission or successor, never retroactive approval evidence.
Consolidation preserves exact descriptions and per-source origins without summing
or deduplicating potentially overlapping financing estimates.

These are proposed budget-year resources only. Form 1 still needs explicit receipt
categories, past/current actuals, beginning/ending cash evidence, reconciliation of
office totals and joint Treasurer/Accountant certification. Neither a source label
nor a proposal amount establishes certified receipts, available cash or the still
unconfirmed local earmark rule.

Validation: SQLite `python .tmp/my_work_sqlite.py budget.test_resource_context
budget.test_office_forms budget.test_actuals_consolidation budget.test_historical_forecasts`
PASS, 60 tests, no skips, 65.842s, exit 0, both stores destroyed; session 43064
collected, `.tmp/budget-resource-context.log`. Covers HTTP create/revise/replay,
retained exports, stale approval, owner/UAT/reparent protection, explicit zero,
missing fund, legacy refusal and maximum-length consolidation.

Synthetic browser PASS: created 75, revised to 80, submitted, independently approved,
then renamed setup. Approved display and downloaded CSV retained original source
identity and 80.00. Prior issued Form 2 checksums remained unchanged. Screenshot
`output/playwright/budget-resource-snapshot.png` inspected; browser/server closed.
An initial manually entered URL omitted `/finance/` and returned 404; the verified
route worked. This is not an application failure or LGU acceptance.
Native `python .tmp/retrieval_native.py budget.test_resource_context
budget.test_resource_context_concurrency budget.test_actuals_consolidation
budget.test_office_forms` PASS: 40 tests, no skips, 59.148s, exit 0. Both stores
destroyed; session 70669 collected, `.tmp/budget-resource-native.log`. Covers
competing revisions, creation/revision against submission, resource persistence,
consolidation and retained Form 2 regression. Owned MySQL stopped afterward.
Compilation, migration drift (no changes), whitespace and 478 local documentation
links pass. Operator database SHA-256 remains
`C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C`.
NOT RUN - OUT OF SCOPE for this prerequisite: broad release regression and actual
Form 1/printer/LGU acceptance. They remain required before the corresponding gate.

### Retained unsigned office Form 2 (2026-10-11)

Migration 0015 adds `BudgetOfficeForm` in the Finance store. Each preparation pins
an independently approved proposal's schema-7 context, explicit office/fund scope,
LGU name, fund designation, full-coverage declaration/reference, and the names and
designation references for Department Head, Local Budget Officer and Local Chief
Executive. Coverage is a reviewed human declaration backed by retained sources;
the system does not invent a complete office history from the selected rows alone.
Known unselected office scopes, missing actual rows/forecasts, unmapped offices,
inconsistent scopes/totals and unknown object classes block preparation.

All office centers contribute once to each account/object. Other offices/funds are
excluded; explicit zero is retained and missing data never becomes zero. PS/MOOE/
FE/CO/SPA are explicit mutually exclusive row classifications, not inferred tags.
Special-purpose subtotals therefore do not re-add ordinary rows. Proposal approval
is checked against its original submission event; current source/office evidence
must still reproduce the frozen schedule before preparation or new issuance.

Preparation locks the proposal before existing sorted Fund source checks. Version
identity is a native-safe ordinary unique constraint. A signed 24-hour preview pins
actor, proposal, office/fund, context checksum and latest preparation. Independent
review locks proposal before child, rejects self-review/replay and prevents an older
preparation from issuing over a newer one. Stale/obsolete preparations can be returned
without altering earlier evidence. These locks do not serialize all ledger posting;
freshness is a verified coherent captured cohort, not a universal financial-period lock.

Issued bytes, source payload and decision hashes remain immutable. Current owner/read
access is required for detail/download; UAT membership denies prepare/decide. Download
verifies retained evidence/bytes, archives those same bytes and records an audit event;
it never calls the renderer again. Returned/pending preparations have no downloadable
issued document. A successor preserves older issued copies.

The seven-column landscape PDF includes category subtotals, office totals, blank
physical signature lines and a retained-evidence annex. It explicitly says unsigned;
application review supplies neither physical signatures nor signed-copy receipt.
Noto Sans is bundled with its OFL license for Filipino names and peso signs;
unsupported glyphs fail issuance and roll back its decision. Continuation pages
identify office/fund/year and repeat column headings; category headings stay with
their first row. Form 1 reconciliation and joint Treasurer/Accountant certification
remain next. Physical signing, accepted paper dimensions/layouts and LGU acceptance
remain operational gates; this is not a production-readiness claim.

Validation so far:
- Initial SQLite FAIL - CAUSED BY CURRENT WORK: 13 tests, one error and one failure
  (`.tmp/budget-office-forms.log`, session 36495, exit 1). The self-review test lacked
  review permission; the missing-amount test encountered a scope error first. Fixed
  the permission fixture and moved explicit missing-data projection before freshness
  discovery so the expected field errors are surfaced. Both stores were destroyed.
- Broader SQLite PASS: 62/62, no skips, 78.940s, exit 0; both stores destroyed,
  session 11508 collected (`.tmp/budget-office-forms-final.log`).
- Broader native PASS: 64/64, no skips, 96.609s, exit 0; both stores destroyed,
  session 8719 collected (`.tmp/budget-office-forms-native.log`). Includes concurrent
  preparation/decision and successor-versus-issuance, plus populated/preflight migrations.
- Final SQLite PASS: 15/15, no skips, 17.543s, exit 0; both stores destroyed,
  session 16875 collected (`.tmp/budget-office-forms-render-final.log`). Includes
  office/fund isolation across centers, glyph-rejection rollback and final renderer/HTTP flow.
- Final native PASS: 4/4, no skips, 13.051s, exit 0; both stores destroyed, session
  97660 collected (`.tmp/budget-office-forms-native-final.log`). Final renderer,
  unsupported-glyph rollback and both issuance races pass.
- Final instance-deletion retention PASS: 1 no-database test, 0.002s, exit 0
  (`.tmp/budget-office-form-retention.log`), covering prepared, issued and returned
  states and proving the guard acts before database deletion.

Commands use the documented Python 3.11 environment:
```text
python .tmp/my_work_sqlite.py budget.test_office_forms budget.test_schedule_office_identity budget.test_actuals_consolidation budget.test_version_identity_migration
python .tmp/retrieval_native.py budget.test_office_forms budget.test_schedule_office_identity budget.test_actuals_consolidation budget.test_version_identity_migration budget.test_office_form_concurrency
python .tmp/my_work_sqlite.py budget.test_office_forms
python .tmp/retrieval_native.py budget.test_office_forms.OfficeFormTests.test_issue_retain_unsigned_pdf_and_download_after_sources_change budget.test_office_forms.OfficeFormTests.test_unsupported_glyph_rolls_back_issuance_without_missing_character_boxes budget.test_office_form_concurrency
python .tmp/my_work_sqlite.py budget.test_office_form_retention
```

Synthetic browser/PDF PASS: preparation, independent issue, retained download,
successor preservation and a 420px preparation view. Console has zero errors/warnings.
Screenshots: `output/playwright/office-form-prepare-mobile.png` and
`output/playwright/office-form-issued.png`. The final synthetic two-page copy at
`output/pdf/synthetic-office-form-2.pdf` was rendered and both pages inspected; SHA-256
`446ec93e998bd653d2124483d33e640209feeef4255b5d8e2d53f4334dab2b51`.
A six-page layout-only stress copy retained all 25 distinct long-description rows,
five categories, maximum-width numbers and Unicode. Visual review exposed and fixed
an orphaned category heading; all final pages were re-rendered/inspected. Poppler
reports unavailable optional display fonts, but the embedded Noto glyphs render
correctly and extraction reproduces names/peso signs. Stress data is not a financial
fixture or an issued record. Browser/server closed (sessions 37985/31581 collected).
Compilation, isolated migration drift, whitespace and 475 local documentation links
PASS. Owned native fixture stopped after final teardown; 33308/8791 listeners clear.
No runner remains active. Operator SQLite hash remains
`C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C`.
No operator migration or publication. Full release regression NOT RUN - OUT OF SCOPE
for this checkpoint; it remains required before publication. Real printer, signed
form receipt, LGU acceptance and Form 1 remain unperformed/unimplemented.

### Captured office identity before Form 2 (2026-10-11)

Schema-7 planning schedules retain each row's office ID and captured office name,
including proposed-only and historical-only objects. Proposal capture and selected
source evidence must agree with the captured center mapping. A mapping change
detected between source validation and projection is rejected. This is evidence
consistency checking, not a universal lock on all organizational setup changes.

New historical forecasts retain office identity with their source row. Clearing a
source preserves that identity and the existing unresolved-forecast guard, without
assigning the forecast to today's mapped office. Unmapped proposal rows retain a
missing office; the requesting department is never used as a guessed replacement.
The two captured-office CSV columns apply only to schema 7. Submitted snapshots
and older-schema export shapes remain unchanged after office renaming/remapping.

The [Form 2 issuance boundary](FINANCE_BUDGET_ACTUALS_CONTRACT.md) now specifies
complete office/fund coverage, explicit missing/zero treatment, signatory evidence,
unsigned physical-signing copies, immutable output versions and separate Form 1
reconciliation. These are next implementation requirements, not completed issuance.
The retained reference PDF hash still matches the audit. No fresh amendment search,
physical signature, accepted printed form or LGU acceptance is claimed.

PASS SQLite: 71/71, no skips, 75.725s, exit 0; both stores destroyed, session
50946 collected (`.tmp/budget-office-identity.log`). PASS native MySQL: 84/84,
no skips, 103.084s, exit 0; both stores destroyed, session 62423 collected
(`.tmp/budget-office-identity-native.log`). Coverage includes captured native/external
office identities, setup remapping after submission, mapping changes injected after
source validation, missing offices, older-schema CSV shape, orphaned forecasts,
consolidation and existing source-selection/forecast races. The injected mapping
checks do not establish serialization with every organizational setup writer.

Commands (documented Python 3.11 environment):
```text
python .tmp/my_work_sqlite.py budget.test_schedule_office_identity budget.test_actuals_office_scope budget.test_actuals_objects budget.test_actuals_consolidation budget.test_planning_context
python .tmp/retrieval_native.py budget.test_schedule_office_identity budget.test_actuals_office_scope budget.test_actuals_objects budget.test_actuals_consolidation budget.test_planning_context budget.test_actuals_selection_concurrency budget.test_historical_forecast_concurrency
```

No new model or migration; isolated migration drift and compilation PASS. Whitespace
and 473 local documentation links PASS. Owned native fixture stopped after teardown;
ports 33308/8791 are clear and no runner remains active. Operator SQLite hash remains
`C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C`.
Full release regression NOT RUN - OUT OF SCOPE for this isolated identity/export
checkpoint and remains required before publication. Browser/PDF checks NOT RUN -
OUT OF SCOPE: HTTP CSV paths are tested and no UI or form renderer was changed.
No operator migration, release, merge or deployment was performed.

### Historical object forecasts (2026-10-11)

Migration 0014 adds `BudgetVersion.historical_forecasts`. Forecasts identify the
fund/center/account/normalized object, retain selected actual rows and their digest,
and require an explicit nonnegative amount (including zero), planning-year date,
basis, actor/time and change reason. Existing proposal-line estimates stay separate.
The signed 24-hour editor pins user/version/object/state/source; mutation holds the
BudgetVersion before existing Fund validation, denies UAT mutation and rejects
replay, stale evidence, wrong scope and submitted-state editing.

Clearing a selected source keeps its forecast visible with a review problem rather
than dropping it. Source replacement requires deliberate forecast review; a new
proposal line for that object requires reconciliation and clearing the historical
forecast. Neither situation contributes a total or passes submission unresolved.
Clearing retains the prior forecast in audit history and remains possible when the
current source is invalid. Zero and missing remain distinct.

Schema-6 context freezes forecasts, source rows and review state at submission.
Schedule and CSV retain amounts, dated basis and current/stale/missing state;
earlier schemas and exports are unchanged. Consolidation copies only approved
submitted forecasts and retains source-proposal/checksum origins; overlapping
historical forecasts are rejected instead of silently added. Forecasts are planning
evidence, not certification, appropriation or physical officer signatures.

PASS SQLite: 59/59, no skips, 70.670s, exit 0; both stores destroyed, session 20427
collected (`.tmp/budget-historical-forecasts.log`). PASS native: 62/62, no skips,
87.152s, exit 0; both stores destroyed, session 73190 collected
(`.tmp/budget-historical-forecasts-native.log`). Native coverage includes concurrent
forecast saves and forecast-clear versus submission, retaining one consistent
snapshot, plus the existing selection race. Migration preflight/populated tests
now restore the latest schema after exercising migration 0013; both backends pass.
The final CSV review-state column was added after these suites started. Focused
SQLite export/frozen/stale checks PASS: 2/2, no skips, 3.846s, exit 0; both stores
destroyed, session 72889 collected (`.tmp/budget-forecast-export-final.log`).

```text
python .tmp/my_work_sqlite.py budget.test_historical_forecasts budget.test_actuals_office_scope budget.test_actuals_objects budget.test_actuals_consolidation budget.test_planning_context budget.test_version_identity_migration
python .tmp/retrieval_native.py budget.test_historical_forecasts budget.test_actuals_office_scope budget.test_actuals_objects budget.test_actuals_consolidation budget.test_planning_context budget.test_version_identity_migration budget.test_historical_forecast_concurrency
python .tmp/my_work_sqlite.py budget.test_historical_forecasts.HistoricalForecastTests.test_forecast_is_separate_dated_frozen_and_exported budget.test_historical_forecasts.HistoricalForecastTests.test_changed_certification_requires_deliberate_forecast_review
```

Synthetic browser PASS: populated migration 0014 preserved existing proposal/source
snapshots and generated identities (before/after digest
`3ba928503f6f706a7cc348a5036b5fc780d73c5d38a8882dfa9efeb5f30af102`). Clerk entered
30 against GSO-HISTORY actual 40; schedule and final downloaded CSV show total 70
and proposed zero, with dated basis and current review state. Desktop schedule and
420px editor screenshots were inspected: `output/playwright/budget-historical-forecast-schedule.png`
and `output/playwright/budget-historical-forecast-mobile.png`. Browser console clear.
This does not establish complete mobile workflow, printer or LGU acceptance.

Compilation and isolated migration drift pass. Operator DB hash unchanged; no
operator migration, release or deployment. Browser/server closed; owned MySQL
stopped after teardown; no runner remains. Broader Finance release regression,
coverage/signatory decisions, issued Form 2, joint Form 1 and operational/LGU gates
remain unfinished. Missing forecasts are still explicit incomplete context; this
checkpoint does not claim complete office forms.

### Represented-office discovery and retained object schedule (2026-10-11)

The selector discovers additional historical funds/centers for offices represented
by the requesting department, proposal lines in the fiscal-year ledger, or same-call,
same-owner consolidation sources. External scope discovery remains Budget-owner
specific; native discovery uses the latest certified fund/period and verifies its
retained payload. Only the represented offices' currently mapped centers appear.
Discovery is advisory: actual selection still validates exact source currency and
scope under proposal/Fund locks. No unrelated office or ledger is newly authorized.
Submitted pages show retained choices without discovering subsequent evidence.

New schema-5 planning contexts retain full selected choices and an object-level
schedule. Group by fund/center/account/normalized object class; preserve every source
row and proposal/estimate basis. Historical-only rows show proposed zero explicitly
as "No proposal line"; absent actuals or second-half estimates remain missing and
cannot produce a current-year total. Different source/proposal classes remain
separate rows. Earlier context schemas are not backfilled or relabeled. Drafts with
no proposal amounts may inspect their requesting office's certified history.

The proposal page shows the schedule and a dedicated archived CSV with retained
evidence. Both use frozen schema-5 context after submission and existing scoped
read/export behavior. Existing planning comparison exports keep their earlier
contract. Consolidation must explicitly resolve retained complete-scope origins
even when that historical fund/center has no proposed line; source links preserve
the represented office needed to select that evidence. No default source silently
replaces it. Legacy origins retain their prior scope behavior.

This is selected historical context, not issued Form 2 or complete office acceptance.
Historical-only forecast entry, coverage/signatory decisions, retained Form 2 and
joint Form 1 reconciliation remain open. No source absence is certified zero.

SQLite PASS: 75/75, no skips, 86.264s, exit 0; both stores destroyed, session 46084
collected (`.tmp/budget-office-scope.log`). This covers new cross-center/fund history,
unrepresented-office rejection, empty-proposal context, historical consolidation,
frozen schedule/CSV, legacy export refusal and dependent source/planning/adoption
regressions. Native PASS: 76/76, no skips, 94.819s, exit 0; both stores destroyed,
session 82954 collected (`.tmp/budget-office-scope-native.log`), including the native
selection/submission race. Final SQLite object assertions PASS: 2/2, no skips,
4.694s, exit 0; both stores destroyed, session 15412 collected
(`.tmp/budget-office-objects-final.log`). These additional assertions were added after
initial suite discovery and check the multi-object schedule totals and unmatched
historical-class row; production code is the same as the full native run.
Compilation, isolated migration drift, whitespace and 468 documentation links PASS.
Operator database SHA-256 remains unchanged. Browser/server closed and owned MySQL
stopped after teardown; no test runner remains. No new migration, release or deployment.
Broad Finance regression NOT RUN - OUT OF SCOPE for this incremental checkpoint;
required before publication and completion.

Synthetic browser PASS: select GSO-HISTORY from discovered scopes, inspect its 40 FE
actual with no proposed line, make a signed choice, return to the proposal, and
download the CSV. The schedule/CSV retain 60 MOOE in GSO plus 40 FE in GSO-HISTORY,
separately from the two new proposal rows; all absent forecasts remain missing.
`output/playwright/budget-office-object-schedule.png` was visually inspected; downloaded
CSV rows checked; browser console zero errors/warnings. This is desktop synthetic
evidence, not mobile, printer, operational or LGU acceptance.

```text
python .tmp/my_work_sqlite.py budget.test_actuals_office_scope budget.test_actuals_complete_scope budget.test_actuals_objects budget.test_actuals_views budget.test_actuals_consolidation budget.test_planning_context accounting.test_budget_actuals
python .tmp/retrieval_native.py budget.test_actuals_office_scope budget.test_actuals_complete_scope budget.test_actuals_objects budget.test_actuals_views budget.test_actuals_consolidation budget.test_planning_context accounting.test_budget_actuals budget.test_actuals_selection_concurrency
python .tmp/my_work_sqlite.py budget.test_actuals_objects.NativeObjectSelectionTests.test_distinct_objects_sum_once_and_survive_submission_export budget.test_actuals_objects.NativeObjectSelectionTests.test_unmatched_object_set_retains_evidence_but_does_not_invent_zero
```

### Complete selected-scope evidence and populated upgrade (2026-10-11)

New signed previews and explicit source selections retain every certified account
within the chosen fund/responsibility-center/period, even with no proposal line.
Native rows carry retained account codes/titles; external candidates derive account
identities from the adopted certificate, not today's account catalog or proposal.
Both routes still verify current scope, decision and source evidence under Fund
locks. Other office rows remain excluded. New choices carry `complete_scope`;
legacy choices reproduce their original account-filtered hashes without rewriting.
The screen labels accounts without proposal lines. Existing proposal comparisons
and submitted CSVs keep their narrower contract and frozen behavior.

This was a prerequisite, not complete office/Form 2 implementation. At that checkpoint,
scopes still originated from proposal fund/center lines; the subsequent discovery and
schedule checkpoint above extends this boundary. Whole offices with additional historical
centers/funds, forecasts without proposal lines, retained output issuance and Form 1
joint certification remain unfinished. No missing amount becomes certified zero.
Retained DBM LBM 94 PDF hash was rechecked against the source audit; pages 23–24
were rendered and visually inspected for Form 2 columns and signatory instructions.

Browser upgrade initially FAIL - CAUSED BY CURRENT WORK: migration 0013's ordinary
AddField could not add a STORED generated column to a populated SQLite table.
Earlier fresh-database and duplicate-preflight tests had not covered that success
path. Migration 0013 now uses Django's SQLite table-copy/rebuild path, retaining the
standard native operation and duplicate preflight. Added a populated migration test
for combined/non-combined values, retained proposal lines, audit payload and identity.
The existing populated synthetic browser fixture subsequently upgraded successfully.
No operator migration or financial evidence repair was performed.

Synthetic browser PASS: account absent from the new proposal remains visible with
40 FE / 60 MOOE actuals, signed selection succeeds, origin requirement clears,
retained evidence remains available; console has zero errors/warnings. Screenshot:
`output/playwright/budget-historical-scope.png` (visually inspected). Desktop check
only; this does not establish whole-office, mobile, printer or LGU acceptance.

Source-selection regression PASS: SQLite 59/59, no skips, 71.629s, exit 0; both
stores destroyed, session 30904 collected (`.tmp/budget-complete-scope.log`). Native
60/60, no skips, 72.887s, exit 0; both stores destroyed, session 58706 collected
(`.tmp/budget-complete-scope-native.log`), including the selection/submission race.
Populated-upgrade SQLite PASS: 43/43, no skips, 23.435s, exit 0; both stores destroyed,
session 17890 collected (`.tmp/budget-populated-upgrade.log`), including both actual
migration cases, version identity and the complete budget.tests module. The source
suites began before the SQLite migration repair; the populated-upgrade suite tests
the repaired migration. Native migration/creation PASS: 11/11, no skips, 21.883s,
exit 0; both stores destroyed, session 26846 collected
(`.tmp/budget-populated-upgrade-native.log`). This includes both populated/preflight
migration cases and five native creation races. Owned MySQL fixture stopped after
teardown; browser/server also closed. No runner remains active.

```text
python .tmp/my_work_sqlite.py budget.test_actuals_complete_scope budget.test_actuals_objects budget.test_actuals_views budget.test_actuals_consolidation accounting.test_budget_actuals
python .tmp/retrieval_native.py budget.test_actuals_complete_scope budget.test_actuals_objects budget.test_actuals_views budget.test_actuals_consolidation accounting.test_budget_actuals budget.test_actuals_selection_concurrency
python .tmp/my_work_sqlite.py budget.test_version_identity_migration budget.test_version_identity budget.tests
python .tmp/retrieval_native.py budget.test_version_identity_migration budget.test_version_identity budget.test_version_identity_concurrency
```

Compilation, isolated migration drift, whitespace and 468 documentation links PASS.
Operator database SHA-256 remains unchanged. Broad Finance regression NOT RUN - OUT
OF SCOPE for this incremental checkpoint; required before release. No release,
master integration, operational or LGU acceptance is claimed.

### Combined-version identity and creation boundary (2026-10-11)

Budget migration 0013 adds a generated version identity only when the requesting
office is null, with a normal unique constraint on annual call/type/generated number.
The existing non-null office constraint remains. A preflight rejects historical
combined duplicates without renumbering, deleting or rewriting any proposal evidence.

Consolidation locks its complete source set in primary-key order without joined
call locks, then locks the shared annual call before allocating a number. This avoids
partially locking overlapping source sets before acquiring the common boundary.
Proposal transitions explicitly lock their version before the call. Manual successor
creation locks its predecessor before the call to avoid foreign-key lock inversion.
Manual draft creation shares the call lock, rechecks that the call remains published,
and returns identity conflicts as form errors after transaction rollback. A combined
proposal cannot include two approved alternatives for the same requesting office;
original alternatives and their source evidence remain untouched. Earlier consolidation
coverage that combined same-office alternatives is now intentionally superseded by
this rejection; ordinary different-office source sets remain supported.

Initial SQLite PASS: 57/57, no skips, 40.894s, exit 0; both stores destroyed,
session 98489 collected (`.tmp/budget-version-identity.log`). This includes actual
migration rollback/preflight/restore over synthetic duplicate rows, database uniqueness,
manual duplicate form behavior, source origins, planning and the full budget.tests
module. Final focused SQLite PASS: 15/15, no skips, 13.423s, exit 0; both stores destroyed,
session 90182 collected (`.tmp/budget-version-identity-final.log`). Initial native
PASS: 59/59, no skips, 52.223s, exit 0; both stores destroyed, session 91549
collected (`.tmp/budget-version-identity-native.log`), including native migration
preflight and database uniqueness. Intermediate native PASS: 8/8, no skips, 13.492s, exit 0; both stores destroyed,
session 18021 collected (`.tmp/budget-version-identity-native-final.log`).
Latest SQLite PASS: 52/52, no skips, 28.350s, exit 0; both stores destroyed, session
91355 collected (`.tmp/budget-version-identity-final2.log`). Final native PASS: 10/10, no skips,
18.340s, exit 0; both stores destroyed, session 61420 collected
(`.tmp/budget-version-identity-native-final2.log`). All six creation/selection races
pass, including approval and manual predecessor interactions added after the
intermediate native run started. Owned MySQL fixture stopped after teardown.

```text
python .tmp/my_work_sqlite.py budget.test_version_identity budget.test_version_identity_migration budget.test_actuals_consolidation budget.test_planning_context budget.tests
python .tmp/retrieval_native.py budget.test_version_identity budget.test_version_identity_migration budget.test_version_identity_concurrency budget.test_actuals_consolidation budget.test_planning_context budget.tests
python .tmp/my_work_sqlite.py budget.test_version_identity budget.test_actuals_consolidation
python .tmp/retrieval_native.py budget.test_version_identity budget.test_version_identity_concurrency budget.test_actuals_selection_concurrency
python .tmp/my_work_sqlite.py budget.test_version_identity budget.test_actuals_consolidation budget.tests
```

No operator migration or browser data mutation in this checkpoint. Compilation,
isolated migration drift, whitespace and 468 documentation links pass. Operator
database SHA-256 remains unchanged. UI layout testing NOT RUN - OUT OF SCOPE:
layout is unchanged; affected POST/form behavior is exercised through Django HTTP
tests. Full Finance release/operational/form acceptance remains open.

### Consolidated proposal source origins (2026-10-11)

Budget migration 0012 adds retained source origins to newly consolidated proposals.
Consolidation reads the approved sources under sorted source-version locks, verifies
nonempty planning snapshots against their submitted audit evidence, and captures
explicit selections and retained certified rows without consulting current ledger
amounts. Historical sources without snapshots are not backfilled. The new field is
immutable through model validation and reproduced against the consolidation audit
snapshot when checking context/selection readiness.

Every affected office/period still present in the combined proposal requires an
explicit current choice before a new planning context/submission. Conflicting native
and external evidence is retained separately; no amounts are merged and no external
default silently replaces a source. The selector displays originating approved
proposals and their evidence. Clearing a choice restores the required review; removing
all proposal lines from a scope removes the immediate requirement, while retained
origins ensure adding that scope later does not erase its review requirement.

Code inspection exposed the existing consolidated ceiling issue: a proposal without one
requesting office previously compared all lines to a zero ceiling. Such versions now
check each responsibility center's mapped office/fund/object against that office's
call ceiling. Unmapped offices receive no capacity, and spare ceilings in another
office are not pooled. Department-proposal ceiling behavior stays as before.

Synthetic browser PASS: original approved source retained → combined scope selected
→ proposal submitted for review with certified 100.00 and original source unchanged.
Screenshots `output/playwright/budget-consolidation-origins.png` and
`output/playwright/budget-consolidation-submitted.png` inspected; console clear.
Migration 0012 applied only to disposable browser/test stores. Browser/server stopped.
Compilation and isolated migration-drift check pass. Operator DB hash unchanged.

```text
python .tmp/my_work_sqlite.py budget.test_actuals_consolidation budget.test_actuals_views budget.test_planning_context budget.tests
python .tmp/retrieval_native.py budget.test_actuals_consolidation budget.test_actuals_views budget.test_planning_context budget.tests budget.test_actuals_selection_concurrency
```

SQLite PASS: 72/72, no skips, 68.967s, exit 0, both stores destroyed, session
82133 collected (`.tmp/budget-actuals-consolidation.log`). Native PASS: 73/73, no skips, 70.648s, exit 0; both stores destroyed, session
57244 collected (`.tmp/budget-actuals-consolidation-native.log`). Owned native
fixture stopped after teardown. Whitespace and 469 documentation links pass.
Scope includes six new consolidation/ceiling scenarios, existing source-choice tests,
planning context, the complete `budget.tests` module and native selection/submission
concurrency. This does not establish simultaneous consolidation-creation safety:
executive version allocation uses a nullable-office uniqueness scope and disjoint
source sets need a shared creation boundary. Review that next, including competing
source versions for one office, before publication. Full historical office rows,
retained forms and Form 1 joint certification remain open; no release or deployment.

### Budget source inspection and selection screen (2026-10-11)

The proposal links to a scope selector for its fund/office/comparison periods.
Read permission uses the existing Budget context boundary; mutation additionally
requires Budget preparation permission and excludes UAT viewers. Each candidate is
limited to the proposal office and accounts. Native/current adopted-external routes
are separate cards with certification metadata, reviewed object rows and retained
component evidence. The page does not expose the entire Accounting fund capture.

A signed 24-hour preview pins actor, proposal, state, source identity and exact row
fingerprint. POST calls the existing selection service, which rechecks source currency
and the preview fingerprint under proposal-before-Fund locks. Tampering, replay,
changed source, another actor, expired preview and submission block selection.
An explicit reason accompanies selection/clear; clearing restores the existing external
default and retains audit history. Removed proposal scopes retain an audited clear path.
Submitted proposals expose retained choices without fresh candidates or mutation forms.

The initial browser GET failed on a new account-label lookup (`name` instead of
`LedgerAccount.title`): FAIL - CAUSED BY CURRENT WORK, corrected before successful
browser validation. No financial write occurred on that failed GET. The final browser
selected the native two-object source, returned to the same scope and reproduced the
saved explanation/evidence. Desktop/mobile screenshots inspected, final console clear:
`output/playwright/budget-actuals-source-screen.png` and
`output/playwright/budget-actuals-source-mobile.png`. Only disposable fixture stores
were used. Final native tests and validation are recorded below and in CONTINUE.md.

Initial SQLite PASS: 26/26, no skips, 30.746s, exit 0, both stores destroyed, session
48193 collected (`.tmp/budget-actuals-ui.log`). Initial native PASS: 27/27, no skips,
37.304s, exit 0, both stores destroyed, session 43847 collected
(`.tmp/budget-actuals-ui-native.log`), including the existing selection/submission race.
The final pass adds expired-preview and same-permission/different-actor checks.
An overly broad expiry mock also expired login signatures: SQLite 27 tests/one fixture
failure (31.589s), native 15 tests/one identical fixture failure (20.897s); both exit 1
and both stores destroyed. The native process had loaded the test before its repair.
Final corrected SQLite PASS: 14/14, no skips, 15.066s, exit 0, both stores destroyed,
session 22547 collected (`.tmp/budget-actuals-ui-final2.log`). Final corrected native
PASS: 15/15, no skips, 20.741s, exit 0; both stores destroyed, session 97372
collected (`.tmp/budget-actuals-ui-native-final2.log`). Compilation, whitespace and
469 local documentation links pass; operator database hash unchanged. Owned browser/
server and MySQL fixture stopped after completed teardown.

```text
python .tmp/my_work_sqlite.py budget.test_actuals_views budget.test_actuals_objects
python .tmp/retrieval_native.py budget.test_actuals_views budget.test_actuals_objects budget.test_actuals_selection_concurrency
python .tmp/retrieval_native.py budget.test_actuals_views.ActualsSourceViewTests budget.test_actuals_selection_concurrency
```

No migration or posted-ledger change. Consolidation choice handling, historical rows
without proposal amounts, complete office-form issuance and Form 1 joint certification
remain unfinished. Full release regression NOT RUN - OUT OF SCOPE for this focused
screen checkpoint; still required before publication and operational acceptance.

### Multiple native object classes in Budget comparisons (2026-10-11)

Native selection retains every reviewed account/object row in its pinned fingerprint.
Account grouping sums rows once while retaining their components and common source
identity; conflicting identity metadata is rejected. Proposal/source class sets must
match before publishing an account comparison total. Mismatches preserve object-level
source evidence in the page and CSV, with no inferred class allocation or zero.
New explicit-selection contexts use schema 4; schema-2 and already retained schema-3
snapshots remain unchanged. Exact reversals retain both object rows at net zero.

SQLite PASS: 30/30, no skips, 35.057s, exit 0; native PASS: 30/30, no skips,
34.078s, exit 0. Both test stores destroyed; sessions 1769/55315 collected.
Logs `.tmp/budget-actuals-objects.log` and `.tmp/budget-actuals-objects-native.log`.

```text
python .tmp/my_work_sqlite.py budget.test_actuals_objects budget.test_planning_context accounting.test_budget_actuals accounting.test_budget_native_statements
python .tmp/retrieval_native.py budget.test_actuals_objects budget.test_planning_context accounting.test_budget_actuals accounting.test_budget_native_statements
```

Scope covers inherited source-selection checks, class matching/mismatch, submitted
snapshot/CSV immutability, exact reversals and dependent planning/calculation tests.
Synthetic browser PASS: 40.00 FE/60.00 MOOE, certified total 100.00, raw activity
100.00 once. Screenshots `output/playwright/budget-objects-desktop.png` and
`output/playwright/budget-objects-mobile.png` inspected; console zero errors/warnings.
Mobile retains horizontal table scrolling; this does not establish usability acceptance.
Browser fixture uses only `.tmp/native-statement-browser-20261011`. A helper-only
custom-User import failed before financial changes, then was corrected and rerun.
No new migration; the browser applied existing 0011 only to its disposable stores.
Final compilation, whitespace and 468 local documentation links PASS. Owned browser/
server and MySQL fixture stopped; listeners clear. Operator database SHA-256 unchanged.
Broader release regression NOT RUN - OUT OF SCOPE for this bounded comparison change;
required before publication. Selector UI, consolidation and full office forms remain open.

### Explicit Budget source selection (2026-10-11)

The service/planning-context integration adds an audited native/external choice for
each proposal fund, center and prior-year/first-half period. Budget migration 0011
stores the current selection map; Budget audit events retain each before/after
decision. Changes require an editable proposal, Budget preparation permission,
expected proposal state and explicit reason. Clearing a choice is also audited and
restores the prior default external-adoption behavior; it can remove a stale scope.

Proposal locks precede sorted shared Fund locks. Native reads validate the proposal
ledger and office, latest certified version, retained decision and current full
source fingerprint without impersonating an Accounting user. The internal coherent
capture was separated from the Accounting permission wrapper for this authorized
Budget path. External choices must reference the current adopted office certificate.
Choices retain exact row/decision identities and checksums; a changed source requires
an explicit new choice. One route replaces the other for the entire selected scope;
missing native account rows do not fall back to external rows or become zero.

Draft display/submission revalidates choices. Submitted proposals retain the exact
native row/components and certification evidence initially using planning schema 3; legacy
schema-2 source behavior and CSV headers remain unchanged. Native evidence is labeled
as native, with no inaccessible cross-office Accounting link. Later source changes
do not rewrite the submitted proposal or its CSV. Existing review validates that
the submitted snapshot remains intact.

SQLite PASS: 29 discovered, 28 passed, one native-only skip, 31.972s, exit 0;
both stores destroyed, session 36406 collected (`.tmp/budget-actuals-selection.log`).
Native PASS: 29/29, no skips, 34.895s, exit 0, both stores destroyed;
session 37764 collected (`.tmp/budget-actuals-selection-native.log`). The race proves
one competing selection and a submission snapshot consistent with the serialized
selection/clear outcome.
Selection UI and scoped inspection are covered by the newer screen checkpoint above. Consolidated proposals still need deliberate source selection; no implicit
copy/merge of conflicting office choices is implemented. The newer multi-object checkpoint below removes the initial adapter rejection while
retaining complete reviewed rows and checking class-set agreement. Issued forms and Form 1 reconciliation
remain open. No operator migration was run.
The planning comparison still concerns proposal account groups. It is not a complete
office Form 2: later office issuance must preserve historical rows even where no
new proposed amount exists. The native retained statement itself keeps the full cohort.

```text
python .tmp/my_work_sqlite.py budget.test_actuals_selection budget.test_actuals_selection_concurrency budget.test_planning_context accounting.test_budget_actuals accounting.test_budget_native_sources
python .tmp/retrieval_native.py budget.test_actuals_selection budget.test_actuals_selection_concurrency budget.test_planning_context accounting.test_budget_actuals accounting.test_budget_native_sources
python .tmp/native_attribution_manage.py makemigrations --check --dry-run
```

Scope includes five new selection/snapshot scenarios, existing Budget planning,
external adoption, coherent source capture and a native selection/submission race.
Compilation, isolated migration drift, whitespace and 468 documentation links pass.
Browser selection is NOT RUN - OUT OF SCOPE until the selector exists; broader
cross-module release regression and official/LGU acceptance remain required.
Owned MySQL fixture stopped after teardown; process/port clear. Operator database
SHA-256 unchanged. No operator migration, publication or deployment occurred.

### Native statement screens and retained evidence (2026-10-11)

The Accounting workspace now links full native version history with search and
50-row pages. Preparation displays reviewed office/account/object totals, gross
debit/credit coverage and every source line. A signed 24-hour preview pins actor,
owner, fund/period, source fingerprint and latest version; submission still rechecks
all service controls. The preparation form retains explanations on failed submission.
Fund/period are fixed hidden preparation fields with distinct IDs; the separate
preview selector is the visible scope control. Missing classification links back to
the existing expenditure review register.

Independent certification/return retains designation and review note. Superseded or
changed certified sources remain readable with a warning. Export requires current
explicit native export permission and department scope, verifies retained evidence,
and archives deterministic JSON bytes with the decision and source evidence. Later
source changes do not alter an earlier certified download. This is evidence export,
not an accepted printed LBP form, physical signature or Budget adoption.

SQLite PASS: 15/15, no skips, 24.323s, exit 0, both stores destroyed, session 96033
collected (`.tmp/budget-native-ui.log`). Native PASS: 15/15, no skips, 23.831s,
exit 0, both stores destroyed, session 67121 collected (`.tmp/budget-native-ui-native.log`).
Three HTTP scenarios cover preparation/independent certification/export, retained
bytes after source changes, preview tampering/actor/period/staleness, UAT denial,
51-version pagination/search, foreign-scope denial and CSRF/POST protection. Existing
certification and statement calculation suites also run.

```text
python .tmp/my_work_sqlite.py accounting.test_budget_native_views accounting.test_budget_native_certifications accounting.test_budget_native_statements
python .tmp/retrieval_native.py accounting.test_budget_native_views accounting.test_budget_native_certifications accounting.test_budget_native_statements
```

Synthetic Chromium PASS: prepare → independent officer certification → download.
The actual downloaded JSON retains the certification decision, 100.00 synthetic
total and both source lines. Desktop preview/decision and mobile screenshots were
inspected: `output/playwright/native-budget-preview.png`,
`output/playwright/native-budget-certified.png`, `output/playwright/native-budget-mobile.png`.
Console clear. Final hidden scope widgets/distinct IDs were verified in this browser
flow after automated tests started; they change presentation, not the posted contract.
Browser data are isolated in `.tmp/native-statement-browser-20261011`; no operator
migration or data change. Broad release regression, official printed-form fidelity
and LGU acceptance are NOT RUN - OUT OF SCOPE for this increment. Native/external
Budget selection, office-form issuance and joint Form 1 reconciliation remain unfinished.
Compilation, whitespace and 468 documentation links PASS. Owned browser/server and
MySQL fixture stopped; ports 8791/33308 and their processes are clear. Operator DB
SHA-256 unchanged; no publication/deployment occurred.

### Retained native preparation and certification service (2026-10-11)

`NativeBudgetStatement` and migration `0035_native_budget_statements` retain one
immutable full-fund/period cohort, reproducible statement, preparer, completeness
basis and supporting reference per version. This is a distinct native record, not
an external upload. The Fund row serializes version creation and decisions; the
unconditional fund/period/version identity is enforced on both databases.

Preparation requires a new explicit native permission, a completed January–June
or calendar-year period, current preview fingerprint, expected latest version and
fully reviewed classifications. Empty or unresolved sources cannot be proposed as
certified zero. Separate explicit certification permission is never inherited merely
from posting or external-adoption authority. The deciding officer must differ from
the preparer and retain designation/authority and independent coverage review.
UAT mutation denial remains mandatory. New read/export permissions are separate.

Certification rechecks the complete source fingerprint and rejects older preparations
when a newer version exists. A stale preparation can still be returned. Certified
records retain their original payload and decision; later backdated source changes
make them stale for new use rather than rewriting them. The currentness helper also
rejects superseded certified versions. This helper is an advisory read, not a locked
Budget adoption action. Shared Fund locks serialize attribution/native decisions,
but posting has no universal period lock: certification records the coherent source
read, not a guarantee against all subsequent posting. Budget adoption must repeat
the checks in its own controlled selection flow.

SQLite PASS: 21 discovered, 19 passed, two native-only skips, 22.104s, exit 0;
both stores destroyed; session 56991 collected, `.tmp/budget-native-certifications.log`.
Native PASS: 21/21, no skips, 29.224s, exit 0, both stores destroyed, session 12795
collected, `.tmp/budget-native-certifications-native.log`. The new native race proves
one version for competing preparations and one decision for competing certification
attempts; the existing attribution/capture race is also included. Migration
was generated using isolated settings; no operator migration occurred. No certification
screen, issued office output, native/external selection or Form 1 joint certification
is claimed by this service increment.

Commands:

```text
python .tmp/my_work_sqlite.py accounting.test_budget_native_certifications accounting.test_budget_native_statements accounting.test_budget_native_sources accounting.test_budget_native_certification_concurrency
python .tmp/retrieval_native.py accounting.test_budget_native_certifications accounting.test_budget_native_statements accounting.test_budget_native_sources accounting.test_budget_native_certification_concurrency
python .tmp/native_attribution_manage.py makemigrations --check --dry-run
```

Compilation, migration drift, whitespace and 468 documentation links PASS. Scope
covers new persistence/permissions/transitions, source capture, statement calculation,
and native version/decision races. Browser/output fidelity, broader release regression
and LGU acceptance are NOT RUN - OUT OF SCOPE for this internal service increment.
Native certification here is a recorded authorized system decision with explicit
authority, not proof that a physical form was signed or that the LGU accepted it.
Owned MySQL fixture stopped after teardown; its process/port are clear. Operator
database SHA-256 remains unchanged. No operator migration, publication or deployment.

### Native statement calculation (2026-10-11)

`accounting/budget_native_statements.py` calculates all office/center/account/object
rows from one trusted schema-7 cohort and the existing verified allocation projection.
It does not read newer heads or setup while calculating, filter away other offices,
or count out-of-period dependency journals as activity. Each included component pins
its exact approval and allocation. Every period financial line remains in the bridge,
with included/excluded/unresolved/unreviewed debit and credit controls reconciled to
the captured ledger. Gross columns preserve exact reversals even at net zero.

Unreviewed journals, unresolved portions and empty cohorts prevent complete
classification. Stale or invalid approvals raise the existing validation errors;
they are never silently removed from totals. Retained office metadata is used as
reviewed; inconsistent identities across grouped rows require reconciliation.
`classification_complete` describes the captured allocation coverage only. It does
not establish a complete real-world ledger, a certified zero, or officer authority.
The payload explicitly remains `certificate: false`.

This is the calculation boundary for subsequent retained native statements,
distinct certification permissions/decisions and current-source checks on Budget
selection. No native output is disguised as an externally signed document. The later
retained-service checkpoint above covers persistence and its distinct decision boundary.
Office issuance, external/native overlap and Form 1 reconciliation remain unfinished.
Validation commands (both use isolated default/Finance stores):

```text
python .tmp/my_work_sqlite.py accounting.test_budget_native_statements accounting.test_budget_attributions accounting.test_budget_attribution_reversals
python .tmp/retrieval_native.py accounting.test_budget_native_statements accounting.test_budget_attributions accounting.test_budget_attribution_reversals
```

Initial SQLite/native: FAIL - CAUSED BY CURRENT WORK, five new fixture setup errors
each (`make_call` not attached), 15 tests, 15.694s/17.088s. All required fixture
helpers were attached; the initial runs had already imported the old class. Both
initial runs exited 1 and destroyed both stores. Logs `.tmp/budget-native-statements.log`
and `.tmp/budget-native-statements-native.log` retained. A prior-period regression was
also added before rerunning. Final SQLite PASS: 16/16, no skips, 21.987s, exit 0;
both stores destroyed, session 46488 collected, `.tmp/budget-native-statements-final.log`.
Final native PASS: 16/16, no skips, 20.457s, exit 0; both stores destroyed,
session 3914 collected, `.tmp/budget-native-statements-native-final.log`.
Compilation, whitespace and 468 documentation links pass. Operator database SHA-256
unchanged. No operator migration, release or deployment occurred.
Owned MySQL fixture stopped after teardown; port 33308 and its process are clear.
Scope rationale: six statement tests plus the existing allocation and exact-reversal
suites exercise this pure calculation and its authoritative source contracts.
One test asserts zero Finance reads during projection; another asserts one during
authorized capture plus calculation. There is no schema or mutation change in this
increment. Browser, official layout, broad release regression and human acceptance
are NOT RUN - OUT OF SCOPE for this internal calculation; they remain required for
the later usable certification workflow and release gate.

Next integration boundary, verified against current code: `BudgetActualScope` owns
one external `current_version` and serializes adoption under Fund-before-scope locks.
`budget_actuals.planning_actuals` and `budget.planning_context.build_context` currently
label that evidence as an adopted external certificate. Native persistence must
retain an explicit distinct source type, resolve overlap through controlled scope
selection, and preserve already-issued external bytes and Budget snapshots. Do not
populate the existing external upload contract with generated statement bytes.
Distinct certification must recheck the full cohort and independently reviewed
allocations; new Budget selection must detect changed source coverage without
rewriting an older issued statement. Form 1's joint certification remains separate.

### Historical claim repair navigation (2026-10-11)

Unlinked liability warnings now open a read-only original-credit finder in a separate
tab, preserving entered Budget allocations. Candidates are paged by 50 and scoped
to the same owner, fund and account, with actual original posted dates no later than
the target. Earlier sources outside the Budget period remain discoverable. Search
uses journal/claim reference; neither amount nor date proves a relationship.
Generated and already-linked movements remain on their original financial workflows.
Malformed reversal lineage fails closed. An original credit points to itself.

The existing historical claim page carries validated payment context without adding
an application selection. Its existing preparation permission, complete-history
attestation and independent review remain authoritative. Invoice splits/shared
applications retain their existing routes. Approval changes captured evidence, not
posted financial lines; a fresh independently reviewed Budget classification is
required. The old signed editor is never silently rebased.

Validation commands:

```text
python .tmp/my_work_sqlite.py accounting.test_budget_claim_repair_views accounting.test_claim_attributions accounting.test_budget_unlinked_liabilities accounting.test_budget_preparation_views
python .tmp/retrieval_native.py accounting.test_budget_claim_repair_views accounting.test_claim_attributions accounting.test_budget_unlinked_liabilities accounting.test_budget_preparation_views
```

SQLite PASS: 18/18, no skips, 10.463s, exit 0; native PASS: 18/18, no skips,
11.376s, exit 0. Both stores destroyed. Logs `.tmp/budget-claim-repair.log`
and `.tmp/budget-claim-repair-native.log`; native session 99779 collected.
Actual HTTP proposal/independent approval preserves posted lines, changes the Budget
capture and leaves required source reclassification visible. Pagination/search,
nonliability/linked targets, invalid context and UAT mutation denial are covered.
The late defensive malformed-lineage exception branches have no dedicated new test;
the valid browser path was checked after those changes.

Synthetic Chromium PASS: warning → separate finder → reference search → contextual
claim form; original editor retained and applications unselected. Screenshots
`output/playwright/budget-claim-source-finder.png` and
`output/playwright/budget-claim-repair-context.png` inspected; console clear.
Browser verification did not submit another claim; full approval is covered by the
two-store HTTP tests. Broad release regression and official/LGU acceptance are
NOT RUN - OUT OF SCOPE for this unpublished navigation increment. Native certification
and Budget adoption remain open; candidates are not asserted to be actual originals.
Compilation, whitespace and 468 documentation links pass. Browser/server and owned
MySQL fixture stopped, with no listeners on 8791/33308. Canonical operator database
SHA-256 remains `C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C`.
No operator migration, commit, publication or deployment occurred.

### Paged source selection (2026-10-11)

Posted-source discovery now uses 50-row pages with an authenticated retained
selection. Page changes and searches first save current checkboxes, preserving
selections outside the page/filter. Empty search results retain the selection panel
and preparation action. Unchecking removes only that page's choices; explicit remove
also works for off-page choices. Starting a different fund/period is an explicit new
selection. The signed state binds actor/department/fund/period and exact displayed
IDs; signed-page submissions reject unseen checkbox IDs or another actor's selection.
Current eligibility is rechecked for the complete selected group, then the existing
signed preparation context is created. No attribution or ledger mutation occurs
during selection. The 250-journal mutation bound does not cap discovery totals.

Validation commands:

```text
python .tmp/my_work_sqlite.py accounting.test_budget_preparation_selection accounting.test_budget_preparation_views accounting.test_budget_preparation_pairing
python .tmp/retrieval_native.py accounting.test_budget_preparation_selection accounting.test_budget_preparation_views accounting.test_budget_preparation_pairing
```

SQLite PASS: 17/17, no skips, 19.248s, exit 0, both stores destroyed; session 9964
collected, `.tmp/budget-preparation-selection.log`. Three new HTTP scenarios use
actual posted journals to cover 102-row/three-page retrieval, cross-page selection,
empty search retention, complete preparation, unchecking/removal, token tampering,
actor/period mismatch and forged off-page choices. Existing preparation and reversal
HTTP/service regressions also run. Native PASS: 17/17, no skips, 27.997s,
exit 0, both stores destroyed; session 43021 collected,
`.tmp/budget-preparation-selection-native.log`. The owned fixture stopped after
teardown. Compilation, whitespace and 468 documentation-link checks pass.

Synthetic Chromium PASS: 59 journals over two pages, one choice per page, a search
with zero matches preserving both choices, then an editor containing both originals.
`output/playwright/budget-source-selection.png` was visually inspected. Console had
no errors/warnings. Browser and owned server closed afterward. The fixture added
55 actual synthetic posted sources only to the disposable two-store databases;
canonical operator DB hash is unchanged. Broader regression, certification and
LGU acceptance remain NOT RUN - OUT OF SCOPE for this unpublished retrieval increment.
The next preparation gap is guided historical-claim source repair, followed by
the distinct native certification and Budget adoption work.

### Explicit reversal pairing (2026-10-11)

The editor offers the actual matching original lines when an exact reversal has
duplicate financial signatures. Its signed context retains these candidates and
whether an independently reviewed predecessor is available. Ambiguous fields have
no selected default; only unique matches are preselected. Forms require a complete
one-to-one mapping. Joint inheritance forwards explicit pairs to the shared service.
Standalone inheritance rereads trusted ledger evidence, requires the original source
checksum and builds exact reviewed rows using the existing pairing service; proposal
creation then repeats the current-source/version checks under the Fund lock.

The review screen names each reversed original journal/line from the retained
ancestor evidence. Neither line position nor equal amount chooses the classification.
Tests deliberately swap identical amounts whose reviewed offices differ, and verify
the selected original office, signed amount and source-line identity survive review.
This does not alter posting history or create a certificate.

Commands:

```text
python .tmp/my_work_sqlite.py accounting.test_budget_preparation_pairing accounting.test_budget_preparation_views accounting.test_budget_preparation accounting.test_budget_joint_attributions
python .tmp/retrieval_native.py accounting.test_budget_preparation_pairing accounting.test_budget_preparation_views accounting.test_budget_preparation accounting.test_budget_joint_attributions accounting.test_budget_joint_concurrency accounting.test_budget_attribution_concurrency
```

SQLite PASS: 26/26, no skips, 16.022s, exit 0; both stores destroyed, session
71407 collected, `.tmp/budget-preparation-pairing.log`. The new test class also
executes the existing reversal regressions. Three new HTTP cases cover missing/
duplicate pairing rejection, chosen-office preservation, joint predecessor approval
and stale source rejection with retained input. Native PASS: 28/28, no skips,
24.081s, exit 0; both stores destroyed, session 1627 collected,
`.tmp/budget-preparation-pairing-native.log`. The owned fixture was stopped after
teardown. Python compilation, whitespace and documentation-link checks pass.

Synthetic browser PASS: actual equal-line fixture, blank ambiguous choices, explicit
cross-pairing, independent review and evidence download. The reviewed output visibly
preserves reversed original line 2 as excluded and line 1 as included (-500.00), with
its original office/basis. Screenshots `output/playwright/budget-reversal-pairing.png`
and `budget-reversal-pairing-review.png` were visually inspected. The final retained
source-line display was verified after browser-server restart. Console had no errors
or warnings. Browser and owned server were closed afterward. Fixture creation and
server logs use `.tmp/budget-pairing-browser-*`; only the disposable two-store fixture
was changed. Broader regression and LGU/operational acceptance remain NOT RUN - OUT
OF SCOPE for this unpublished increment. Paged selection is covered by the later
checkpoint above; guided historical-source
repair, certification and Budget adoption remain open.

### Guided preparation screens (2026-10-11)

The register now offers explicit posted-source selection by owned fund, date and
reference. All matching journals are selectable (no retrieval cap); the existing
250-journal mutation bound remains. The editor retains the signed preparation
context and accepts explicit line partitions, split amounts, office/object choices,
source component basis and only actual linked reviewed components. Uncertain amounts
start unresolved and need a supporting explanation. Allocation totals and every
financial constraint remain enforced by the shared service.

Independent review is still a separate action. Exact standalone reversals can copy
their retained reviewed predecessor; joint repairs explicitly select their same-batch
predecessor. No browser allocations replace the inherited rows. Expired authentic
contexts and invalid/stale submissions retain bound inputs without new signatures
or automatic rebasing. Forged tokens are rejected. JavaScript packages ordinary
form fields into one structured field to avoid the framework's field-count limit;
server forms and request-size controls remain in force. Browser Back restores the
enabled form state. No global request limit was raised.

Final validation commands:

```text
python .tmp/my_work_sqlite.py accounting.test_budget_preparation_views accounting.test_budget_preparation accounting.test_budget_attribution_views accounting.test_budget_joint_attributions
python .tmp/retrieval_native.py accounting.test_budget_preparation_views accounting.test_budget_preparation accounting.test_budget_attribution_views accounting.test_budget_joint_attributions accounting.test_budget_joint_concurrency accounting.test_budget_attribution_concurrency
```

Final SQLite PASS: 23/23, no skips, 10.726s, exit 0, both stores destroyed;
session 60539 collected, `.tmp/budget-preparation-ui-final.log`. Six HTTP cases
cover split submission/replay, invalid totals/expiry with retained inputs,
CSRF/UAT/POST-only mutation, 102 allocations exceeding 1,000 ordinary fields,
standalone reviewed reversal and joint predecessor repair. Final native PASS:
25/25, no skips, 16.860s, exit 0, both stores destroyed; session 68681 collected,
`.tmp/budget-preparation-ui-final-native.log`. The owned fixture was stopped after
teardown. Python compilation, whitespace and 468 documentation-link checks pass.
Earlier selections passed SQLite 21/21 (8.523s) and native 23/23 (22.661s),
but predate the large-form and standalone-mirror cases; those are not the final gate.

Synthetic Chromium PASS: source selection → new split row → pending proposal →
independent review → retained evidence download. All three unresolved allocations
remained explicit after review. Screenshots under `output/playwright/` include
`budget-preparation-editor.png` and the corrected `budget-preparation-mobile.png`.
Mobile textarea overflow found during inspection was fixed and rechecked after
server restart; the final style change does not change validation. Console had no
errors or warnings during the completed flow. Browser/server were stopped afterward.
The fixture uses only disposable databases at `.tmp/budget-review-browser-20261011`.
The canonical operator DB hash is unchanged.

The subsequent pairing checkpoint above resolves the duplicate-signature editor
gap recorded at this checkpoint. Historical claim repair
needs a guided original-source selection/link. Source selection pagination and its
retained selection are covered by the later checkpoint above.
Broader regression, official certification, Budget adoption and LGU/operational
acceptance remain unfinished. This checkpoint is not full preparation completion
or a production gate. No operator migration, release or deployment.

### Guided preparation submission boundary (2026-10-11, focused validation passed)

`budget_preparation` creates an actor/department-bound, signed 24-hour editor context
while holding the same Fund lock as proposal creation. It retains the selected
period journals and financial-line labels, current proposal versions, coherent
source checksum and office choices. Actual claim applications expose only their
reviewed source components, with exact source-approval identities and application
shares. Missing classifications remain visible warnings; unlinked liability lines
remain explicit. This is not an accepted browser-supplied ledger capture.

Submission authenticates the context and current prepare permission, requires the
complete selected group and restores expected versions from the signed context.
It delegates all partitions, claim binding, reversal pairing and explicit same-batch
inheritance to the existing proposal service. Optional office-choice pinning checks
the exact office data used by normalization, so changing setup cannot silently
retarget an open editor. Existing internal callers retain their original contract.
No new models, migrations, posting authority or certificate status are introduced.

This module is the trusted submission boundary. The later initial UI and its
remaining workflow gaps are recorded above; backend tests alone do not prove usability.

Validation commands:

```text
python .tmp/my_work_sqlite.py accounting.test_budget_preparation accounting.test_budget_attributions accounting.test_budget_joint_attributions accounting.test_budget_attribution_views
python .tmp/retrieval_native.py accounting.test_budget_preparation accounting.test_budget_attributions accounting.test_budget_joint_attributions accounting.test_budget_attribution_views accounting.test_budget_joint_concurrency accounting.test_budget_attribution_concurrency
```

SQLite PASS: 22/22, no skips, 12.647s, exit 0, both stores destroyed, session
92793 collected. Log `.tmp/budget-preparation-context.log`. Six new integration
cases cover retained splits/replay, tampering/expiry/actor/UAT denial, selected-group
and version overrides, source/office staleness, actual components with joint repair,
and missing/forged component evidence. Native PASS: 24/24, no skips, 26.483s,
exit 0; both stores destroyed and session 91829 collected. Log
`.tmp/budget-preparation-context-native.log`; it adds the two existing proposal/
review concurrency modules. The owned MySQL fixture was stopped after teardown.
This checkpoint changes submission validation, not
schema or ledger persistence. Broader application regression and browser preparation
acceptance remain NOT RUN - OUT OF SCOPE until the editor is wired to screens.

### Whole-batch review screens (2026-10-11)

Accounting now links to a department-scoped expenditure-review register. Search
matches journal/evidence/preparer and retains the complete matching batch; fund,
period and decision filters preserve pagination and all versions. Invalid filters
show errors instead of broadening results. Detail verifies retained checksums and
one coherent group decision, renders every allocation and exposes unresolved
coverage. Explicit review/export permissions and UAT mutation denial remain in force.

An independent reviewer records or returns the whole batch through the existing
Fund-locked service. Stale-source failures preserve the review note and write no
partial decisions. CSRF, POST-only mutation, self-review and cross-department
restrictions are tested. The retained JSON export includes original source snapshots
and decisions, identifies itself as classification-only, archives its exact bytes
and rechecks current authority. Later decisions do not rewrite earlier downloads.
No signed certificate or official form equivalence is claimed.

Validation PASS (isolated two-store Python 3.11 wrappers):

```text
python .tmp/my_work_sqlite.py accounting.test_budget_attribution_views accounting.test_budget_attributions accounting.test_budget_joint_attributions accounting.test_budget_unlinked_liabilities accounting.test_budget_actuals
python .tmp/retrieval_native.py accounting.test_budget_attribution_views accounting.test_budget_attributions accounting.test_budget_joint_attributions accounting.test_budget_unlinked_liabilities accounting.test_budget_actuals accounting.test_budget_joint_concurrency accounting.test_budget_attribution_concurrency
```

SQLite: 32/32, no skips, 32.146s, exit 0; native MySQL 8.4.11: 34/34,
no skips, 44.608s, exit 0. Both stores destroyed and session 88991 collected.
Logs `.tmp/budget-review-ui.log` and `.tmp/budget-review-ui-native.log`.
The five HTTP tests cover complete-group search/pagination, preserved export bytes,
stale review/whole-group return, permission/owner/UAT restrictions, CSRF and tampering.
The scope includes the affected review service and existing actuals boundary, with
native competing-submission/review cases. Full application regression remains
NOT RUN - OUT OF SCOPE for this unpublished UI increment and is still required
before feature completion/publication.

Synthetic Chromium browser PASS on isolated loopback 8791: search for the second
journal retained both group members; pending export downloaded; the independent
reviewer recorded both decisions; unresolved coverage stayed visible; the maker
could read the retained decision without export/review controls. Desktop and
390-pixel mobile screenshots were inspected; tables retain horizontal scrolling.
Browser console reported zero errors/warnings. Evidence under `output/playwright/`
and `.playwright-cli/`; synthetic databases/exports under
`.tmp/budget-review-browser-20261011`. Browser and owned server stopped afterward.
The final template wording/contrast edits were verified by browser reload after
server restart. This is not real office usability or printer/form acceptance.
The Playwright wrapper help encountered a Windows UV_HANDLE_CLOSING shutdown
assertion; the already-installed CLI completed actual browser commands successfully.

Next implement the guided preparation and dependency-repair editor, then native
office certification, distinct joint summary certification and Budget adoption.
Do not use the current review approval as complete source coverage. Production
remains NO-GO; no operator migration, master integration or deployment occurred.

### Joint reversal repair (focused validation passed)

The source-successor reproduction passed: changing the approved source component
stales both its payment and return. Updating the payment alone fails connected
usage validation; preparing the return alone fails its predecessor check. An
implicit combined batch remains rejected. Evidence: one isolated SQLite test,
1.980s, exit 0, both stores destroyed, `.tmp/budget-joint-reproduction.log`.

An explicit `inherit_from` now selects the immediate physical reversal predecessor
in the same proposal batch. The server prepares parents first, copies their exact
financially mirrored allocations and retains their real proposal UUID/checksum.
It does not fabricate approval fields. Migration 0034 stores this immutable map;
empty maps are omitted from legacy proposal projections and checksum payloads.
Capture schema 6 distinguishes `proposal_dependency` from an approved attribution.

Independent review verifies the complete pending dependency chain before any
decision writes. All decisions share one review time and the existing Fund lock;
connected dated usage runs before commit and rolls back the entire group on failure.
Detached projection requires the exact approved dependency versions and same batch
decision. A later predecessor successor invalidates current dependent use while
retained older captures remain reproducible. Original source components and their
non-reversal applications still require separate review batches.

Six regression cases cover repair, transitive reversal chains, source change,
self-review/return, tampering and legacy empty-map checksums. A native race checks
that competing reviewers create only one complete group decision. Current runs:
SQLite `.tmp/budget-joint-review.log` PASS: 59 discovered, 58 passed, one native-only
skip, 205.853s; both stores destroyed. Native `.tmp/budget-joint-review-native.log`
PASS: 62/62, no skips, 224.559s, exit 0; both stores destroyed. Session 83318
collected. The new competing-review race makes exactly one complete approved
decision, with one review timestamp and valid connected usage. The owned MySQL
fixture was shut down after teardown. Isolated
`python .tmp/native_attribution_manage.py makemigrations --check --dry-run` PASS,
no model drift. No operator migration or deployment.
Compilation, whitespace and 468 documentation links pass; the canonical operator
database SHA256 remains unchanged.

Joint checkpoint commands (documented Python 3.11 environment):

```text
python .tmp/my_work_sqlite.py accounting.test_budget_joint_attributions accounting.test_budget_component_usage accounting.test_budget_application_components accounting.test_budget_reviewed_components accounting.test_budget_claim_components accounting.test_budget_claim_links accounting.test_budget_claim_sources accounting.test_budget_attributions accounting.test_budget_attribution_reversals accounting.test_budget_native_sources
python .tmp/retrieval_native.py accounting.test_budget_joint_attributions accounting.test_budget_joint_concurrency accounting.test_budget_component_usage accounting.test_budget_component_usage_concurrency accounting.test_budget_application_components accounting.test_budget_reviewed_components accounting.test_budget_claim_components accounting.test_budget_claim_links accounting.test_budget_claim_sources accounting.test_budget_attributions accounting.test_budget_attribution_reversals accounting.test_budget_attribution_concurrency accounting.test_budget_native_sources
```

Scope: exact proposal/review dependency repair, legacy evidence compatibility,
connected dated usage and affected source/claim/attribution boundaries. Broader
application regression and browser/operational acceptance remain NOT RUN - OUT OF
SCOPE for this unpublished backend increment and required before feature completion.

### Journal partitions

Unlinked-liability inclusion reproduced an actual gap: the posted payment was
accepted without exact original proof. The required-rejection test failed with
`ValidationError not raised`, 1 test, 0.144s, exit 1, both stores destroyed; session
`73710` collected, `.tmp/budget-unlinked-reproduction.log`. This expected red test
identifies missing validation in the unpublished implementation.
Schema 7 now rejects inclusion of any unlinked liability line, regardless of its
chosen inclusion purpose or financial sign. The check runs in the shared binding
path during proposal, independent review and current projection. Existing historical
claim review supplies the resolution route without changing posted lines or adding
a second hold. Explicit independently reviewed exclusions and unresolved treatment
remain available. This is a source-proof rule, not automatic certification of every
exclusion or native expenditure output.
Schema 1–6 captures retain their previous read interpretation. Only trusted retained
evidence may use that path; new preparations/reviews always capture current schema 7.
Five new tests exercise rejection, historical recovery/return, unchanged financial
lines, one-read output, exclusions/unresolved amounts and legacy-read compatibility.
SQLite PASS: 67 discovered, 66 passed, one native-only skip, 167.999s, exit 0,
both stores destroyed; session `99625` collected, `.tmp/budget-unlinked-coverage.log`.
Native PASS: 71/71, no skips, 222.190s, exit 0, both stores destroyed; session
`39006` collected, `.tmp/budget-unlinked-coverage-native.log`. Joint-review,
dated-capacity, attribution and coherent-capture races pass. The owned fixture was
shut down after teardown; no runner remains. Compilation, whitespace and 468 local
documentation links pass. Operator DB hash is unchanged. No new migration or deployment.

```text
python .tmp/my_work_sqlite.py accounting.test_budget_unlinked_liabilities accounting.test_budget_opening_components accounting.test_budget_joint_attributions accounting.test_budget_component_usage accounting.test_budget_application_components accounting.test_budget_reviewed_components accounting.test_budget_claim_components accounting.test_budget_claim_links accounting.test_budget_claim_sources accounting.test_budget_attributions accounting.test_budget_attribution_reversals accounting.test_budget_native_sources
python .tmp/retrieval_native.py accounting.test_budget_unlinked_liabilities accounting.test_budget_opening_components accounting.test_budget_joint_attributions accounting.test_budget_component_usage accounting.test_budget_application_components accounting.test_budget_reviewed_components accounting.test_budget_claim_components accounting.test_budget_claim_links accounting.test_budget_claim_sources accounting.test_budget_attributions accounting.test_budget_attribution_reversals accounting.test_budget_native_sources accounting.test_budget_joint_concurrency accounting.test_budget_component_usage_concurrency accounting.test_budget_attribution_concurrency accounting.test_budget_native_capture_concurrency
```

Scope covers all affected attribution/source/component/claim boundaries and the
capture-version change. Broad application, browser, official-form and LGU acceptance
remain NOT RUN - OUT OF SCOPE for this unpublished backend increment and required
before the full feature can be considered complete.

The structural-source increment passes focused SQLite/native validation. A database-free
reproduction demonstrated that an original excluded opening liability could not
retain explicit component basis (`.tmp/budget-opening-reproduction.log`, exit 0).
The rule now separates this source evidence from period expenditure: independently
reviewed excluded original liability components may describe future applications,
while opening/closing/direct-equity movements and their reversals still cannot be
included in period expenditure. No principal basis is inferred from an account.

The new integration fixture stages an opening CSV, independently approves, posts
and reconciles it through existing services, then reviews its actual historical
claim identity. Tests distinguish a later principal component from an already
recognized expense component, retain an outside-period opening source in one read,
preserve original lines and old output after a return, reject missing basis and
prevent second expenditure recognition. A pure test retains the structural
inclusion prohibition for every supported structural source type.
SQLite PASS: 31/31, no skips, 70.176s, exit 0, both stores destroyed; session `59134`
collected, `.tmp/budget-opening-components.log`. Native PASS: 33/33, no skips,
97.984s, exit 0, both stores destroyed; session `57257` collected,
`.tmp/budget-opening-components-native.log`. Both joint-review and dated-capacity
races pass. The owned MySQL fixture was shut down after teardown. No new migration.
Immediate database-free rule check PASS: 1/1, 0.013s, exit 0, no database setup;
`python .tmp/my_work_sqlite.py accounting.test_budget_opening_components.StructuralComponentNormalizationTests`,
`.tmp/budget-structural-normalization.log`, session `48762` collected.

```text
python .tmp/my_work_sqlite.py accounting.test_budget_opening_components accounting.test_budget_joint_attributions accounting.test_budget_component_usage accounting.test_budget_application_components accounting.test_budget_reviewed_components accounting.test_budget_attribution_reversals
python .tmp/retrieval_native.py accounting.test_budget_opening_components accounting.test_budget_joint_attributions accounting.test_budget_component_usage accounting.test_budget_application_components accounting.test_budget_reviewed_components accounting.test_budget_attribution_reversals accounting.test_budget_joint_concurrency accounting.test_budget_component_usage_concurrency
```

Scope: the changed original-credit declaration rule and dependent component,
application, reversal, dated-usage and joint-review contracts. Broader regression,
usable preparation/review screens and native certification remain required before
publication; this increment does not establish unlinked-liability completeness.

`BudgetExpenditureAttribution` retains one journal's complete proposed partition,
financial/source snapshot and checksum, preparation identity, version and independent
decision. Each journal has one current approved head across all offices. Ordinary
database uniqueness protects journal/version and batch/journal identity on MySQL as
well as SQLite. An attribution is metadata over unchanged posted lines.

Batch proposal and review share the existing Fund row lock. No new classification
writer may bypass that serialization. Each proposal supplies its expected latest
version; retries/stale submissions cannot silently supersede another proposal.
Review validates the whole batch before changing any head. An older submitted
version cannot replace a newer proposal, and maker/self-review and Finance UAT
mutation are denied. Specific read/prepare/review/export permissions are distinct
from certification authority.

Components must exactly partition every positive financial line across included,
excluded and unresolved dispositions. Included rows retain explicit purpose, office,
object class, original account and sign. Excluded/unresolved rows cannot smuggle in
an office expenditure allocation. Two offices cannot each consume the whole same
line. Reviewed unresolved amounts remain unresolved, not zero or certified coverage.
Account classes constrain explicit choices; they do not select or approve a purpose.

Native capture schema 7 joins current attribution metadata in the same Finance
statement as financial evidence. `reviewed_allocations` verifies the captured
financial source, proposal and independent decision without rereading head pointers.
Schema 1/2/3/4/5/6 evidence remains verifiable and immutable, but new capture includes the
additional attribution state and therefore requires a refreshed comparison.
Source snapshots for classification omit current attribution metadata, avoiding
self-referential checksums. Existing cash-flow checksum formats are unchanged.

The claim-evidence extension passes focused SQLite/native checks. One joined
Finance statement also retains current historical claim heads, invoice slices and
complete shared proposal payloads. Joined invoice rows are assembled into distinct
financial lines before controls are calculated. Linked original/application journals
outside the period enter `claim_sources`, not period activity. Native and historical
relationships are retained, including historical applications with no native origin
field. Dependency closure also retains reversal ancestors; missing/out-of-scope
references remain explicit issues instead of triggering later evidence reads.

Per-journal financial fingerprints follow directed dependencies: an application
depends on its original; a reviewed historical schedule retains all its members.
A later native payment changes cohort coverage without forcing reclassification of
an unchanged original expense solely because a new application now points to it.
Full timestamp precision is retained in schema 3. Capturing these decisions alone
does not prove valid settlement exclusion or native certification; detached source
verification is implemented below, while application classification remains open.
`verified_claims` implements detached source/decision checking and passes its initial
SQLite tests. It reproduces established journal/claim snapshots
from captured rows, reuses existing approval/proposal checksum payload builders
without ORM access, and requires every current shared member to reproduce the same
proposal and independent decision. It does not authenticate arbitrary client data;
only trusted server captures or retained artifacts may drive financial workflows.
Submission, independent approval and reviewed projection now invoke this verifier,
with focused SQLite/native integration tests passing. Mutation checks follow the selected journal dependencies,
so an unrelated broken claim does not block another journal's preparation. This
guards source validity, not expenditure recognition/settlement deduplication.

The schema-4 extension passes focused SQLite/native tests. A single version/slice join
replaces the current-head-only claim join, and explicit head IDs select current
records. Only versions actually referenced by posted allocation envelopes, plus
their complete older shared groups, enter `retained_claim_attributions`. Unreferenced
drafts/history stay out of returned evidence. Financial-source fingerprints separately
retain the exact pins used by their directed dependency set, avoiding reclassification
of an unchanged original merely because a later invoice payment pins its approval.
Schema 5 additionally retains original posted audit events from the same Finance
statement, with event and financial-line deduplication. Detached verification now
checks exact older decisions and complete groups, compatible current invoice rows,
positive complete shares, original posting audit actor/allocation evidence and
exact predecessor shares. These checks pass focused SQLite/native validation.
They establish source proof, not the expenditure recognition/settlement decision.

`budget_claim_links.application_links` now projects known application amounts from
verified capture, with SQLite/native checks passing. It preserves native whole/invoice links, reviewed
historical/shared amounts, exact old invoice approvals and reversal signs; linked
shares must reproduce the complete financial line once. Conflicting native and
historical ownership is rejected. Original-credit identity, account, dates and
reversal predecessor links are checked. Unlinked liability lines remain explicit.
This projection neither assigns expenditure purpose nor calculates certified totals;
it supplies the source amounts needed by the still-unimplemented deduplication rule.

`budget_claim_components.validate_usage` is a pure calculation primitive used by
the connected approval gate below. Its inputs must be complete verified
posted movements tied to exact reviewed components; it does not authenticate or
infer those inputs. Components share dated capacity across offices, and inclusion
requires an explicitly eligible principal basis. Exact reversals preserve amount,
component, office, purpose and object class; source cancellations adjust capacity
on their actual dates. Later returns cannot repair an earlier overuse. Iterative
lineage checking avoids an artificial recursion limit. This creates no financial
hold and does not change payable/Treasury balances. Complete application binding
and service integration remain required before claiming double-counting prevention.

The new `budget_reviewed_components.source_components` begins source binding.
Original excluded liability-credit partitions may retain an explicit
`claim_component_basis`, independently reviewed with their amounts and evidence.
The detached binder requires the whole credit to have declared bases and a valid
captured approval. It supplies the calculator with exact component amounts/date
and keys containing the approval UUID, original line and normalized row ordinal.
Missing declarations are not inferred. Expected-version comparison rejects changed
source approvals; retained old captures still reproduce their original identities.
Exact reviewed reversals inherit the declaration but cannot become new original
capacity. Complete source/application movement coverage remains required.

`budget_application_components.bind_application_rows` now participates in proposal,
independent approval and reviewed projection. A resolved linked financial line must
partition each actual original-credit share into exact reviewed component keys.
Wrong sources/keys, incomplete allocations, invented links, and second expenditure
recognition from already-recognized/non-expenditure components are rejected. Entire
unresolved lines remain explicit. Exact reviewed payment reversals inherit component
references and mirrored amounts/signs; source-capacity reversals retain the original
basis rather than appearing as ordinary payment consumption. Source approval pins
enter the proposal source fingerprint, so changed direct decisions invalidate new
use while retained captures remain self-contained. Source and dependent application
proposals cannot share a batch before a guided dependency workflow exists.

Per-financial-line binding alone does not establish complete component usage or
certification. The connected gate below validates application lines across journals/
dates (including outside-period movements), transitive component-source decisions
and exact source cancellation lineage. Schema 7 also requires exact source proof
before including unlinked liabilities, with historical-review recovery as described above;
no native actuals certificate or double-counting-complete claim is enabled.

The connected usage gate passes focused SQLite/native validation.
`budget_component_usage.component_usage` follows the captured undirected financial
dependency group, verifies every current head (including transitive sources), and
builds dated movements from exact reviewed rows. Original capacities use immutable
component keys; reversals retain predecessor row identity, amount, purpose and
office through any number of reversals. Source corrections change capacity rather
than pretending to be ordinary payments. Each current application counts once.
Unreviewed entries/unresolved lines remain explicit incomplete coverage; stale
decisions fail. Older pre-claim captures remain readable without acquiring this
new completeness claim. The schema-7 inclusion guard is distinct from this component
calculation; neither independently authorizes certification.

Application/source-correction approval writes all heads inside the existing
Fund-locked transaction and then validates one fresh capture; a failure rolls back
the entire decision, including reviewer fields. Source-only successor approval
can still invalidate dependent classifications, which must be repaired before
new dependent use. Reviewed projection invokes the same usage gate. No cash or
payable reservation is created.

## Required next work before completion of this feature

- The reviewed reversal implementation passes focused SQLite/native tests. It pins captured predecessor
  attribution versions through the full chain, preserves their component amounts,
  office/object/purpose/basis and flips financial signs. Unique financial lines can
  be paired automatically as a review suggestion; duplicate lines require an explicit
  bijection. Ancestors outside the period stay evidence, not additional period activity.
  Changed ancestor attribution makes new use stale without rewriting old capture.
  Missing/unproved predecessors remain unresolved; structural opening/closing/equity
  sources cannot become expenditure.
  Explicit same-batch reversal dependencies are now implemented as described above;
  focused database validation passes; finish the guided workflow before treating
  batch usability as complete. Implicit co-batching remains rejected.
- Verify recognition/settlement deduplication against retained original payable and
  liquidation links; do not assume a per-journal partition alone establishes this.
  Preserve the difference between a loan-principal repayment and settlement of an
  expense already recognized; do not blanket-exclude all liability debits.
  Source inspection confirms that `claim_attributions.application_origin` also reads
  separately approved historical claim heads: a blank native `payable_origin_id` is
  not proof of no settlement. Shared historical applications and invoice slices need
  their complete retained decisions. Current native capture includes line-level
  native links; the schema-3 extension now captures historical heads and linked
  original claims, with focused SQLite/native validation. Verify this evidence before making a
  deduplication decision; do not call the
  live claim resolver after capture and mix its newer pointers into frozen evidence.
  Native invoice applications also pin an exact older attribution in
  `payable_allocation.attribution`; `claim_splits.retained_allocation` verifies that
  version, its compatible current invoice schedule and the original posting audit.
  Current-head capture alone cannot reproduce this proof after a compatible successor.
  Shared reversals likewise retain the entire older approval group. Capture the
  referenced retained versions, complete groups and posted allocation evidence in
  the coherent read before using those links for settlement deduplication (implemented
  and tested in schemas 4/5). Do not
  replace a pinned decision with its current successor or blanket-reject valid
  older pins. Keep this distinct from current historical-head verification, which
  is now implemented. Avoid multiplying financial rows when adding version evidence.
  Once source proof passes, the expenditure rule must distinguish exact portions
  of a mixed liability. A whole-journal label or ordinary original-credit capacity
  alone cannot prevent the same amount being assigned to both recognition and
  payment. Retain explicit reviewed source/component references, compatible dated
  amounts and reversal meaning; preserve loan principal and fees separately.
  Classification checks must not create a second financial reservation or rewrite
  payable capacity. Per-line binding and connected dated usage are now implemented;
  neither establishes a new local accounting policy. Evaluate
  all linked posted applications and source corrections from the same capture,
  including movements outside the selected reporting period. Candidate approvals
  replace their own current allocations once under the shared Fund lock; unapproved
  proposals must not count as extra posted consumption. Validate transitive source
  decisions, and never silently discard stale allocations to make capacity fit.
- Add usable batch preparation/review, complete history and controlled export. The
  service currently supports batches up to 250 journals per mutation; this is not a
  register/history retrieval limit. Avoid a separate manual worksheet per journal.
  Resolve stale predecessor/dependent correction ordering without silently rebasing
  approvals. The current separate-batch restriction is not a final workflow policy.
  Specifically reproduce and repair a source successor with both an approved
  payment and its approved return: after the source changes, the whole-group stale
  check and the predecessor/return separate-batch restriction may prevent either
  dependent from being repaired first. Use explicit joint proposal dependencies
  and independent atomic review; do not drop stale movements or invent a prior
  approval to pass capacity. This is required before publication of a usable workflow.
- Check the structural-source boundary before calling component coverage complete:
  the current normalizer disallows component-basis declarations on opening/closing/
  direct-equity sources. Excluding an opening movement from period expenditure must
  not by itself remove a legitimate, explicitly evidenced later principal repayment.
  Establish and validate the supported source route while preserving the exclusion
  of the original structural movement; do not blanket-include structural entries.
- Persist native office statements and separately authorize certification, with
  source-change checks on new Budget selection and retained proposal/output versions.
  Native statements must not masquerade as external signed originals. Form 1 office
  reconciliation and joint certification remain separate requirements.
- Complete focused and native races, broader Accounting/Budget/Reporting/Finance and
  voucher regressions, browser/source-to-output proof and relevant acceptance.

## Validation in progress

Migration `0033_budgetexpenditureattribution_and_more.py` was generated with isolated
settings. No operator migration was run. Focused SQLite PASS: 12/12 tests, no skips,
71.202s, exit 0; both disposable stores destroyed. Command:
`python .tmp/my_work_sqlite.py accounting.test_budget_attributions accounting.test_budget_native_sources`.
Initial fresh MySQL 8.4.11 PASS: 14/14, no skips, 92.452s, exit 0; both stores
destroyed. Command: `python .tmp/retrieval_native.py accounting.test_budget_attributions accounting.test_budget_attribution_concurrency accounting.test_budget_native_sources accounting.test_budget_native_capture_concurrency`.
These initial results predate the reversal implementation. Reversal SQLite PASS:
16/16, no skips, 93.284s; both disposable stores destroyed. Native PASS: 19/19,
no skips, 125.295s, exit 0; both stores destroyed. Commands use the initial labels
above plus `accounting.test_budget_attribution_reversals`; the native command also
retains both concurrency modules. Logs: `.tmp/budget-attribution-reversals.log` and
`.tmp/budget-attribution-reversals-native.log`. The SQLite run began before the fifth
reversal-of-reversal test; native includes it. Both began before the in-memory lookup
optimization. Expanded schema-2 SQLite PASS: 35 discovered, 33 passed, two native-only
skips, 90.730s, exit 0; both stores destroyed. It used all these modules plus
`accounting.test_budget_actuals budget.test_planning_context`; log
`.tmp/budget-attribution-expanded.log`, session `59945` collected.
Compilation, migration-drift and whitespace checks pass.
That expanded run predates schema 3. Initial schema-3 SQLite PASS: 21/21, no skips,
52.791s, exit 0; both disposable stores destroyed. Session `89149` collected,
log `.tmp/budget-claim-capture.log`, with `accounting.test_budget_claim_sources`,
`accounting.test_budget_attributions`, `accounting.test_budget_attribution_reversals`
and `accounting.test_budget_native_sources`. It began before directed-dependency
refinement, malformed-reference guards and the additional unchanged-original assertion;
final SQLite validation must cover those edits. Schema-3 native PASS: 24/24, no skips,
68.738s, exit 0; both stores destroyed. Session `43577` collected,
`.tmp/budget-claim-capture-native.log`, including the added shared-claim
approval/capture race and both existing attribution/native-capture race modules.
The owned MySQL 8.4.11 fixture was restarted and its identity verified. Stop it after
native teardown. Do not confuse pending schema-3 tests with passed schema-2 checks.
Native `43577` predates the detached verifier. Verifier SQLite PASS: 22 discovered,
21 passed, one native-only skip, 48.174s, exit 0; both stores destroyed. Session
`42269` collected, with the four claim-capture tests and attribution/reversal/native-source
modules, `.tmp/budget-claim-verification.log`. Tests exercise live-service snapshot
parity for whole, split and shared approved claims, zero extra Finance reads, old
retained capture reuse, altered approval rejection and missing shared-head rejection.
These verifier checks passed. Integration tests add submission/review rejection and
unrelated-journal scope isolation: SQLite `33677`, `.tmp/budget-claim-integration.log`;
native `18637`, `.tmp/budget-claim-integration-native.log`. Integration PASS: SQLite
24 discovered, 23 passed, one native-only skip, 50.534s, exit 0; native MySQL 26/26,
no skips, 78.529s, exit 0. Both stores were destroyed in both runs; both sessions
collected. Native includes all capture/attribution/reversal modules and three race
modules. Older pinned-version/native posting-envelope verification remains open;
these passes establish current historical-head verification, not full deduplication.
Schema-4 initial SQLite PASS: 26 discovered, 25 passed, one native-only skip,
64.278s, exit 0; both stores destroyed. Session `20117` collected,
`.tmp/budget-claim-pins.log`. Schema-4 native PASS: 28/28, no skips, 94.420s,
exit 0; both stores destroyed. Session `31351` collected,
`.tmp/budget-claim-pins-native.log`. SQLite began before directed pin-scoping
and unchanged-original assertions; native includes them and all three race modules.
The new tests post actual invoice payments/shared reversals, approve compatible
successors and check exact retained old decisions, omitted unreferenced drafts,
one Finance read and unchanged financial totals. The verified
owned fixture is running; stop it after native teardown, without overlapping runners.
Schema-5 SQLite PASS: 26 discovered, 25 passed, one native-only skip, 54.590s,
exit 0; both stores destroyed. Session `20079` collected,
`.tmp/budget-claim-pin-verification.log`, with
claim capture/verification and attribution/reversal/native-source tests. It adds
old-decision tamper, old shared-member tamper and missing posting-audit checks,
while proving earlier retained evidence remains usable. SQL query compilation and
Python compilation pass. Schema-5 native PASS: 28/28, no skips, 95.781s, exit 0;
both stores destroyed. Session `5140` collected,
`.tmp/budget-claim-pin-verification-native.log`. It includes all
capture/attribution/reversal modules and three races, validating the pinned approval
and posting proof before the newer projection/helper refactor.
Projection SQLite PASS: 29 discovered, 28 passed, one native-only skip, 72.604s,
exit 0; both stores destroyed. Session `96623` collected,
`.tmp/budget-claim-links.log`, with
`accounting.test_budget_claim_links` plus claim-capture, attribution, reversal and
native-source modules. Three new tests check native payment/return signs, exact
shared historical amounts and explicit unlinked/scoped behavior. Existing pinned
payment/shared-return tests now check projection preserves the old decision and
amounts. Native `5140` predates the projection and dependency-helper refactor;
projection native PASS: 31/31, no skips, 98.123s, exit 0; both stores destroyed.
Session `46837` collected, `.tmp/budget-claim-links-native.log`, with the projection
label plus all earlier claim/attribution/reversal/capture/race modules.
Pure component calculations PASS: seven database-free tests, 0.032s, exit 0.
Command: `python .tmp/my_work_sqlite.py accounting.test_budget_claim_components`,
log `.tmp/budget-claim-components.log`. Coverage includes mixed components,
cross-office overuse, dated returns, exact/duplicate/missing/cyclic reversals,
source cancellation and a 1,201-movement chain. These calculations are not yet
wired to reviewed source/approval services; native persistence tests do not apply
to this pure primitive but remain required for the later integration.
Source-binding SQLite PASS: 21/21, no skips, 32.042s, exit 0; both stores destroyed.
Session `27029` collected,
`.tmp/budget-reviewed-components.log`, using `accounting.test_budget_reviewed_components`
plus component/attribution/reversal modules. Native `32511`,
`.tmp/budget-reviewed-components-native.log`, adds those two new modules to the full
31-test projection selection. Four integration tests cover independent approval,
exact mixed amounts, no additional Finance reads, unchanged sources after a later
payment, incomplete/invalid basis, changed versions, old captures and exact reversal
inheritance. Native PASS: 42/42, no skips, 98.386s, exit 0; both stores destroyed.
Session `32511` collected; this includes all three native race modules. The owned
MySQL 8.4.11 fixture was stopped after teardown. No test runner remains active.
Python compilation, whitespace and 467 local documentation-link checks PASS.
Broader regression/browser acceptance is NOT RUN - OUT OF SCOPE for this internal
source-binding increment; it remains mandatory before completing the feature.
Application-binding SQLite PASS: 45 discovered, 44 passed, one native-only skip,
75.901s, exit 0; both stores destroyed. Session `5287` collected,
`.tmp/budget-application-components.log`, with the new application module plus
reviewed-source/component/claim-link/claim-source/attribution/reversal/native-source
modules. Native `94618`, `.tmp/budget-application-components-native.log`, adds all
three native race modules. Five new integration tests cover actual payment amounts,
independent approval, complete source pins, one-read retained projection, wrong
components/capacity, prohibited second recognition, unresolved evidence, changed
source review and exact returned-payment inheritance. The historical claim-proof
test now explicitly leaves Budget classification unresolved instead of silently
excluding a payment before its source components are reviewed. Native PASS: 47/47,
no skips, 103.804s, exit 0; both stores destroyed. Session `94618` collected.
A sixth test was added after discovery: an actual reviewed shared payment must
retain its 300/200 original-credit shares; an otherwise balanced 400/100 partition
must fail. Its isolated SQLite run PASS: 1/1, no skips, 1.657s, exit 0; both stores
destroyed. Session `17250` collected, `.tmp/budget-application-shared.log`.
Its fresh native check PASS: 1/1, no skips, 2.433s, exit 0; both stores destroyed.
Session `64894` collected, `.tmp/budget-application-shared-native.log`, with the exact
sixth method label. The owned MySQL fixture was stopped after final teardown; no
test runner remains active. Final Python compilation, whitespace and 468 local
documentation-link checks PASS. The canonical operator database SHA256 is unchanged.
Broader regression and browser/operational acceptance remain NOT RUN - OUT OF SCOPE
for this internal increment and required before feature completion/publication.
Connected-usage validation is running: SQLite `41803`, `.tmp/budget-component-usage.log`,
with the new usage module plus the prior application/source/component/claim/attribution/
reversal/capture selection. Native `63919`, `.tmp/budget-component-usage-native.log`,
adds `accounting.test_budget_component_usage_concurrency` and all three prior race
modules. Six new cases cover shared capacity/approval rollback, future out-of-period
use, dated returns, source cancellation/restoration, incomplete coverage and a
three-source stale dependency. A native race competes for the same remaining
component after both financial payments already exist. Results pending.
The initial SQLite run predates the distinct-office fixture refinement and legacy
guard. Focused SQLite `11020`, `.tmp/budget-component-usage-compat.log`, covers actual
distinct offices plus pre-claim schema 1/2 read compatibility. Native `63919` includes
the office refinement but predates the guard; run the compatibility method after
native teardown. The verified owned fixture remains running; no native overlap.
Initial connected-usage SQLite FAIL - CAUSED BY CURRENT WORK: 52 discovered, six
setup errors, one native-only skip, 78.818s, exit 1; both stores destroyed, session
`41803` collected. Every new case selected September 30 while the current date is
September 26. The existing completed-period guard correctly rejected the fixture;
the tests did not reach usage assertions. Corrected the fixture to September 10,
retaining all actual movements through September 7 and the earlier-period test.
No production guard was weakened. Older `63919`/`11020` still use the prior fixture.
Corrected full SQLite `58845`, `.tmp/budget-component-usage-final.log`, includes all
seven usage cases and all prior application/source/component/claim/attribution/
reversal/capture modules, plus all four native-only race modules. Run the matching
corrected native suite after `63919` teardown. Results pending.
Older native `63919` FAIL - CAUSED BY CURRENT WORK: 55 tests, seven identical
completed-period setup errors, 110.495s, exit 1; both stores destroyed. Focused
SQLite `11020` also FAIL - CAUSED BY CURRENT WORK: two identical fixture errors,
0.258s, exit 1; both stores destroyed. Both sessions collected. Corrected native
`37125`, `.tmp/budget-component-usage-final-native.log`, now runs the same full
selection as corrected SQLite, with a strengthened race assertion requiring the
losing approval to fail specifically on dated component capacity. No runner overlap.
Corrected full SQLite PASS: 56 discovered, 52 passed, four native-only skips,
80.382s, exit 0; both stores destroyed. Session `58845` collected,
`.tmp/budget-component-usage-final.log`. All seven usage/compatibility cases reach
their assertions and pass; native `37125` remains pending.
Corrected native PASS: 56/56, no skips, 116.665s, exit 0; both stores destroyed.
Session `37125` collected, `.tmp/budget-component-usage-final-native.log`. The new
Fund-lock race confirms exactly one competing approval succeeds and the other
fails specifically on dated component capacity, retaining its submitted state.
The owned fixture was stopped after teardown; no test runner remains active.

Final commands (isolated Python 3.11 wrappers; no operator database migration):

```text
python .tmp/my_work_sqlite.py accounting.test_budget_component_usage accounting.test_budget_component_usage_concurrency accounting.test_budget_application_components accounting.test_budget_reviewed_components accounting.test_budget_claim_components accounting.test_budget_claim_links accounting.test_budget_claim_sources accounting.test_budget_attributions accounting.test_budget_attribution_reversals accounting.test_budget_attribution_concurrency accounting.test_budget_native_sources accounting.test_budget_native_capture_concurrency
python .tmp/retrieval_native.py accounting.test_budget_component_usage accounting.test_budget_component_usage_concurrency accounting.test_budget_application_components accounting.test_budget_reviewed_components accounting.test_budget_claim_components accounting.test_budget_claim_links accounting.test_budget_claim_sources accounting.test_budget_attributions accounting.test_budget_attribution_reversals accounting.test_budget_attribution_concurrency accounting.test_budget_native_sources accounting.test_budget_native_capture_concurrency
```

Scope: new usage/rollback/dependency behavior and its source, attribution, reversal
and concurrency dependencies. Broader application regression and browser/operational
acceptance remain NOT RUN - OUT OF SCOPE for this unpublished backend increment;
they remain required before the completed workflow/publication gate. The initial
fixture failures above are not pre-existing failures or passing tests. Operator
database SHA256 remains unchanged; whitespace and documentation-link checks pass.
The canonical operator database SHA256 remains unchanged. Native races cover competing submissions,
review decisions, capture during multi-journal approval and (in the new run) predecessor
approval versus dependent reversal review. Wider regressions and
ordinary browser validation remain pending. Production and LGU acceptance: NO-GO.
