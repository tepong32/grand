# GRAND continuation handoff

Mandatory gate added 2026-09-07: [post-Finance operational scrutiny](docs/FINANCE_OPERATIONAL_SCRUTINY.md). **Finance production gate: NO-GO** pending functional completion, scrutiny, critical-gap verification and LGU acceptance. Run the full scrutiny only after the current functional phase; existing tests/container work do not satisfy it. Preserve all historical and deferred roadmap items.

Last updated: 2026-10-14

## Current bounded Finance checkpoint — partial settlement outputs

Branch `codex/finance-partial-output-replay`, same isolated worktree below,
based on accepted v0.7.168 / `5d61369`. No newer master was found on October 14.
The [partial payment replay](docs/FINANCE_PARTIAL_PAYMENT_OUTPUT_REPLAY.md) adds
one realistic regression case to existing consolidated settlement tests: two
payments, exact reversal of one bank return, replacement, three-stage report/CSV
downloads, immutable earlier exports and original invoice/reservation evidence.
No production code, schema, policy, workflow, permission or dependency changes.

Focused PASS: one SQLite case / 4.544s; one native case / 5.500s, no skips,
actual exit 0 and both stores destroyed. Initial native connection refusal is
ENVIRONMENTAL: the owned isolated fixture was stopped before setup. Its failed
log is retained; verified loopback fixture startup succeeded. Dependent PASS:
23 exact cases on SQLite / 30.263s and native / 42.722s, no skips, exit 0,
both stores destroyed and unchanged operator hashes verified. New assertions
verify the bank balance and retained release/status/replacement identities.
Owned MySQL stopped after validation. Installed-VM publication/remote gates pending.
Existing v168 documentation-primary run 38555013367 is still in progress; no
failure has been observed, and security passed. This is not full CI acceptance.

GO for bounded validation; production remains NO-GO. No ordinary settlement defect
has been reproduced, and this checkpoint must not be described as new functional
breadth. Next independent work: inspect an ordinary payable's clerk handoffs from
the published department dashboards/My Work, repairing only demonstrated reachability
or source-context gaps. Local earmark rules and Form 1 numeric/statutory authority
remain unknown/deferred. Use the finite remaining-task list below.

## Published Finance checkpoint — source findings

Functional release v0.7.167 / `51cad4bed51587db31052ac89d52826af4f861d0`
is installed-VM committed, integrated into master and pushed with its tag; exact
remote refs verified. Worktree `C:/Users/Administrator/.codex/worktrees/finance-form1-treatments/grand`,
branch `codex/finance-form1-treatments`; published Auth/security work and Python
3.11 / Django 5.2.18 are preserved. No operator migration, grant or data change.

[Source findings](docs/FINANCE_FORM1_TREATMENTS_IN_PROGRESS.md) now connect ordinary
Budget preparation to distinct Budget/Accounting/Treasury factual decisions,
returns/successors, full history and original-document JSON/ZIP export. Original
package/JEVs and numerical deductions remain unchanged. Separate read/export
permissions, UAT denial, owning native locks and immutable history are retained.

PASS: final nine-label, 35-case dependent scope; SQLite 33 passed / two native
skips, 1,436.823s; native all 35 passed / zero skips, 1,642.254s. Exact identities,
frozen source and both-store cleanup verified. 87927/36607 are terminal.
Earlier fixture/test/display mistakes and failed logs remain in the leaf report.
PASS: desktop/mobile browser preparation and three distinct decisions, every
original part, unchanged package and two journals, no numerical approval.
Owned browser/server closed. File-save cancellation remains ENVIRONMENTAL /
unresolved; HTTP ZIP integrity and JSON readback pass, not normal-browser acceptance.

PASS: [candidate 38480389037](https://github.com/tepong32/grand/actions/runs/38480389037),
all 19 jobs; native 2,544 passed / zero skips; SQLite 2,345 passed / 199 native-only
skips. Full raw logs, complete exact coverage and cleanup verified in
`.tmp/ci-proof-38480389037/acceptance.json`; every prior 2,533 identity retained,
eleven new tests and only the explicit new native-race SQLite skip added.
Resulting [primary 38547702277](https://github.com/tepong32/grand/actions/runs/38547702277)
passed all 19 jobs on attempt 2: native 2,544 / zero skips, SQLite 2,345 / 199
native skips. Full original logs, exact coverage and both-store cleanup verified
in `.tmp/ci-proof-38547702277/acceptance.json`. The final evidence uses seventeen
unchanged successful jobs from attempt 1 and the actual SQLite-3/verify retry
logs; original job timestamps/source revision match exactly. It does not rewrite
or declare the unsuccessful first attempt a pass.
Do not restart the old candidate watch: handle 92555 is missing; its run is terminal.

Primary first attempt: SQLite worker 3 exceeded the unchanged 20-minute job limit
and was canceled; the complete gate is not accepted. Exact job/annotations/raw
log are retained in `.tmp/ci-proof-38547702277/`. The identical candidate worker
completed all 267 cases in 702.687s; primary started the same first 205 cases before
cancellation. Median duration of 29 common cases was 1.60 times candidate; no
assertion failure was observed. This proves timing variance, not its specific
hosted-resource cause. One bounded canceled-job/dependent-gate retry completed successfully on the
identical SHA, with no source, limit, assertion or check change. Preserve
the unsuccessful attempt; do not label it PASS. Full primary acceptance now passes with complete exact coverage, while the failed
first attempt and timing risk remain documented.

Timing: candidate CI ran 06:49:58–07:29:27 Singapore time, October 14 (39m29s).
The tool connection reported closed stdout during observation; follow-up resumed
around 18:09. That observation/interruption gap is not measured coding work and
its cause was not established. The candidate itself completed, rather than running
through that gap. Primary promotion happened only after current-state verification.

The [finite remaining-task list](docs/FINANCE_REMAINING_WORK_2026-10-14.md) corrects
unsupported whole-project forecasts. Next independent checkpoint: one named
ordinary cross-office output replay/inventory, planned at 2–4 active hours plus
actual validation/CI waits. Supported numerical Form 1 treatment/successors,
statutory issued output, confirmed earmark rules, required office outputs, ordinary
scenarios and operational/LGU acceptance remain required. Unknown local rules stay
open/deferred; do not invent them or broaden peripheral scope. Production NO-GO.

## Authentication review and dashboard pass — 2026-10-14

The user explicitly requested a separate security branch, employee/public signup
redesign, then dashboard polish and department starting pages. This scoped pass
began on primary v0.7.109, whose auth files match the current Finance checkout.
Primary advanced to v0.7.157 (`739e365`), then v0.7.160 (`15b079c`) and its
documentation checkpoint v0.7.164 (`1f9a5c0`) during this pass. Integration preserves
that already-published primary work without importing unfinished development
branches. Primary already supplies targeted repairs for the same Finance test
calendar issues; those replace the earlier broad fixture clock. See
[identity/access design and rollout requirements](docs/AUTH_SECURITY.md), AUTH-001
in [the decision log](docs/IMPLEMENTATION_DECISIONS.md).

Public email/Google signup creates only a citizen identity. Employee creation
requires HR directory authority plus `users.add_user`, with explicit department
assignment and separately granted module roles. Unassigned employees get a
pending page; citizens get their own dashboard. Conflicting legacy identities
are quarantined pending read-only audit and human reconciliation. Guessing URLs
does not confer access. Shared default-store authentication counters require
`users.0002_authattemptbucket` before rollout; configure trusted edge capacity
and daily counter pruning. No operator migrations or role changes were applied.

PASS: initial existing boundary suite 113 tests; new pre-fix checks reproduced
12 failed boundaries and one broken citizen URL in 19 tests. Focused SQLite
147 passed / 2 native skips; final native identity, dashboard, profile, leave and
counter checks 132/132 passed (48.849s), including two concurrent-counter races.
Dependency consistency and updated audit pass with no known vulnerabilities.

FAIL - PRE-EXISTING: full SQLite first run 1,230 tests, 9 failures / 42 errors /
86 skips (650.599s). All 51 failures reproduce on untouched master c5bd920 with
its original dependencies (51 tests, 9 failures / 42 errors, 47.454s). Finance
fixtures combined fixed August/September 2026 scenarios with today's date.
The v0.7.158 voucher test fixture used a deterministic September 15 business
clock; production financial date/capacity checks are unchanged. An initial
September 12 clock left two September 13 corrections in the future; corrected.
PASS: all 51 repaired scenarios on fresh native stores (87.206s). Final full
SQLite regression passed 1,231 discovered / 1,145 passed / 86 native/environmental
skips (619.814s); skipped checks are not passes. The successful runner exited 0.
Version Manager security checkpoint v0.7.158 is published. The security and
subsequent presentation releases use
[PR #115](https://github.com/tepong32/grand/pull/115); its merge state and final
`verify` / `mysql` results are the authoritative primary integration evidence.

Dashboard presentation now shares the configured GRAND theme across citizen,
employee, signup/sign-in and assignment-pending pages. Twenty office presets
provide relevant next steps; aliases select descriptions without granting roles,
unknown offices retain the generic fallback, and unavailable cards are
nonclickable. Existing module helpers govern available links. See
[dashboard scope](docs/DEPARTMENT_DASHBOARDS.md).

PASS: affected UI/auth/integration SQLite 384 discovered / 381 passed / 3 skips
(118.549s), covering departments/users/profiles/home/leave, assistance, social
welfare, reporting, records, TracePoint and `finance.test_operations`. An initial
run used a nonexistent namespace as a test label and a stale generic-Planning
expectation; both were corrected, with a separate unknown-office fallback check.
Desktop/mobile browser checks of citizen and Planning dashboards show no
horizontal overflow at 390px. HR provisioning/leave links and invalid login
errors were checked with synthetic accounts. The old broken password-reset link,
a Windows UTF-8 copy issue and new public-button contrast were repaired. No
external OAuth/email flow is claimed as tested. Native UI/auth checks passed
52/52 (29.298s); a final display-state check distinguishes implemented Finance
cards requiring permissions from unfinished work passed 6/6 on fresh native
stores (1.012s). System checks, migration drift and whitespace checks pass.
Final full SQLite/MySQL CI is required before PR integration; consult PR #115
for the completed run and publishing state. No deployment approval is implied.

Tests use disposable SQLite stores and dedicated fresh MySQL schemas
`test_grand_auth_ci_default` / `test_grand_auth_ci_finance`. The pre-existing
owned MySQL server is preserved. The original checkout's modified SQLite DB and
unrelated work remain untouched. External Google callback, live email delivery,
trusted proxy operation and LGU acceptance are NOT RUN - ENVIRONMENTAL; they
require the configured deployment. Finance production remains NO-GO.

Final primary reconciliation also found a counter-selection bypass in v0.7.159:
ignored `login`/`email` fields and username/email/Unicode aliases could split the
same target's attempt count. Isolated probes against that committed middleware
reproduced all four cases. The fix reads each route's actual form field, resolves
known aliases through the authentication store's collation to account IDs, and
binds reset confirmations to URL UIDs. The native collation regression also
checks accent/case aliases. A full SQLite run was interrupted and restarted
after this source change; it is not passing evidence. Combined pre-fix native
affected tests passed 409/409 (365.995s). Final focused auth tests passed 40/40
(113.103s): `python .tmp/sqlite_run.py users.test_auth_security`. Final native
affected regression passed 414/414 with zero skips (380.616s), including account
aliases, MySQL collation and concurrent counters: `python .tmp/native_auth.py
users profiles departments home leave_mgt assistance social_welfare reporting
records tracepoint finance.test_operations`. These isolated local wrappers use
the same Django labels/native runner with dedicated disposable runtime roots and
schema names. The committed CI equivalents are `python manage.py test
--testrunner scripts.ci_test_runner.ShardedDiscoverRunner` and
`python scripts/run_mysql_tests.py --ci-shard`; the PR's final `verify` / `mysql`
jobs enforce exact complete coverage and zero native skips before integration.

The final credential review found that ordinary profile forms could change
another employee's recovery email under HR profile authority. The committed
v0.7.161 form reproduced the overwrite on an isolated unsaved user. Profile
forms now contain names only; owners use allauth email management with recent
authentication, and trusted account administrators retain separate account
tools. Current-password guesses across Django/admin password change and allauth
password change/reauthentication use the same persisted login account counter.
The obsolete v161 CI run 38442355330 and incomplete local full run were cancelled
after this finding; neither establishes complete passing coverage. PASS: final
SQLite identity/profile/home/department/leave regression, 145/145 (73.212s),
`python .tmp/sqlite_run.py users.test_auth_security profiles users.tests home
departments leave_mgt`. An initial new citizen fixture omitted its required
contact/address and failed; valid synthetic fields fixed that fixture without
relaxing production validation. PASS: native affected regression 419/419 with
zero skips (196.750s), using the same department/user/profile/home/leave,
assistance/social-welfare/reporting/records/TracePoint/Finance-operation labels
in `python .tmp/native_auth.py`. System checks and migration drift pass on the
final settings. The PR's final complete backend gates remain authoritative for
integration; obsolete runs are not substitutes for those gates.

The v0.7.162 auth tree passed complete CI run [38444989661](https://github.com/tepong32/grand/actions/runs/38444989661): 2,522 discovered, SQLite 2,324 passed / 198 native-only skips, MySQL all 2,522 passed with zero skips. Retained artifacts verify the exact release tree and all eight shards per backend. Primary advanced to Budget v0.7.160 during the final remote verification; that result covers the previous primary tree. The branch now preserves the published whole-package review UI unchanged and requires fresh combined-source gates in PR #115. No unfinished branch history is imported.

PASS: final auth/Budget integration check on v160's unchanged Budget source:
68 discovered, SQLite 64 passed / four native-only skips (891.036s); native
all 68 passed with zero skips (1028.442s), including reviewed original evidence
and race checks. Commands used the same isolated `.tmp/sqlite_run.py` and
`.tmp/native_auth.py` wrappers with `users.test_auth_security`,
`users.test_auth_concurrency` and Budget Form 1 package views, reviews, packages,
register, exports, print and review-concurrency labels. Broader final CI remains
the exact-source integration gate; primary's Budget code is retained unchanged.

## Finance validation retained from current primary

The following Finance evidence retains the candidate state supplied by primary
`739e365` and later `15b079c`, which were published during this auth pass. Its candidate-promotion
wording records that earlier run. The combined integration now requires the
complete final SQLite/native CI coverage gates in PR #115; Finance production
acceptance remains NO-GO. Preserve its source/runtime/operational boundaries.


## Current Finance checkpoint — guided whole Form 1 intake

The 17 intended intake paths are preserved on `codex/finance-budget-attribution`.
Published Auth primary `c5036fff861227ef5960255c044ed699150df523` (PR #115)
was integrated by fast-forward; source tree exactly matches its tested candidate
`81ee30f`. Only README needed documentation conflict reconciliation; retain both
Auth boundaries above and Finance evidence below. Original WIP bytes and stash
remain retained under ignored `.tmp/intake-pre-primary-preservation`. No unfinished
Auth branch or operator database was imported or changed.

PASS on prior v164 / Django 5.2.17: final dependent SQLite 26 cases / 1119.611s,
25 passed / one expected native race skip; native all 26 PASS / zero skips /
1274.336s, including three races. Both actual exits 0 and both stores destroyed;
exact identities/hashes retained in `.tmp/form1-intake-final-*-completion.json`.
Launchers 81806 and 6016 are terminal; never poll or restart them. This is prior
base evidence, not acceptance of the newly combined source/runtime.

The published security patch is retained: Python 3.11, Django 5.2.18 and allauth
65.19.7. Django's official 5.2.18 notes identify fixes including an insufficient
5.2.17 mitigation; do not downgrade published security repairs to the older pin.
Isolated patch packages are under
`C:/xxx/_INSTALLS/_HERE/_xxx/grand-primary-20261014-security-patches`, ahead of the
retained isolated dependency runtime. Operator `.venv` is untouched.

PASS: updated-primary SQLite 74 cases / 1158.336s, 70 passed / four expected
native-only skips; MySQL all 74 PASS / zero skips / 1306.670s, including review/
counter races and native collation. Both actual exits 0, exact 74-ID sets and
both-store cleanup verified. Launchers 48180/26309 are terminal; do not restart.
Logs/receipts `.tmp/intake-primary-{sqlite,native}*`; local acceptance guard PASS.
Native's 23 W036 warnings exactly match published primary; none were silenced.
System/drift, loaded requirement pins, audit and frozen 1,261-source checks PASS.
Only seven intended application sources differ from c503. Discovery: 2,533 IDs;
the two published department-test renames are verified; all previous Finance
identities remain. Discovery is not full execution.

Published c503 [primary run 38457755758](https://github.com/tepong32/grand/actions/runs/38457755758)
PASS: all 19 jobs, native 2,527 PASS / zero skips, SQLite 2,329 PASS / 198 native
skips (original 195 plus three Auth cases). Full logs, exact identities, both-store
cleanup and twenty passing negative annotations verified. Master c503 verified
when acceptance receipt was written. This run excludes the six new intake cases.

Intake is the locally validated candidate prepared for v0.7.166; primary acceptance remains pending. The existing source/cash/forecast/PhilHealth
services and signed one-hour previews retain exact original worksheet bytes,
source/actor/version checks and explicit missing/unresolved choices. Normal form
preview requires file reattachment; no provisional record or file cache exists.
Earlier synthetic browser successor v2 passed original bytes/net figures, unchanged
history/two journals and no financial authority. Updated-primary disposable browser
rehearsal PASS with exact original bytes/net figures and unchanged history/two
journals; source preview starts unresolved. Final desktop/mobile screenshots were
visually inspected. Both owned browsers/servers are now closed; ports 8798/8799
are not listening. Launchers 86856/39004 are terminal after deliberate shutdown,
not failed application tests; do not restart them. Audit PASS (no known
vulnerabilities) and all loaded requirement versions match published pins.
Both canonical SQLite hashes still match the recorded originals. Preserve all
earlier evidence and operator stores.

Release scope: seven application sources, eight continuity documents and two final
screenshots; VERSION/CHANGELOG only through installed Version Manager. Read-only
v166 preview is historical/unexecuted, not reserved. Fresh tag allocation, adapted
exact-current-base release guards, actual VM, complete candidate checks, primary
integration/push and exact remote acceptance remain. Production remains NO-GO;
GO for validated development. Statutory signatures/issuance, reviewed overlap
recipes and LGU acceptance remain open. The v164 primary watcher completed exit 0;
all 19 full logs/identities/cleanup were accepted; do not restart it.

Documentation follow-up v0.7.164 / `1f9a5c01f1635e6cea0a4e385d39f87637bc3743`
is integrated and pushed, with master/Finance branch/tag refs verified. It changes
only eight acceptance notes and VERSION/CHANGELOG; application sources match the
fully accepted v160 release below. The automatic
[documentation primary run 38453244967](https://github.com/tepong32/grand/actions/runs/38453244967)
completed SUCCESS on that exact SHA: all 19 jobs, native 2,473 PASS / zero skips,
SQLite 2,278 PASS / 195 unchanged native-only skips. All full logs, exact IDs,
both-store cleanup, security checks and twenty passing permission-denial
annotations were verified. Receipt `.tmp/form1-review-v164-primary-acceptance.json`
also verifies exact master/tag refs. Watcher 32136 completed exit 0; do not restart.
Continue first-package preparation intake from this fully accepted primary.

Installed Version Manager v0.7.160 / `15b079c1d78a9bc63edbd8197242ba2f15d11644` is integrated into master,
with its tag and both exact remote refs verified. The bounded
[whole-package internal review screen](docs/FINANCE_FORM1_REVIEW_UI_2026-10-14.md)
passed [candidate run 38442773424](https://github.com/tepong32/grand/actions/runs/38442773424) and [primary run 38447621668](https://github.com/tepong32/grand/actions/runs/38447621668): security, verify, mysql and all sixteen workers.
All 2,473 identities completed exactly once on each backend: native 2,473 PASS /
zero skips; SQLite 2,278 PASS / 195 unchanged native-only skips. Full terminal
logs, identity sets, two-store cleanup and passing permission-denial annotations
were independently verified. Local 20-case dependent suites, three native races,
real three-office browser decisions, system/drift and audit also passed.
GO for continued Finance development; production remains NO-GO. The next bounded
clerk step is whole Form 1 preparation intake through existing governed services.
Intake must support the first package with original SPA/flow sources, exact cash
anchors and explicit cash-forecast/PhilHealth evidence. Reuse the existing
capture/prepare services; clerks must not construct JSON. Missing controls
remain unknown and treatment choices remain explicit.
Statutory signatures/issuance and LGU acceptance remain open/deferred tonight.

Fresh accepted-primary security evidence: Dependabot still reports 24 OPEN alerts
(one Critical, 15 High, eight Medium), but all released pins are outside their
affected ranges and both actual security audits pass. GitHub's current SBOM still
lists the previous PyJWT 2.13.0 / pypdf 6.16.1 / urllib3 2.7.0, confirming an
outdated provider graph. Preserve the separate unresolved provider-status finding;
do not dismiss alerts or treat the production gate as accepted.

Installed Version Manager previews v158/v159 are historical, unexecuted previews:
both numbers were concurrently taken by unrelated authorized authentication/UI
releases on other branches. The scope guard refused reuse before staging or
commit. Preserve those tags/history and allocate the next available version
only when this Finance checkpoint is ready; do not integrate unrelated work merely
to obtain a version number.

Installed Version Manager released v0.7.157 at
`739e36574a4596eab5a6d0225e288cd98df1feff`. Its exact-SHA
[candidate run 38431327925](https://github.com/tepong32/grand/actions/runs/38431327925)
completed SUCCESS: security, verify, mysql and all sixteen regression workers.
Both aggregate gates verified all 2,468 discovered IDs exactly once. MySQL passed
all 2,468 tests with zero skips, including all 195 identities skipped on SQLite;
SQLite passed 2,273 tests with those 195 unchanged native-only skips. Full terminal
logs, metadata, annotations, identities and both-store cleanup were verified.

After fresh policy/ref/cleanliness checks, the clean primary checkout was advanced
by fast-forward to that exact tested release. Atomic push published master and
only v0.7.157; both remote refs were verified at `739e3657`. The automatic
[primary run 38436008732](https://github.com/tepong32/grand/actions/runs/38436008732)
completed SUCCESS on the exact released SHA: all 19 jobs, including security,
verify, mysql and all sixteen regression workers. Primary MySQL passed all 2,468
tests without skips; SQLite retained its 195 native-only skips. Complete raw
logs, exact identities, cleanup and all twelve failure-level annotations mapped
to passing negative permission cases were verified. Watcher 2518 completed exit 0;
do not poll or redispatch it. Engineering CI incident RESOLVED / GO for the next
Finance checkpoint. Provider dependency-alert refresh remains separately tracked;
no alert was dismissed. Finance production remains NO-GO pending functional
completion, operational scrutiny, critical-gap verification and LGU acceptance.

Complete local publication proof also passed both 2,468-ID suites, six runner
checks, security/system/migration/dependency checks and five Telegram tests. Do
not poll or restart completed local launchers 26124/21064/13291 or candidate
watcher 88932. Retained source proof allows only the verified final CRLF removal
in the CI runner, with identical AST and six rerun checks; all other 1,135 sources
match the original fingerprint. No application validator, ledger, permission,
assertion, native constraint or existing job limit was weakened for the CI repair.

Next Finance checkpoint: guided whole Form 1 preparation/intake and independent
Budget, Accounting and Treasury review through the existing governed services.
Do not create new posting authority or infer statutory signatures/issuance.
Manual LGU decisions remain deferred tonight. See
[CI evidence](docs/FINANCE_V157_CI_VALIDATION.md) and
[roadmap](docs/FINANCE_ROADMAP.md).

### Historical validation records

The records below describe earlier checkpoints; their then-pending publication
statements are historical and do not override the current status above.

Prior candidate, October 13: v0.7.156 / `d666f3ab` is published to the
development branch; primary/tag promotion remains NO-GO. Its actual
[run 38409417032](https://github.com/tepong32/grand/actions/runs/38409417032)
verify job exceeded the existing 20-minute limit. MySQL also completed CANCELLED
at its unchanged 60-minute limit, October 13 14:59:30 UTC. Complete raw logs and
all nine annotations are retained. Its 1,108 distinct named starts are not a
passing count; no terminal summary or unittest failure markers. Six source/role
permission annotations map to five completed passing negative tests. Watcher
10156 completed exit 1; do not poll it again or repeat this candidate dispatch.
Two verify source-export annotations map to completed passing
negative-permission cases. Fresh current-producer export profiling PASS:
one case / 96.329s under cProfile, both stores destroyed; source proof remained
unchanged before the subsequent CI-only edits. Full-profile time includes
156.405s fresh migration setup and 56.386s overlapping deepcopy cost; these are
diagnostics, not an ordinary retrieval SLA.

The next bounded repair distributes complete discovery across isolated CI
workers; it changes no application validator, ledger, lock, permission or
assertion. See [candidate v157 CI validation](docs/FINANCE_V157_CI_VALIDATION.md).
Six CI-runner regression checks PASS. Discovery-only partition proof retains all
2,468 original IDs exactly once, whole classes and original within-shard order.
The complete corrected SQLite shard rehearsal is PASS: launcher 21064 completed
exit 0; all 2,468 IDs exactly once, 2,273 passed / 195 unchanged native-only
skips, eight fresh two-store cleanups and all source/result/log hashes verified.
Do not poll/restart completed 21064. The corrected native rehearsal subsequently
completed PASS at launcher 26124; do not poll/restart that completed handle.
Local native shards are
sequential because that server uses fixed disposable test names; CI workers
each have their own MySQL service. Local evidence does not establish a remote pass.
Complete all local proof before Version Manager execution and exact-SHA
candidate dispatch. Both actual aggregate verify/mysql gates must pass before
primary integration and the held guided whole Form 1 intake/review milestone.
Manual acceptance remains OPEN/deferred tonight under the user's instruction.

Latest user direction, October 13: complete the native checks and one verified
remote attempt for this bounded CI repair. If verify remains unaccepted, retain
the actual failure evidence and resume independently validated Finance work up
to the next vm-commitable checkpoint. Avoid further speculative optimization;
do not bypass mandatory primary checks or report critical findings as resolved.
Keep README, handoff, roadmap and gap documentation current with actual changes.

Latest local evidence: all eight SQLite shards passed, including unchanged
195 skip identities/reasons verified against the previous full producer.
All eight native indices passed 206/205/369/204/413/392/354/325 tests
with no skips; each destroyed both test stores. These 2,468 completed native
tests include all 195 exact identities skipped on SQLite. Native launcher
26124 is terminal exit 0. Complete independent publication proof PASS is retained
in `.tmp/ci-shards-v157-local-publication-gate.log`.
Preflight 13291 completed exit 0: runner/YAML, system/drift, pip/audit and five
explicit Telegram checks all passed with actual exit/log-hash records. Installed
Version Manager preview confirms v157 without changing files/Git. Publication
requires `.tmp/verify_ci_shards_candidate_gate.py` to pass every completed shard,
exact actual log IDs, all original skip identities/reasons, exit/log hashes,
both-store cleanup, preflight evidence and all 1,136 frozen source hashes.
Initial read-only `.tmp/execute_ci_shard_release.py` scope inspection PASS: 12
intended paths, empty index, expected parent/branch, absent v157 tag, installed
preview and frozen-source proof. It made no staging/commit/push. Its `--execute`
and the installed-tool adapter both require the complete local publication gate;
use them only after all native results are terminal PASS. Installed Version
Manager manages the two VERSION/CHANGELOG additions; expected release scope is
14 paths at that inspection. The subsequent user-requested README and roadmap
updates expand the intended scope to 14 paths plus VERSION/CHANGELOG, 16 total.
Fresh read-only scope inspection passes this exact expanded set with an empty
index and unchanged source proof. Preserve failed v154/v155/v156 tags and do
not publish them in bulk.

Worktree: `C:/Users/Administrator/.codex/worktrees/grand-finance-my-work`, branch
`codex/finance-budget-attribution`, based on v0.7.153 / `61e690e4`.
This handoff covers the released development v0.7.154 candidate and the later
published development v0.7.155 runtime repair. Master integration,
resulting remote checks and deployment are not yet confirmed here; inspect the
actual branch/tag/run evidence before continuing dependent implementation.

Actual release update, October 13: installed Version Manager executed v0.7.154,
commit `bc8e482bafa7da33550b1aad3380ad293638d3d0`, with exactly the 400 reviewed
paths plus VERSION/CHANGELOG. The candidate was clean, all 91 staged artifact
bytes matched their original files, and the branch was pushed. Local v0.7.154
tag points to that SHA; master/tag publication and primary integration remain
pending. Explicit dispatch created [candidate run 38294180301](https://github.com/tepong32/grand/actions/runs/38294180301)
on that exact SHA. Verify completed CANCELLED at its 20-minute limit; MySQL also
completed CANCELLED at its 60-minute limit (actual annotation: 1h0m0s). Neither is
PASS. Complete job logs and actual timeout annotations are retained; the security, system
and migration checks passed, but project tests have no terminal passing summary.
Master remains `c5bd920a`. See the current runtime repair below.
Completion of the vm-commit workflow now requires both repaired-candidate jobs
to pass, clean primary integration/push/tag verification and the resulting primary
run. Preserve the failed v154 candidate commit/tag/logs; a later producer's pass
does not rewrite that candidate's result.

Actual runtime release update, October 13: installed Version Manager executed
v0.7.155 / `e6e1cb8e1a65121dcd392271a23f9cf618da3d23`, exactly the ten reviewed
repair paths plus VERSION/CHANGELOG. Clean HEAD, parent, local tag and unchanged
source proof were verified; the development branch push matches that SHA.
The guarded dispatch returned HTTP 204 at 21:34:15 UTC on October 12 and created
[repaired candidate run 38311451830](https://github.com/tepong32/grand/actions/runs/38311451830)
on the exact SHA. Verify job `115017911166` completed CANCELLED at the unchanged
20-minute limit; MySQL job `115017911366` also completed CANCELLED at its unchanged
60-minute limit (actual annotation 1h0m0s), ending 22:34:36 UTC on October 12.
The full native log has 809 distinct original test headers, no terminal summary,
and ends in the package permission/UAT case. Its service/dependency steps passed.
All four denial annotations map to completed passing permission cases; the other
annotations are the timeout, cancellation and runner notice. Complete native log
is 2,234,354 bytes, SHA-256
`e193b85977e95c172e4d7b8c7bfc4417a71cbadb2ea0c2eec80994f26bb01622`.
Complete verify logs/annotations show 797 distinct named test headers, ending
in whole-package export, and no terminal suite summary. Its security/system/drift
checks passed. The two denied-export annotations belong to completed passing
negative-permission cases, not failed assertions. The runtime repair is therefore
insufficient for the CI budget; do not promote it or raise limits merely for green.
The actual export profile completed PASS (handle 89995, exit 0): one genuine
scenario / 191.746s under cProfile. Its 873,287,954 calls include fresh migrations;
overlapping function times must not be summed. It recorded 1,840 joint snapshot
reconstructions, including a duplicate in native summary projection. A subsequent
bounded repair removes that duplicate and an ignored/repeated SPA flow construction.
The subsequent scoped-reuse focus passed 13 SQLite / 16 native cases with no skips,
exit 0 and both stores destroyed; separate Telegram passed five cases. System,
drift, dependency consistency and audit checks pass. These changes are not the
released v155 producer and require their own full regression and remote proof. See
[subsequent runtime work](docs/FINANCE_V156_RUNTIME_VALIDATION.md).
Earlier full fresh scoped-reuse runs used SQLite handle 18438, native handle 15756;
logs `.tmp/ci-summary-reuse-full-sqlite.log` and `full-native.log`. Frozen producer
has 1,133 source hashes / 2,468 discovered root IDs, all prior IDs preserved.
Use `.tmp/ci_summary_reuse_source_gate.py` for this producer. Do not overlap native
runners or substitute earlier producer passes. Version Manager preview for v156
updates only VERSION/CHANGELOG; actual execution has not occurred. Manual overnight
deferrals and next guided whole Form 1 intake/review milestone remain unchanged.
Earlier bounded observation: full SQLite had started 799 distinct original/new
cases and full native 783, without failure headers or terminal summaries. Both
handles were then reconfirmed live and all 1,133 source hashes remained exact. These were
started-case counts, not passes or percentages. The integration checkout is clean
at `c5bd920a`; operator checkout remains `ce0c724` with its pre-existing dirty
database, untracked policy test and historical output evidence preserved.
The guarded actual-release helper is `.tmp/execute_ci_summary_release.py`; it
requires `.tmp/verify_ci_summary_candidate_gate.py` to prove both complete suites,
exact 2,468 IDs, unchanged 195 SQLite native-only skips, zero native skips, focused/
Telegram/system/security results and the producer fingerprint. Do not execute
until complete actual local results exist. After actual release, push only the
development branch, verify its SHA, preview then execute guarded
`.tmp/dispatch_ci_summary_candidate.py <actual-SHA>` once and inspect both actual
jobs. Primary integration/tag publication requires those passes and a fresh remote/
policy check; do not publish old failed v154/v155 tags or force-push.
Resume verified October 13, 20:25 local: the app goal is ACTIVE. Both previously
reported test handles are gone; no matching Python test process or disposable
MySQL listener remained. The logs stopped at 06:59 local with 817 SQLite / 803
native started cases and no terminal summary. These runs are INTERRUPTED,
not PASS or demonstrated application failures. Their complete bytes were preserved
as `.tmp/ci-summary-reuse-full-*-interrupted-20261013-0659.log`; the cause of the
process interruption is not established. No source change followed the frozen capture.
The owned MySQL fixture was restarted and its loopback port/data directory/strict
mode verified. Full fresh runs restarted at 12:26:37 UTC: SQLite handle 98606 /
worker PID 33156; native handle 84146 / worker PID 28224. Follow these new handles,
not 18438/15756. `.tmp/rerun_full_reuse.py` retains separate start/result JSON with
actual exit codes and log hashes; a missing result is never a pass. Native schemas
remain exclusively owned by that runner. Release and dependent implementation
remain gated on complete current-producer local validation and both actual remote
jobs passing. Manual overnight deferrals remain unchanged.
Full new-producer SQLite completed PASS: 2,468 discovered / 2,273 passed /
195 unchanged native-only skips, 3,465.705s, handle 98606 exit 0; both test
stores destroyed. Exact unique IDs and all prior skip IDs/reasons match; all
1,133 source hashes remain unchanged. Complete raw log SHA-256 is
`59c906aa4b124ea71f862b36cd883835ccbd0ffb2b7a28041da4b41b62e81354`;
proof `.tmp/ci-summary-reuse-sqlite-completion-proof.json`. Native handle 84146
was still live at that SQLite proof; it subsequently completed as recorded below.
Do not poll the completed SQLite handle again. New binary captures
use the verified Windows Python pipe encoding CP1252; the initial strict-UTF8
proof reader failed on an expected permission-message apostrophe. Only the
reader was corrected; original bytes/hashes and passing process result remain.
Full new-producer native completed PASS: all 2,468 expected IDs exactly once,
5,084.954s, zero skips, handle 84146 exit 0 at 13:54:51 UTC; both test stores
destroyed. Raw log SHA-256:
`172794e6c1418e4971202328624d3cd5e1def3f888b5b2786384dcafa2f11fef`.
Do not poll either completed full handle. Combined local publication gate PASS,
exit 0, including actual result/log hashes, exact full/focus/Telegram IDs, unchanged
195 SQLite skips, zero native skips, cleanup, system/drift/audit/consistency and
all 1,133 frozen source hashes. Candidate publication is GO. This checkpoint's
report records validation before publication: inspect actual Git/tag/execution
evidence for v156 rather than inferring execution from its refreshed preview.
Exact-SHA remote verify/mysql remain required before primary integration/tag
publication or dependent implementation. Production/full Finance remains NO-GO.
Actual publication update: installed Version Manager executed v0.7.156,
`d666f3abd8d7c382582dc0a76dfb1aae0fdfc92a`, parent `e6e1cb8e`, exactly 18
intended paths (16 repair/evidence plus VERSION/CHANGELOG), uniform commit
subject and local tag verified. The development branch push matches that SHA;
master remains `c5bd920a` and remote v156 tag is not published. Guarded preview
passed, then the single dispatch returned HTTP 204 at 13:58:40 UTC, October 13.
[Candidate run 38409417032](https://github.com/tepong32/grand/actions/runs/38409417032)
tests that exact SHA. Verify `115337497255` and MySQL `115337496904` are both
IN_PROGRESS in their complete project/native regression steps. Verify dependency,
audit, system and migration prerequisites passed; MySQL initialization/setup passed.
Neither complete job is yet PASS. Read-only watcher handle 10156 is live; follow
that handle and actual API evidence, never repeat release/push/dispatch. Publication
proof `.tmp/ci-summary-reuse-v156-release.json`, dispatch marker in
`.tmp/actions-release-20261012/dispatch-d666f3abd8d7c382582dc0a76dfb1aae0fdfc92a.json`.
These outcome observations postdate the released candidate; source is unchanged,
but this handoff update is not part of that commit. The vm-commit workflow still
requires both remote passes, primary integration/push/tag and resulting checks.
Later terminal verify result: job 115337497255 completed CANCELLED at the
unchanged 20-minute limit (actual annotation 20m0s), October 13 14:19:15 UTC.
Complete raw log: 2,095,630 bytes, SHA-256
`263ea7a5af3c6d1acc05590fc050adb726cd08385f42d70eb171c97a1f61f399`.
All five annotations are retained. There are 796 distinct expected test headers,
ending in complete reviewed whole-package export, no terminal passing summary,
no failure-detail headers or unittest failure markers. Telegram was not reached.
Security/system/drift passed. Runtime repair remains insufficient for CI and
HIGH/OPEN; do not promote, repeat dispatch or raise limits merely for green.
MySQL job remains IN_PROGRESS; watcher 10156 is still live. Inspect its actual
result independently. Further diagnosis must use the retained complete log and
measured current-producer scenario; dependent Finance implementation remains held.
Current-producer genuine export cProfile is now live, handle 14855, isolated
SQLite via `.tmp/my_work_sqlite.py`, exact complete-reviewed-three-office export
case. New files `.tmp/ci-runtime-v156-package-export.prof` and
`ci-runtime-v156-package-export-profile.log` preserve earlier profiles. Follow
that handle; source remains unchanged and no passing profile result is yet claimed.
The old GitHub watcher (49890) completed exit 1; do not poll or repeat it.
Do not repeat release/dispatch. Master integration, remote tag publication and
resulting primary checks remain pending. These post-publication documentation
updates are later than the released candidate; retain its original evidence.

GitHub's push notification also exposed one Critical default-branch alert:
PyJWT [GHSA-ffc3-869f-jxw9](https://github.com/advisories/GHSA-ffc3-869f-jxw9),
affected <=2.13.0, fixed 2.14.0. Candidate 2.15.1 is outside that range.
Authenticated alert reads show 24 open old-master alerts: one Critical, 15 High,
eight Medium. Exact candidate pins are outside every returned affected range;
local pip-audit also passes. This does not close default-branch alerts or replace
actual CI. Keep dependent implementation NO-GO while those checks are pending.
The application/test runtime repair belongs to v155, not the older v154 producer.
These post-publication outcome updates are later than the v155 release; do not
misrepresent them as part of the candidate under test.

Current runtime repair: repeated pure joint-actuals reconstruction is a measured
application bottleneck, not yet proof of the entire CI timeout's cause. Reuse the
same freshly verified original preparation/trial within one snapshot operation;
each officer observation still undergoes independent full actuals/trial checks.
Public verification, role/actor/office/cohort/time/checksum checks and complete
snapshot equality remain; there is no global cache, new authority or database
mutation. Two new regressions reject separately forged observations and a valid
but different later cohort. Focused fresh SQLite PASS: 49 tests / 19.381s / no
skips, both stores destroyed. An earlier nonexistent class-label attempt ran no
source tests and is not a pass. Affected fresh MySQL PASS: 108 tests / 301.966s /
no skips, exit 0, exact actual-discovery IDs once and both stores destroyed.
Separate Telegram PASS: five tests / 0.703s, no database setup. Fresh dependency
consistency and audit PASS: no broken requirements, no known vulnerabilities;
verified Python 3.11, Django 5.2.17 and exact isolated patched imports/metadata.
Full fresh SQLite PASS (handle 33886, exit 0): 2,466 tests / 3,983.312s,
all discovered IDs exactly once, the same 195 native-only skip IDs/reasons,
both stores destroyed and exact source/CI proof unchanged. Full fresh native
PASS (handle 9694, exit 0): 2,466 tests / 5,723.615s / no skips, every discovered
ID exactly once and both stores destroyed. Native started only after affected
handle 33042 exited. All five original full-native failures pass within this
complete run. Original failed logs and the earlier case-level proof remain retained.
On the identical guarded synthetic Form 1 package, two fresh-actor reads improved
from 5.313/5.379s to 2.420/2.440s; profiled reconstruction fell from 43,828,078 to
20,937,138 calls and 13.764s to 6.591s. Original joint snapshot, package checksum
and synthetic store hashes stayed exact. Logs are `.tmp/ci-runtime-package-read-`
`before.log` and `after.log`; this is scoped evidence, not an operational SLA or
complete CI result. The v0.7.154 source fingerprint remains historical and must
not validate the new application/test producer. No timeout or coverage was relaxed.
The [runtime repair validation](docs/FINANCE_V155_RUNTIME_VALIDATION.md) records
the new 2,466-ID discovery, independent source fingerprint, actual focused/system
results and completed full SQLite/native handles. Version Manager preview
and actual execution are complete; new-producer CI remains pending as recorded above.
The workflow now appends `--verbosity 2` to its two full test commands, matching
the local suites already running. This prints exact test identities for future
timeout diagnosis; every other workflow byte, timeout and test selection is
unchanged. Original 1,132-source hashes remain retained; the new CI provenance
check proves all 1,131 non-workflow source hashes unchanged and permits only
those two exact suffixes. Use `.tmp/ci_runtime_source_gate.py --check-ci-observability`
for this producer, not the original no-change mode or v154's gate.
The new `.tmp/verify_ci_runtime_candidate_gate.py` completed PASS: every
original/new root-suite ID exactly once, exact existing 195 SQLite native-only
skips, native zero skips, affected/Telegram PASS and precise source/CI proof.
Its initial assumed Telegram namespace and root-suite membership were incorrect:
the explicit CI label discovers five `tests.TelegramBotHandlerTests` IDs from the
actual Telegram source, while root discovery does not recurse into that plain
directory. The verifier now checks exact source-backed scoped discovery; no
application/test, assertion, coverage or passing log changed. Initial verifier
failures remain retained. Log: `.tmp/ci-runtime-complete-candidate-gate.log`.
Candidate publication is GO; primary integration/dependent work still requires
both actual remote jobs. Do not substitute v154's historical publication gate.

User steering 2026-10-12: finish the next vm-commitable checkpoint, then perform
the actual version-manager commit, integrate intended work into master and push,
verify the remote result. Later steering prioritizes the failed Actions incident
and explicitly requests resuming the Finance goal after both remote jobs pass.
This authorizes release after its real review/regression/integration gates; it
does not waive those gates or require whole Finance completion before releasing
this bounded checkpoint.
Do not add dependent features while the release/CI defects remain unresolved.
Preserve unrelated work; inspect accumulated dependent scope,
version-manager adapter/preview and current remote/PR/check policy before release.

Overnight steering, 2026-10-13: after the current actual vm-commit and CI repair,
continue the existing Finance completion plan autonomously and vm-commit subsequent
validated work as well. Defer items requiring manual intervention tonight; retain
them in the gap register rather than guessing an LGU answer or marking acceptance
complete. This includes earmark-before-ARO confirmation, office-specific form/
printer acceptance, named signatory/Chief Executive decisions and physical custody
or witnessed operational acceptance. A software route may preserve explicit
unknown/pending states, but must not fabricate the missing decision or evidence.
Stay within purchased Budget–Accounting–Treasury scope and the existing roadmap;
the next implementation remains guided whole-package intake/review after the CI
gate. Overnight deferral does not waive financial controls, release tests, actual
remote CI, statutory approval or the production NO-GO boundary.

CI priority: complete authenticated run metadata, annotations and log archives
were retrieved for failed scheduled runs 139/138 and passing run 136. All use
master `c5bd920a650e5ade538cafd259de1f730fa81eea`; see
[incident evidence and repair gate](docs/FINANCE_CI_INCIDENT_2026-10-12.md).
Candidate publication is GO after the bounded repair checks below; primary
integration and dependent implementation remain NO-GO until both complete remote
jobs pass. The full local runs
already reproduced 24 failure and six error markers in inherited Accounting
fixtures. A narrow unchanged assertion reproduced the extra-journal defect;
the actuals-review setup now keeps earlier inherited scenarios on their original
fixture. Five focused and 147 broad cases passed (seven existing native-only
SQLite skips); full SQLite passed and full native found five further failing cases.
Repair validation now passes the focused and ordered native follow-ups. No assertions or tests
were removed.

Current bounded checkpoint: whole Form 1 draft register/detail and indexed office
candidate retrieval, with complete draft PDF/ZIP/JSON delivery. Original package,
source, attachment and decision verification remains mandatory. Candidate offices
are not authorization. Counts/status filtering precede 50-row paging only after
actual original-source access; malformed retained roots fail closed. Request-local
arithmetic reuse hashes the entire actual envelope; source reuse pins its actual
SPA FK and envelope hash for this actor/request, including permission denial.
Neither cache supplies currentness, review or capacity. Migration 0022 preflights
root checksums and original office identities before native DDL/backfill; original
financial evidence is unchanged. No operator migration or grants were performed.

Focused history validation: SQLite one case PASS in 642.272s; MySQL one case PASS
in 684.450s, both stores destroyed. Logs `.tmp/form1-package-register-final-sqlite.log`
and `.tmp/form1-package-register-final2-native.log`. These prove 105-version history
for all three offices, page 3, search/status, source revocation, separate export
grants, forged-index denial, retained-root corruption and migration backfill.
They predate the final request-local denial-cache refinement. Latest producer code is
frozen for full fresh-store release regressions, which include this focused case
and dependent package/review/export/print/assembly/native concurrency cases:

- SQLite PASS: `python .tmp/my_work_sqlite.py --verbosity 2`, handle 9656, exit 0;
  2,462 tests in 7,284.909s, 195 existing native-only skips. All discovered IDs
  appear exactly once, terminal count/OK confirmed and 1,132 source hashes unchanged.
  `.tmp/foundation-release-final-full-sqlite.log`, runtime `.tmp/foundation-sqlite-jdctzpxe`.
- Native: `python .tmp/retrieval_native.py --verbosity 2`, handle 64111,
  `.tmp/foundation-release-final-full-native.log`, runtime `.tmp/mysql-regression-bm7v9w0f`.

The full native run completed FAIL: 2,462 tests in 9,500.128s, one failure/four
errors, exit 1; both disposable stores destroyed. Every discovered ID appears
exactly once. Complete tracebacks are retained in
`.tmp/native-release-failure-traces.txt`. Two failures are confirmed candidate
certification fixture contamination: setup already prepares version 1 before
inherited preparation races expect an empty history. Fresh five-case reproduction
FAIL: 22.762s, one failure/one error, exit 1; the same stale-version guard rejects
both cases. Certification setup now creates its reviewed record only for scenarios
defined on the certification fixture chain; inherited preparation assertions and
all test IDs remain intact. This was the first source change after the original
1,132-file snapshot; the later cleanup repair adds four test-only changes below.
Preserve the original snapshot rather than overwriting it.
The other three full-native errors occur before officer-return races begin:
September-12 receipt capacity is rejected. Their unchanged existing test file
dates to v0.7.115. All three PASS in the fresh five-case reproduction; this does
not explain their full-suite failures or establish a repair. A fresh diagnostic
run performs complete suite discovery before selecting the two actuals modules
and officer-return module, with read-only capacity evidence printed only on
failure: `.tmp/diagnose_native_release_tail.py`, handle 40242,
`.tmp/native-release-fixture-and-return-discovery.log`. It completed PASS: 138
tests in 184.661s, no skips, exit 0; both formerly failing preparation races,
own certification races and all officer-return module cases pass. Fresh follow-up
diagnostic now selects all 280 non-atomic/simple cases in full discovery order,
including the other native classes and intervening setup/cleanup. Handle 53639,
`.tmp/native-release-all-non-atomic-diagnostic.log` completed FAIL: 280 tests in
1,259.379s, three errors, exit 1; both stores destroyed. The three
original full-suite officer-return errors have now reproduced in this ordered run.
Diagnostics show the exact September-11 release of 1,000, no holds and zero computed
September-12 capacity. Earlier diagnostics show real October releases labeled
September 18. Two manual native Form 1 factories fail to run their fixture's
cleanups, leaking the inherited PlanningContext September-18 localdate mock.
This is introduced by current candidate tests, not an officer capacity defect;
the production guard correctly rejects the inconsistent dates. All four manual
factory owners now register their cleanups before setup, including failure paths;
the two native owners also assert the exact original localdate callable is restored.
Five fixture files differ functionally from the original full-run producer
(including certification setup); one additional test file has only an extra EOF
newline removed, with its Python AST proven identical; all other 1,126 byte hashes are unchanged. A separate
`.tmp/cleanup-repair-source-fingerprint.json` preserves the new producer; original
full-run hashes/results remain intact. Check it with
`python .tmp/final_release_source_fingerprint.py --check-cleanup-repair`.
Fresh focused validation PASS: 24 native cases in 435.131s, no skips, exit 0,
both stores destroyed (handle 40526,
`.tmp/native-release-cleanup-focused.log`, runtime `.tmp/mysql-regression-24v551vy`)
and 31 SQLite cases in 21.143s, seven native-only skips, exit 0, both stores
destroyed (handle 84602, `.tmp/sqlite-release-cleanup-focused.log`, runtime
`.tmp/foundation-sqlite-pidhppcz`). Native runs both leaking providers before the
unchanged officer consumers; also checks certification races and both manual cash
factories. SQLite adds dependent planning/adoption scenarios and preserves native
skips. All five former native failures pass in the affected follow-ups; the two
providers' new cleanup assertions pass before the unchanged officer consumers.
The broad fresh follow-up PASS: all 280 non-atomic/simple cases in 1,279.465s,
no skips, exit 0, both stores destroyed, in original complete discovery order
with no application instrumentation. Command:
`python .tmp/diagnose_native_release_tail.py --verify-non-atomic`, handle 77434,
`.tmp/native-release-cleanup-broad-ordered.log`. The separate retained selected-ID
manifest matches all 280 log IDs exactly once and the original full discovery.
The publication gate verifies all five former failures pass in the affected and
ordered follow-ups, and all other 1,126 byte hashes remain unchanged.

Release validation scope: preserve the complete local native FAIL rather than
calling it PASS after focused repairs. Only five test fixtures changed behavior afterward; one additional test file
has a byte-exact EOF newline cleanup with identical AST;
application/template/dependency/workflow hashes are unchanged. Full SQLite plus
focused SQLite/native and the broad ordered native follow-up support publishing
a reviewable candidate for the mandatory fresh complete GitHub checks. This is
not approval to integrate primary: actual candidate verify/mysql must both pass
on the released SHA, then primary integration/push must be verified separately.
Do not mechanically repeat unchanged full SQLite or claim the complete native
gate already passed. If the broad follow-up fails, diagnose and repair first.
Do not weaken controls. Operator database hashes remain
unchanged; the master integration checkout remains clean (October 13 recheck).
Old diagnostic 21690/75479 were
deliberately stopped after confirmed fixture defects and verified process/schema
ownership; exit 1, not passes. Accounting repair PASS: five focused/147 broad cases
(seven existing native-only SQLite skips); calendar repair PASS: six focused cases.
Broad voucher SQLite 89418 completed: 796 tests, 646.353s, two remaining fixed-
September settlement failures and 97 existing native-only skips. The cash-expiry
assertion passed. The shared settlement scenario now fixes its payment clock and
also checks the earlier liability before payment; all 43 affected settlement/fee
module cases PASS in 31.107s. Intermediate full handles 53469/54155 were stopped
after this last fixture repair, exit 1, not passes. Final runs above include it.
Do not modify producer/tests during
them or run another native runner. Owned MySQL is on loopback 33308. Browser
rehearsal uses separate seeded stores in `.tmp/package-register-browser-20261012`.
It found a template-only compressed mobile table; the corrected minimum width
retains all columns in the horizontal container (page width 390, table 1100,
container 326 headless; headed viewport 390/document 375/table 1100/container 311).
All 11 pages of the current authenticated PDF response were inspected after hash/
parser verification; the final desktop/mobile control screenshots are readable.
JSON native browser download passed. PDF and ZIP saving canceled in the browser;
an independent 1,458-byte control PDF also failed, so native saving remains an
environmental limitation, not a claimed pass. Authenticated ZIP HTTP bytes match
the browser JSON exactly and all six original document hashes. Budget, Accounting
and Treasury register/detail browser reads and final mobile columns are verified.
The isolated official Playwright CLI 0.1.22 still fails the independent tiny PDF;
the user's global CLI/profile/settings were preserved. System check,
migration drift and patched dependency audit PASS. The first audit found 25
advisories in baseline pins; requirements now pin PyJWT 2.15.1, pypdf 6.19.0 and
urllib3 2.8.0. Full runs use verified isolated patched imports under the user's
installation directory, preserving the shared virtual environment. Old full
handles 1191/21898 were deliberately stopped/cleaned, not passes. See the
[current release validation record](docs/FINANCE_V154_RELEASE_VALIDATION.md).
Representative varied-source retrieval
latency, full intake/review actions and LGU/form/operational acceptance remain open.

Resolved focused-fixture failures remain evidence, not passes: omitted copied
attachments (SQLite 180.089s); unbounded full-root bulk inserts lost native
connection (159.200s and 160.259s); MySQL bulk-created instances lacked PKs for
attachment insertion (184.240s). All failed runs destroyed both test stores.
Fixtures now retain full attachments, bound root inserts and fetch saved PKs.
Obsolete SQLite 15443/85139 and native 20071 were deliberately stopped after
verified process ownership/producer replacement; none is an assertion pass.
Stopped native disposable schemas alone were cleaned on the verified owned server.
Logs retain exact outcomes under `.tmp/form1-package-register-*`; operator data
was not touched. Final register removes redundant assembly reproduction, streams
root candidates and retains only visible card metadata.

Release scope: origin/master is v0.7.109, with 47 earlier intended dependent Finance
commits before this worktree HEAD. Inspect combined scope and broad regression.
REST reports master unprotected/no rulesets. Draft PR 114 is historical native
capture versus its audit baseline; do not retarget it. GraphQL quota exhaustion and
the Code Review connector's missing GitHub connection are not passing CI/review.
No commit/merge/push yet. Installed Version Manager README/core and preservation
adapter inspected; `.tmp/release_finance_foundation_checkpoint.py` preview proposes
v0.7.154, updating VERSION/CHANGELOG only to preserve historical references.
Explicitly stage reviewed intended files after real release gates, execute the
actual ReleaseService, integrate master in an isolated worktree, verify remote
primary/tag and both actual verify/mysql jobs before resuming dependent Finance
implementation. Latest user steering replaces the earlier post-release pause.

Earlier native/source/forecast/account/SPA/whole-package validation and the prior
Finance dependency history are retained in
[checkpoint history](docs/FINANCE_FOUNDATION_CHECKPOINT_HISTORY_2026-10-12.md),
with authoritative contracts linked from AGENTS.md and the roadmap. The root
handoff is the current entry point; archived live-status labels are historical.

The complete printable draft previously passed genuine-source SQLite/native tests
and all 22 reviewed/unknown PDF pages were inspected. Fresh three-office browser
reads, JSON saving and authenticated PDF/ZIP response validation confirm the final
register/template; native PDF/ZIP saving remains limited as recorded above. Final
full regressions must confirm the patched dependency environment and complete
dependent suite. Never reuse an earlier producer's pass as latest proof.

## Next actions and release/incident boundary

1. CI repair v157, internal review v160 and its v164 documentation follow-up
   passed their exact-source remote gates. Preserve full logs/identities/cleanup,
   failed v154/v155/v156 records and all unrelated tags; do not recreate releases
   or restart terminal watchers. Their scope does not accept uncommitted intake.
2. The combined 74-case intake/Auth regression passes; now scope-guard
   the installed VM commit/tag, exact candidate security/verify/mysql, primary
   integration/push and resulting checks. Preserve published security fixes and
   all seven unchanged-source controls; current top section owns active handles.
3. Continue the existing versioned PhilHealth treatment proposal and independent
   return/rejection plan. Preserve unknown arithmetic until an applicable recipe
   is supported and reviewed; no checkbox, guessed offset or invented JEV may
   resolve it. Reuse original sources/locks and create fresh package successors.
   Manual LGU applicability/signature/physical acceptance remains deferred tonight.
4. Update README, roadmap, gaps and feature contracts with actual outcomes.
   Statutory certifiers, Chief Executive approval, issuance, representative source
   retrieval, exact local outputs and operational/LGU acceptance remain open.

eGAPS remains closed and untouched. Earmark-before-ARO semantics remain unconfirmed;
limited office use of eGAPS reports does not waive output/parity requirements.
Keep separate databases, independent maker/checker and immutable financial/custody
history. See [foundation gate](docs/FINANCE_FOUNDATION_GATE.md),
[required outputs](docs/FINANCE_REQUIRED_OUTPUT_MAP.md) and
[operational scrutiny](docs/FINANCE_OPERATIONAL_SCRUTINY.md).

Retry completion: Ran 267 tests in 833.475s. Overall primary security/verify/mysql and
all 19 jobs PASS. No timeout/check/assertion changes. GO for this bounded
engineering checkpoint; numerical/local/production acceptance remains NO-GO.
