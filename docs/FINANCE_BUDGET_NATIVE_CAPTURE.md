# Native Budget ledger capture — 2026-09-26

Development v0.7.153 checkpoint on `codex/finance-budget-native-capture`, based on v0.7.152
`c38646fac6289b5a41be6e98cab750d2eda6bd54` ([draft PR #113](https://github.com/tepong32/grand/pull/113)).
This implements the coherent ledger-read portion of the
[native source audit](FINANCE_BUDGET_NATIVE_SOURCE_AUDIT.md). It is an internal
preparation service, not a delivered certification screen or a repair of the
proposal's missing office attribution. FG-03 remains incomplete.

## Implemented evidence boundary

[`accounting/budget_native_sources.py`](../accounting/budget_native_sources.py)
captures an explicitly authorized Accounting ledger, fund and completed date range.
One Finance SQL statement reads posted headers, both sides of financial lines,
current account/responsibility-center metadata, retained source snapshots,
payable-origin/allocation identities and one-to-one subsidiary evidence. The
assembly performs no lazy financial or metadata reads. Current account/office
metadata is a captured current lookup; it does not establish a historical office
assignment. Missing office identity remains explicit.

The read includes the whole posted fund to obtain reversal ancestors without
interleaving another query. Only period journals and their required reversal
ancestors enter the returned evidence/fingerprint. Unrelated out-of-period posting
does not change that fingerprint. Ancestors remain separately identified and do
not inflate period debit/credit controls. Exact reversal checking compares line
multiplicity, accounts, recorded responsibility centers, debit/credit mirrors and
cash purposes. Missing/out-of-scope parents, non-mirrors and cycles remain unresolved;
no classification inherits from those invalid links.

The detached JSON payload retains its own schema and checksum. Recapture can detect
backdated postings or changed retained source/current account metadata while leaving
the old payload untouched. Its capture time is bound by a separate evidence checksum
outside the financial fingerprint. The checksums check retained integrity, not authenticity of arbitrary
browser input. Callers must use trusted stored evidence. A current match describes
the read snapshot; it does not lock future posting or certify complete records.

Debit/credit controls and unassigned-line counts are ledger controls, not expenditure
totals. Empty source evidence is not a certified zero. No account type becomes an
approved expenditure purpose, and no officer/DV office is substituted. Old cash-flow
snapshot formats, financial journals, external certificate adoption, Budget snapshots
and operator data remain unchanged.

## Remaining integration

Persist this evidence within the native preparation workflow, add one shared reviewed
source-line purpose/office allocation identity across all office statements, and
capture its version in the same coherent source read. Current cash/payable attribution
heads are not native expenditure classifications; this service does not claim their
semantics or capture their independent current approval state. Source links remain
evidence to resolve; this checkpoint does not dereference every generated workflow.

Then implement batch preparation/review, distinct authorized native certification,
current-source warnings on new Budget selection, retained outputs and office-to-Form-1
reconciliation. Exact allocation partitions and recognition/settlement deduplication
remain required. Do not expose a certification action before those contracts pass.
The whole-fund read is uncapped, with memory proportional to fund history; large-LGU
volume/performance acceptance is unproven. Any optimization must preserve complete
lineage and one coherent capture rather than silently limit the register.

## Validation

Initial SQLite PASS: 17 tests (six new source tests and eleven existing adoption
tests), 84.778s, exit 0; both disposable stores destroyed. The later capture-time
integrity and subsidiary tests are included in final SQLite PASS: 24 discovered,
23 passed, one native-only skip, 78.140s, exit 0; both fresh stores destroyed.
Command: `python .tmp/my_work_sqlite.py accounting.test_budget_native_sources accounting.test_budget_native_capture_concurrency accounting.test_budget_actuals budget.test_planning_context`.
Initial fresh MySQL 8.4.11 PASS: 7/7, no skips, 42.870s, exit 0; both
stores destroyed. It proves a completed concurrent posting/synthetic account-metadata change
does not mix into an earlier capture and does make the next read stale. Final
expanded MySQL PASS: 24/24, no skips, 128.164s, exit 0; both fresh stores destroyed.
Command: `python .tmp/retrieval_native.py accounting.test_budget_native_sources accounting.test_budget_native_capture_concurrency accounting.test_budget_actuals budget.test_planning_context`.
The direct source tests plus existing adoption and planning-context regressions cover
this isolated internal read service and its existing permission boundary. No shared
posting service, schema or live calculation changed, so the full application suite
was not rerun for this checkpoint. That is not a broad Finance completion claim.

PASS: compilation, Django system checks, 462 local documentation links and whitespace
checks. The canonical operator database SHA256 remains
`C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C`.
The owned native server was shut down after validation; operator stores were untouched.
Tests cover detached source evidence, missing office context,
empty/foreign scope, changed-source checks and reversal ancestors. No screen, schema
or certification state changes; browser/form acceptance is outside this internal
service checkpoint. Production/LGU acceptance remains NO-GO.
