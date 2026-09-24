# Finance retrieval integrated audit — 2026-09-24

Baseline: development v0.7.145, commit
`9f55dbd48f3f97c5638af870a6be49cffe3848c8`. This checkpoint audits the accumulated
retrieval repairs against the attached Finance Completion Gate and runs full
regression against that unchanged application/test revision. It does not establish
master integration, production readiness or LGU acceptance. **Goal incomplete;
production NO-GO.** The [living gap register](FINANCE_FOUNDATION_GATE.md) is canonical.

## A–C — Existing capability, repairs and this checkpoint

OBR and collection registers have scoped search, filters, truthful counts, complete
pages and matching exports. Their retained 10,000-record synthetic browser evidence
is documented in the foundation gate; it is not a production-volume guarantee.
Subsequent checkpoints repair voucher, journal, Budget, closing, ledger, Treasury,
shadow and retained-history retrieval. This audit adds no financial or application
behavior. It reproduces a remaining personal-work defect and assesses the integrated
revision rather than treating independent scoped passes as whole-goal proof.

| Retrieval area | Current evidence and boundary |
|---|---|
| OBR and collections | Foundation gate FG-01/02: complete scoped pages, narrowing, matching exports and retained synthetic volume/browser evidence. Office acceptance remains open. |
| Voucher and Accounting registers | [Voucher retrieval](FINANCE_VOUCHER_RETRIEVAL.md) and subsequent foundation checkpoints retain actionable/history separation, strict scope and complete exports. |
| Ledger | [Ledger retrieval](FINANCE_LEDGER_RETRIEVAL.md): pages retain running-balance continuity and normal signs; invalid account selections fail closed. |
| Cash and remittances | [Treasury registers](FINANCE_TREASURY_REGISTER_RETRIEVAL.md): complete pages; financial reservation calculations remain independent of displayed pages. |
| Shadow and retained events | [Shadow retrieval](FINANCE_SHADOW_RETRIEVAL.md), [Budget/remittance history](FINANCE_BUDGET_REMITTANCE_HISTORY.md), [Accounting history](FINANCE_ACCOUNTING_HISTORY.md): complete scoped event/run/row navigation under existing permissions. |
| Bank candidates and report history | [Bank/report retrieval](FINANCE_BANK_REPORT_RETRIEVAL.md): independently paged eligible candidates, unchanged match validation, complete scoped report-history route. |
| Schedules and statement evidence | [Reporting schedules](FINANCE_REPORTING_SCHEDULE_RETRIEVAL.md): Active/Inactive/All pages; recent statement previews link to complete existing routes. |
| Personal My Work | PARTIAL: full eligible count but only first 100 tasks, without page continuation. Non-ready views omit the source-queue links suggested by the truncation footer. Reproduction below. |

## D — Reproduced missing retrieval

`finance/work_tasks.py::finance_work_tasks` constructs and sorts authorized tasks,
then returns `tasks[:display_limit]`, with a default limit of 100. The HTTP view in
`finance/portal_views.py::my_work` does not read a page parameter. In
`templates/finance/my_work.html`, exact source-queue groups render only for Ready
for me. The common truncation footer directs every view to those queues.

Read-only synthetic reproduction used the existing task-contract fixture in two
copied, isolated stores, creating 105 submitted setup releases owned by the same
worker. Each retained its actual source identity. Requests for
`/finance/my-work/?view=waiting&page=1` and page 2 returned:

| Observation | Actual result |
|---|---|
| HTTP status, both requests | 200 |
| Eligible / displayed tasks | 105 / 100 |
| Page 2 task identities | Exactly the same ordered 100 identities as page 1 |
| Truncation declared | Yes |
| Exact-queue links rendered | No |
| Submitted source records after retrieval | 105 |

The route was resolved through `reverse("finance_operations:my_work")`; the query
parameters, rather than a guessed URL prefix, define the reproduction. Retained
local evidence: `.tmp/work-cap-audit-20260924/result.json` and
`.tmp/work-cap-audit.log`. These ignored synthetic artifacts are not deployment data.
This proves the Waiting defect; the shared slice is source evidence for other views,
not a claim that every source adapter has been separately replayed at volume.

The personal CSV deliberately has a separately tested 100-row snapshot contract:
eligible count, row count, truncation flag, task identities and immutable archived
bytes. It is not the full financial source register. Preserve this explicit export
meaning during a navigation repair; do not silently relabel old exports or widen
permissions. A numeric-literal slice scan missed the dynamic `display_limit` bound,
so that scan cannot certify complete retrieval.

## E–F — Scope and unknowns

Disabled/unpurchased eGAPS modules and peripheral feature breadth remain outside
this gate. eGAPS was not accessed and may remain closed. Budget historical context
still distinguishes posted expense activity from certified expenditure; capital
outlay and authoritative coverage remain open. Earmark capacity and local lifecycle
rules remain unconfirmed. Infrequent local use of eGAPS reports does not establish
that those outputs are unnecessary.

The parallel [Budget actuals source audit](FINANCE_BUDGET_ACTUALS_SOURCE_AUDIT.md)
retrieved and visually checked DBM's relevant form pages. It establishes a firmer
national reference for certification/coverage work without changing Budget code
or treating national form instructions as local acceptance.
It also reproduces a Budget-versus-actual report defect: 20,000 of posted expense
becomes zero after a typed nominal closing entry while the report remains reconciled.
The original posting is intact. This requires a calculation repair after My Work;
passing baseline regression does not cover or resolve it.

## G–J — Workflow, friction, controls and parity

Retained ordinary workflow replay connects Budget authority and obligation through
payable/DV, independent posting, Treasury advice, recorded acknowledgement/release
and reconciled reporting. See [Treasury rehearsal](FINANCE_TREASURY_OUTPUT_REHEARSAL.md).
Synthetic release evidence does not establish witnessed physical custody or office
acceptance. Retrieval repairs remove concrete navigation barriers, but My Work and
the broader ordinary-work/output acceptance gaps prevent a foundation-complete claim.

This audit does not change financial transitions, permissions, schema or source
history. Preserve separate databases, maker-checker, department/UAT restrictions,
dated capacity, correction lineage and separately authorized export. The next repair
must paginate after the same complete permission/view/date filtering and stable
ordering; page navigation must never perform a financial action.

## Requirement trace update

This supplements the historical [22-section audit](FINANCE_FOUNDATION_REQUIREMENT_AUDIT.md)
without rewriting its v0.7.137 observations.

| Attached sections | Current assessment |
|---|---|
| 1 Foundation; 4 priority; 19 Done; 22 foundation before breadth | INCOMPLETE. My Work retrieval is a concrete next repair before further feature breadth. |
| 2 actual scope; 3 baseline; 16 avoid expansion | Retained purchased/used Finance boundary. Local inventory remains partly unknown; no new eGAPS observation. |
| 5 OBR; 6 collections | Implemented with retained scoped and volume evidence; production performance and local acceptance remain separate. |
| 7 Budget context | PARTIAL: dated expense projection and estimates retained; certified expenditure coverage open. |
| 8 quarterly plan | PARTIAL: versioned operational lifecycle exists; local columns/form acceptance open. |
| 9 earmark | Missing distinct capability, with UNKNOWN local capacity/consumption rules. |
| 10 architecture | Existing controls retained; regression does not prove all possible concurrency/operational cases. |
| 11 friction; 12 context/next action | PARTIAL: substantial retrieval repairs, but personal work after item 100 remains inaccessible through that view. |
| 13 business meaning; 14 vocabulary | Broad clerk acceptance unperformed; existing office terminology alone is insufficient. |
| 15 outputs | PARTIAL: governed generation and working output map; exact local layouts, signatures and accepted inventory open. |
| 17 classifications; 18 gaps; 20 evidence-first; 21 A–K | Updated here and in FG-11; synthetic reproduction distinguished from source inspection and human acceptance. |

## Validation

PASS — full SQLite baseline regression: 1,557 discovered, 1,434 passed and
123 skipped, 1,156.574s, exit 0. Both test stores destroyed; runner terminal.
Log: `.tmp/foundation-integrated-sqlite.log`. Skips are not passes.
PASS — full native MySQL baseline regression: 1,557/1,557, no skips,
1,945.744s, exit 0. Both test schemas destroyed; runner terminal.
Log: `.tmp/foundation-integrated-native.log`. Owned disposable MySQL stopped
afterward. These baseline results do not include the separately prepared later
My Work pagination repair or resolve the independently reproduced Budget-report defect.

Commands use the canonical Python 3.11 environment:

```text
python .tmp/foundation_full_sqlite.py
python .tmp/retrieval_native.py .
```

The SQLite wrapper disables dotenv and uses isolated default/Finance stores, media,
exports and logs. The native wrapper invokes the committed
`scripts/run_mysql_tests.py` with full discovery (`.`), private test credentials
and loopback port 33308. MySQL 8.4.11 strict mode and named-zone conversion passed
its startup preflight. Both test schemas are fresh. Native startup reports 23
`models.W036` conditional-constraint warnings; they are not suppressed or repaired
by this retrieval audit. See [native testing](FINANCE_NATIVE_TESTING.md) and the
historical [identity audit](FINANCE_NATIVE_INVARIANT_AUDIT_2026-09-09.md). Passing
existing race tests cannot establish untested conditional identities universally.

Remote baseline PR #106 also completed `verify`, `mysql` and GitGuardian successfully:
[regression run](https://github.com/tepong32/grand/actions/runs/36005303098).
These are results for that baseline PR, not future checkpoint CI or merge approval.

PASS — synthetic Waiting-cap reproduction, documentation link-target checks and
`git diff --check`. The operator database SHA-256 remains
`C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C` at inspection.
NOT RUN — OUT OF SCOPE: new browser/print acceptance for this documentation-only
audit; retained checkpoint browser results remain historical evidence. No production
or operator migrations, physical release, local-form certification or LGU acceptance
were performed. No master merge or deployment.

## K — Next checkpoint

Repair My Work navigation for every supported view, preserving view/date parameters,
truthful total/range counts and existing deterministic ordering. Verify more than
100 eligible tasks, later-page source links, invalid/out-of-range pages, permission
boundaries and the retained bounded-export contract. Because adapters span multiple
Finance domains, select their dependent regressions, with native checks for any
database-specific behavior. Then return to certified Budget expenditure coverage
after repairing the reproduced Budget-report closing boundary, followed by the
remaining ordinary/output gates. Do not infer earmark rules or acceptance.
