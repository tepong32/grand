# GRAND Finance continuation handoff

Mandatory gate added 2026-09-07: [post-Finance operational scrutiny](docs/FINANCE_OPERATIONAL_SCRUTINY.md). **Finance production gate: NO-GO** pending functional completion, scrutiny, critical-gap verification and LGU acceptance. Run the full scrutiny only after the current functional phase; existing tests/container work do not satisfy it. Preserve all historical and deferred roadmap items.

Last updated: 2026-10-13

## Current checkpoint - Finance foundation release

Worktree: `C:/Users/Administrator/.codex/worktrees/grand-finance-my-work`, branch
`codex/finance-budget-attribution`, based on v0.7.153 / `61e690e4`.
This handoff accompanies the v0.7.154 release candidate. Master integration,
resulting remote checks and deployment are not yet confirmed here; inspect the
actual branch/tag/run evidence before continuing dependent implementation.

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

1. Collect full-run terminal outcomes; investigate/fix actual regressions and
   validate native races, complete original draft downloads and readable mobile
   columns. Record actual skips and unperformed acceptance.
2. Reconcile release validation/roadmap, inspect the final explicit file scope and
   Version Manager preview, commit/tag through its installed ReleaseService, then
   push the intended candidate branch. A branch push does not trigger this workflow:
   dispatch `security.yml` explicitly for that branch and verify the run's exact
   released SHA and both verify/mysql outcomes before integrating into master.
   Preserve canonical operator files, historical evidence and the old PR's scope.
   Prepared helper `.tmp/dispatch_release_candidate_ci.py <released-SHA>` checks
   the real tag/clean candidate, full local terminal coverage, unchanged source
   hashes and exact published branch SHA without dispatching by default. Append
   `--dispatch` only after those gates pass. Syntax check passed; it has not been
   executed or dispatched. HTTP 204 confirms a request, never a passing CI run.
3. After both candidate jobs pass, integrate intended dependencies into clean
   master, push primary/tag and verify the remote SHA/tag and resulting primary
   run. Record actual run URLs, outcomes and remaining limitations, then resume
   the existing Finance roadmap as requested by the latest steering. Do not
   declare incident resolution from local checks alone or treat CI green as
   production/LGU acceptance.

The Finance goal is not complete. Whole-package intake/review UI, representative
varied-source retrieval latency, statutory certifiers/Chief Executive approval/
issuance, exact local form acceptance and all remaining foundation/Finance/
operational gates remain governed by [foundation gate](docs/FINANCE_FOUNDATION_GATE.md),
[Finance roadmap](docs/FINANCE_ROADMAP.md),
[required outputs](docs/FINANCE_REQUIRED_OUTPUT_MAP.md) and
[operational scrutiny](docs/FINANCE_OPERATIONAL_SCRUTINY.md).
eGAPS is closed and untouched. Earmark-before-ARO semantics remain unconfirmed;
limited office use of eGAPS reports does not waive output/parity requirements.
Keep separate databases, independent maker/checker and immutable financial/custody
history. Production remains NO-GO pending the preserved gates and LGU acceptance.
