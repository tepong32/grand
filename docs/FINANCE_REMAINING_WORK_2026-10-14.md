# Remaining Finance foundation work and estimation basis

Scope: the user's original 22-section Budget → Accounting → Treasury Completion
Gate, mapped by the [foundation register](FINANCE_FOUNDATION_GATE.md) and
[requirement audit](FINANCE_FOUNDATION_REQUIREMENT_AUDIT.md). No unpurchased eGAPS
module, unrelated feature family or framework replacement is added here.

## Estimate correction

The earlier approximately 40-hour forecast and subsequent 80–140-hour forecast
were not supported by a reconciled task inventory or measured delivery rate.
Withdraw the 80–140-hour forecast and the apparent precision of the 70% functional /
60% overall figures. Do not turn those figures into deadlines or claim that the
goal expanded to justify the difference. Remaining requirements below mostly
already belonged to the original goal.

The goal accumulator reported 182,332 seconds (50.6 hours) at this checkpoint.
That is accumulated active-turn time, not measured coding hours or human labour.
It includes reasoning, execution, test/CI waits and rework; their individual
shares have not been profiled. Some rework was caused by current-work fixture
defects, rather than hardware or new user scope. Preserve their failed evidence.

Measured recent baselines:

- Current service/state tests: seven discovered; SQLite six passed / one native
  skip, 299.815s; native seven passed / zero skips, 400.317s. Both stores cleaned up.
- Published intake's combined 74-case regression: native 74 passed / zero skips,
  1,306.670s; SQLite 70 passed / four native skips, 1,158.336s.
- Exact v166 candidate CI took 38m03s; resulting master CI took 36m27s. Both
  finished successfully with 19 jobs and 2,533 native tests / zero skips.
  These are observed run durations, not promised future runtimes.

Current v167 measured result: nine-label, 35-case regression passed on both
backends: SQLite 33 passed / two native skips, 1,436.823s (23m57s); native all 35
passed / zero skips, 1,642.254s (27m22s). Candidate CI passed all 19 jobs and 2,544
native tests / zero skips in 39m29s. It ran 06:49:58–07:29:27 Singapore time on
October 14. An observed closed-stdout interruption delayed follow-up until about
18:09; its cause is unknown. Do not count that unobserved gap as coding, test or CI
time, or promise a 2–4-hour wall-clock turnaround that depends on uninterrupted
execution. The resulting primary run passed on attempt 2 after one bounded, unchanged-source
SQLite-3/verify retry; the first timeout and failed verify gate remain retained.
A specific hosted-resource cause was not established; timing headroom remains a
medium engineering risk and is not repaired merely by a successful retry.

Use active agent hours for implementation estimates and separately report elapsed
test/CI waits. Model choice alone supplies no measured GRAND delivery multiplier.

## Finite remaining-task list

The named [partial payment/return/reissue replay](FINANCE_PARTIAL_PAYMENT_OUTPUT_REPLAY.md)
now passes its focused and 23-case dependent SQLite/native checks. It validates
existing settlement/reporting behavior; it adds no financial feature and closes
no mandatory local or production gate. SQLite suite 30.263s / approximately 2m11s
including fresh setup; native 42.722s / approximately 3m27s including fresh setup.
One new regression identity retains gross release history separately from net
settlement and verifies all twelve earlier/current output artifacts.
v169 / `a1cc3a39` is installed-VM committed, integrated and pushed with its tag.
Complete candidate CI passed all 19 jobs: native 2,545 / zero skips; SQLite 2,346 /
199 native-only skips. Raw logs and exact coverage verified; resulting primary
v170 primary verification passed all nineteen jobs on attempt 2, with the exact
same application/test tree. v169's failed primary and v170's failed first attempt
remain preserved: SQLite-3 exceeded the existing twenty-minute job limit; both
mysql gates passed. v170's first suite itself reached OK / 267 cases / 31 skips in
1,060.809s, but coverage upload was skipped. A single worker/gate retry passed in
989.724s without source/limit/assertion changes. Runtime headroom remains a MEDIUM
unresolved risk, with its specific hosted cause unproven. Further CI optimization
is deferred in accordance with the user's instruction. No whole-goal completion
or precise remaining-hours total is inferred.

The named [ordinary clerk handoff checkpoint](FINANCE_CLERK_HANDOFFS_2026-10-14.md)
has now reproduced/repaired a requesting-office dashboard count leak and reduced
demonstrated empty-queue clutter. Final 31-case local scope passes on both backends,
with read-only desktop/mobile source handoffs checked. This advances entry/retrieval
and usability; it does not establish all later physical/review/settlement screen
actions or local acceptance. Publication/CI are in CONTINUE.md. The allowance below
was a planning bound, not a full-goal forecast.

Previously named independent checkpoint: inspect one ordinary payable clerk handoff
through the published department dashboards and existing My Work, comparing
source context and available next actions for each office. Planning allowance:
1–2 active hours for the bounded replay and a small demonstrated repair, plus
actual validation/CI waits. A discovered substantial defect requires a revised
scope/estimate; no whole-goal deadline is inferred. Manual prerequisites below
remain unresolved rather than being replaced with additional feature breadth.

| Original gate | Remaining work / completion evidence | Dependency and current estimate |
| --- | --- | --- |
| FG-03/06: Budget historical context and Form 1 | Source-finding intake, independent decisions, history/export and native races are implemented in v167. Remaining: implement only evidenced numerical treatment through a fresh whole-package successor; retain separate gross ending, deduction, adjustment and net controls. Finish statutory certification/Chief Executive approval and immutable issued output with the actual designated roles. | The earlier 2–4-hour checkpoint allowance is not an actual delivery-time claim: the observation connection was interrupted after candidate CI completed, and verification/integration resumed in the evening. Measured local/CI durations are recorded below. Numerical/issuance effort remains unestimated until the applicable recipe and exact role/output inputs are established. |
| FG-04/05: quarterly plan and distinct earmark certificate | Existing quarterly authority/ARO route is implemented; confirm reserved-column/form meaning. Establish actual earmark appropriation-versus-allotment basis, certificate numbering, consumption, cancellation/correction and independent review before extending existing Budget controls. | Local earmark rules are UNKNOWN; the user explicitly said not yet confirmed. Do not substitute generic reserves or invent capacity. Manual decision deferred; implementation estimate follows the established lifecycle. |
| FG-06: required outputs | Reconcile the [existing office output map](FINANCE_REQUIRED_OUTPUT_MAP.md) with actual Budget, Accounting and Treasury work. Reproduce required fields, columns, classifications, source references, totals, comparatives and signatures from accepted evidence. Fix demonstrated gaps using existing generation/export services. | Scope the remaining output repairs by named required forms, not the 31-form candidate catalog. A bounded next replay/inventory checkpoint can be planned at 2–4 active hours; that does not estimate every subsequently discovered repair or local printer acceptance. |
| FG-07/08/09: ordinary work and source reuse | Extend retained ordinary-chain proof to the actual office scenarios, historical-source adoption, returns/corrections and interrupted recovery that are still required. Prove lineage and unchanged earlier financial evidence through outputs. | Existing core routes and synthetic replay are evidence, not blanket office acceptance. Name the next scenarios before estimating their repair work; no speculative cheque/agency edge-case breadth ahead of foundation completion. |
| FG-01/02/11 and sections 11–14: complete retrieval and understandable work | Known OBR, collection, ledger, Treasury, history and My Work caps are repaired. Verify remaining office reachability, filters/counts/export agreement and responsible next actions on the ordinary chains. Simplify demonstrated confusing screens within their existing workflows. | Keep prior volume proof; do not rebuild registers or restyle the application broadly. Representative local office usability remains unperformed. |
| FG-10 and mandatory final gate | Run proportionate integrated regression and security/data-integrity checks after functional completion. Rehearse configured deployment, isolated two-store restore with reconciled controls, named roles, physical custody/signatures, form/printer use and LGU acceptance. | Full automated CI is not deployment/restore/LGU acceptance. Configuration, witnessed operational work and local scheduling are separate prerequisites; their elapsed duration is not currently estimable. Production remains NO-GO. |

There is no defensible remaining-hours total yet: adding an allowance for a
bounded replay to unscoped numerical/output/certificate work would repeat the
previous estimation mistake. At each vm-commitable checkpoint record its actual
start/end, completed capability, repair/rework and test/CI durations, then estimate
the next named checkpoint. Reconcile this list against the original gate rather
than expanding it indefinitely. Items awaiting local authority stay visibly open;
continue independent authorized implementation without manufacturing answers.

## GO / NO-GO and next action

GO for the published source-findings checkpoint and bounded partial-settlement
validation and its accepted candidate publication. Resulting primary acceptance
requires its actual terminal verify/mysql results and retained exact coverage.
NO-GO for unsupported numerical treatment, inferred earmark authority,
statutory issuance without actual designation/evidence, and production acceptance.
The [current checkpoint](FINANCE_FORM1_TREATMENTS_IN_PROGRESS.md) and
[handoff](../CONTINUE.md) own actual validation and release status.
