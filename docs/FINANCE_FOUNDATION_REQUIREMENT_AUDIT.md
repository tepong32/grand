# Finance foundation requirement audit — 2026-09-22

Audit baseline: development v0.7.137, `3deb36e6c2be85745de2955adef5a94b434e5cd5`.
This reconciles the attached 22-section Finance Completion Gate with the checkout
and retained checkpoint evidence. It is not master integration, a new full-suite
result, or LGU acceptance. **Foundation incomplete; production NO-GO.**
The [living gap register](FINANCE_FOUNDATION_GATE.md) remains canonical.

Subsequent retrieval repairs and the remaining history audit are recorded in
[ledger retrieval](FINANCE_LEDGER_RETRIEVAL.md),
[Treasury registers](FINANCE_TREASURY_REGISTER_RETRIEVAL.md) and
[shadow retrieval](FINANCE_SHADOW_RETRIEVAL.md). Classifications below retain this
audit's v0.7.137 baseline rather than implying those later repairs are absent.

## A — Already implemented

Scoped OBR and collection retrieval has pagination, matching exports and retained
volume/browser evidence (FG-01/02). Existing reviewed Budget, payable, posting,
payment and reporting routes reuse sources and retain correction lineage.
Quarterly plans have versions, independent approval and ARO comparisons. Budget
proposals retain dated ledger context and explicit estimates. These narrower
capabilities do not establish complete historical expenditure or form parity.
See [Budget context](FINANCE_BUDGET_PLANNING_CONTEXT.md),
[quarterly planning](FINANCE_QUARTERLY_PLANNING.md) and
[ordinary Treasury replay](FINANCE_TREASURY_OUTPUT_REHEARSAL.md).

## B — Repaired

Prior checkpoints repaired register retrieval, governed print coverage, overlapping
DV starter cells, Treasury local-date totals and governed tax release dates.
Evidence is retained in [starter layout](FINANCE_STARTER_LAYOUT.md),
[Treasury dates](FINANCE_TREASURY_REPORT_DATES.md) and
[tax dates](FINANCE_TAX_RELEASE_DATES.md). Their passing scoped tests are historical
checkpoint results, not a full regression of this audit head.

## C — Newly implemented in this checkpoint

No application change. This requirement reconciliation records source-confirmed
retrieval defects and a bounded next repair. The preceding checkpoint added
ordinary workflow assertions and six retained Treasury CSVs, not a new posting route.

## D — Missing or partial

| Area | Classification | Evidence and remaining work |
|---|---|---|
| General-ledger retrieval | PARTIALLY IMPLEMENTED | `accounting/views.py`, `ledger`: loops over `lines[:1000]`; `templates/accounting/ledger.html` has no count/page or truncation warning. `ledger_export` iterates the full scoped queryset. Repair UI retrieval and preserve running balances across pages. |
| Treasury cash work | PARTIALLY IMPLEMENTED | `vouchers/cash_views.py`, `workspace`: policies, instruments, exceptions and work items each stop at 100. Work-item count uses the full queryset. Add complete scoped retrieval without changing availability calculations. |
| Remittance register | PARTIALLY IMPLEMENTED | `vouchers/remittance_views.py`, `workspace`: `batches[:100]`; `templates/vouchers/remittances/workspace.html` has no continuation. Complete retrieval and consistent filters/counts. |
| Shadow-cycle register | PARTIALLY IMPLEMENTED | `finance/views.py`, `shadow_workspace`: full count with first 100 cycles; template has no pagination. Supporting acceptance workflow also needs complete retrieval. |
| Budget actuals | PARTIALLY IMPLEMENTED | Posted expense projection is narrower than certified expenditure; capital-outlay and source coverage remain unresolved. Do not relabel the projection. |
| Earmark certificate | MISSING | Distinct identity, lifecycle and consumption absent. Capacity basis is UNKNOWN; generic holds cannot substitute. |
| Required outputs and ordinary acceptance | PARTIALLY IMPLEMENTED | Working map and generated/source checks exist; exact local layouts, complete inventory and human acceptance remain open. |

The four register caps above are confirmed by source inspection, not new runtime
volume reproductions. Other bounded displays need separate triage: opening rows
explicitly disclose a 500-row limit; proposal/plan/remittance/shadow event histories
are bounded; reporting definition history shows 15 runs. Establish a complete
reachable history route before classifying these as repaired. Explicit recent-item
previews and string-length bounds are not automatically retrieval defects.

## E — Out of current scope

Unpurchased/unused eGAPS modules, unrelated HR/payroll/procurement replacement,
framework rewrites and speculative integrations are not authorized by this gate.
Shared identity, permissions, evidence storage and shadow acceptance are supporting
dependencies only where necessary to complete the Finance workflow.

## F — Unknown

Local earmark capacity before/after ARO, consumption/correction rules and certificate
numbering remain unconfirmed. Accepted output inventory, local reserved-column
meaning and configured production behavior are also unverified. Low use of eGAPS
reports does not establish absence of reporting requirements. eGAPS may stay closed;
this audit did not access or modify it.

## G — Full workflow evidence

The retained ordinary replay connects Budget authority/obligation, payable/DV,
independent posting, bank advice, acknowledgement, recorded release and reconciled
payment reporting. The latest replay checks 900 net from 1,000 gross and 100
deductions, original source IDs, receipt/JEV states, archive manifests and unchanged
earlier bytes. A reserved JEV number precedes journal creation; status distinguishes
pending from posted. Synthetic recorded release is not witnessed physical release.
Other ordinary scenarios and human handoff acceptance remain incomplete.

## H — Friction removed

Earlier checkpoints made older OBRs/collections and several other registers
reachable, exposed source context in Budget review and connected eligible OBRs to
payables. Starter particulars no longer collide with the first detail row.
Remaining ledger/cash/remittance limits prevent declaring retrieval complete.
Broad clerk usability and progressive disclosure have not been accepted locally.

## I — Controls retained

No financial, permission, schema or posting change in this audit. Preserve separate
stores, department/UAT boundaries, independent approval, immutable history,
dated capacity, actual physical custody/release duties and archived provenance.
The next retrieval repair must not reset page-two running balances or silently
widen an invalid account selection. Full export and visible scope must agree.

## J — Actual LGU parity gaps

Keep the supplied read-only eGAPS findings as a capability baseline, not fresh
observation. GRAND has connected development capabilities, but certified Budget
actuals, certificate semantics, complete ordinary retrieval, exact forms and office
acceptance are still gaps. The [required-output map](FINANCE_REQUIRED_OUTPUT_MAP.md)
tracks source/output evidence and missing acceptance; a CSV is not a signed form.

## K — Next checkpoint

First reproduce ledger retrieval beyond 1,000 rows and invalid account selection.
Then implement bounded deterministic pages with truthful counts and normal-balance
continuity across page boundaries, including credit-normal accounts and tied dates.
Check department scope and complete CSV agreement. Select dependent regressions
and native validation for any database-specific query introduced. Then address
cash/remittance retrieval, followed by shadow/history reachability. Budget coverage
and output acceptance stay visible; do not invent earmark rules to bypass them.

## Complete requirement trace

| Attached section | Assessment at this checkpoint |
|---|---|
| 1 Coherent Finance foundation | PARTIAL: ordinary replay exists; retrieval and local acceptance incomplete. |
| 2 Actual purchased/used scope | Bounded by the gate; exact local inventory remains partly UNKNOWN. |
| 3 Latest eGAPS baseline | Preserved in the foundation gate; not independently repeated here. |
| 4 Priority order | Reassert retrieval before further output/feature breadth. |
| 5 OBR retrieval | IMPLEMENTED with scoped retained validation; office acceptance open. |
| 6 Collection retrieval | IMPLEMENTED with scoped retained validation; office acceptance open. |
| 7 Budget historical context | PARTIAL: dated projection/estimates/authority retained; certified coverage open. |
| 8 Quarterly plan | PARTIAL: versioned operational route; local column/form semantics open. |
| 9 Earmark certificate | MISSING capability; UNKNOWN local rules. |
| 10 Financial architecture | Existing controls retained; no architectural change or new universal assurance. |
| 11 Reduce friction without removing control | PARTIAL: several retrieval/handoff repairs; more remain. |
| 12 Work context and next action | PARTIAL: connected routes; complete history/retrieval not yet demonstrated. |
| 13 Business meaning before technical detail | PARTIAL: not broadly accepted; some screens still emphasize technical evidence. |
| 14 Familiar office vocabulary | Existing OBR/DV/JEV/ARO routes; full terminology acceptance unperformed. |
| 15 Required outputs | PARTIAL: working map, governed generation and evidence; exact local parity open. |
| 16 No unrelated expansion | Retained; this checkpoint changes documentation only. |
| 17 Evidence-based classifications | Applied above; source inspection distinguished from runtime/acceptance proof. |
| 18 Living gap table | FG-01 through FG-11 retained and linked; new retrieval findings recorded. |
| 19 Definition of Done | NOT MET: important retrieval caps, Budget/certificate gaps and acceptance remain. |
| 20 Observe/reuse/validate workflow | Source audit before code; next defect reproduction explicitly planned. |
| 21 A–K report | Provided above. |
| 22 Foundation before breadth | Active priority; no unrelated domain expansion. |

## Validation and limits

PASS — read-only source/template inspection, connected export comparison by source,
and `git diff --check`. Local Markdown link targets checked. No new runtime or
financial correctness claim is made from this documentation audit.

NOT RUN — OUT OF SCOPE: application suites, MySQL, browser/print tests; no application
or schema changed. Prior v0.7.137 targeted replay passed 9/9, no skips, 12.740s;
that result belongs to its checkpoint. PR #98 remote checks were still pending
during this audit. Full regression and operational/LGU acceptance remain open.
No master merge or deployment.
