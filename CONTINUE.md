# GRAND Finance continuation handoff

Mandatory gate added 2026-09-07: [post-Finance operational scrutiny](docs/FINANCE_OPERATIONAL_SCRUTINY.md). **Finance production gate: NO-GO** pending functional completion, scrutiny, critical-gap verification and LGU acceptance. Run the full scrutiny only after the current functional phase; existing tests/container work do not satisfy it. Preserve all historical and deferred roadmap items.

Last updated: 2026-10-13

## Current checkpoint - Finance foundation release

Worktree: `C:/Users/Administrator/.codex/worktrees/grand-finance-my-work`, branch
`codex/finance-budget-attribution`, based on v0.7.153 / `61e690e4`.
This handoff covers the released development v0.7.154 candidate and the later
working-tree v0.7.155 runtime repair. Master integration,
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

GitHub's push notification also exposed one Critical default-branch alert:
PyJWT [GHSA-ffc3-869f-jxw9](https://github.com/advisories/GHSA-ffc3-869f-jxw9),
affected <=2.13.0, fixed 2.14.0. Candidate 2.15.1 is outside that range.
Authenticated alert reads show 24 open old-master alerts: one Critical, 15 High,
eight Medium. Exact candidate pins are outside every returned affected range;
local pip-audit also passes. This does not close default-branch alerts or replace
actual CI. Keep dependent implementation NO-GO while those checks are pending.
These actual-result updates and the working-tree runtime repair are later than
the released SHA; do not misrepresent them as part of the candidate under test.

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
is complete; v0.7.155 execution and actual new-producer CI remain pending.
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

1. Preserve the complete terminal evidence from [candidate run 38294180301](https://github.com/tepong32/grand/actions/runs/38294180301)
   on `bc8e482bafa7da33550b1aad3380ad293638d3d0`. Verify is CANCELLED at 20 minutes;
   its dependency consistency, security audit, Django system check and migration
   steps passed but the project suite did not finish. MySQL is also CANCELLED at
   60 minutes. Both complete job logs/annotations are retained. Their interrupted
   suites have no terminal summary/full passing count; do not repeat an old
   dispatch or infer assertion outcomes from denial annotations or fixture users.
   Finish the live repaired local runs; re-poll the same handles if observation
   expires rather than restarting. Investigate every actionable failure before
   dependent implementation and obtain new exact-SHA candidate CI afterward.
2. The actual Version Manager commit/local tag, exact 402-file release and candidate
   branch push/dispatch are DONE. Do not repeat that release. The dispatch helper
   used the documented proportional local publication gate: retained full SQLite
   PASS/native FAIL, five fixture repairs, AST-identical EOF cleanup, focused and
   all 280 ordered native PASS, exact source/branch/tag provenance. This permits
   candidate publication, never primary integration without both actual CI passes.
   The later local follow-up now includes the scoped runtime service repair and
   two added regression methods. Fresh discovery preserves all 2,462 original
   IDs and adds four IDs (two inherited), total 2,466. Full fresh SQLite and
   native verification are running; affected native PASS is recorded above.
   Preserve original v154 evidence. The installed Version Manager preview selects
   v0.7.155; actual execution still awaits the repaired producer's release gates.
   Installed `GitService.commit` stages only its managed VERSION/CHANGELOG files
   and commits the existing index. After all gates pass, explicitly stage and
   verify exactly the intended repair scope before executing the installed adapter;
   do not use blanket staging or release metadata alone. Current intended scope
   is the two Accounting files, two-line CI diagnostic change, AGENTS/CONTINUE,
   incident/gap/native-testing documents and v154/v155 validation records (ten
   paths), plus the tool's two metadata updates. The index was empty on inspection.
   After actual v155 commit and candidate push, use the separately prepared
   `.tmp/dispatch_ci_runtime_candidate.py <exact-SHA>` first without `--dispatch`.
   It requires clean HEAD/local v155 tag/remote branch equality and the complete
   repaired local gate. Only then dispatch once; inspect existing exact-SHA runs
   if the POST outcome is unknown. Prior saved dispatch evidence forbids a duplicate.
   Original v154 helper and evidence remain unchanged; no v155 dispatch occurred yet.
3. Finish the runtime repair's regression and exact-SHA candidate CI gate. After
   both repaired candidate jobs pass, integrate intended dependencies into clean
   master, push primary/tag and verify the remote SHA/tag and resulting primary
   run. Record actual run URLs, outcomes and remaining limitations, then resume
   the existing Finance roadmap as requested by the latest steering. Do not
   declare incident resolution from local checks alone or treat CI green as
   production/LGU acceptance.

The clean integration checkout is synchronized to remote master `c5bd920a`;
candidate `bc8e482b` contains that history and is 48 intended commits ahead.
No candidate merge, primary push, remote v0.7.154 tag or operator migration has
occurred. Recheck remote primary and worktree cleanliness immediately before
integration; preserve the operator checkout and historical PR 114.

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
