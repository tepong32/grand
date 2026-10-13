# Finance release and Actions incident

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

This current status supersedes the historical then-pending statements below.
Original causes, severity, attribution and failed producer evidence remain
retained; candidate success does not establish LGU acceptance or production safety.

## Historical candidate runtime repair (October 12–14)

Latest repair is CI workload distribution, locally validated but unaccepted remotely:
[v157 candidate evidence](FINANCE_V157_CI_VALIDATION.md). It preserves complete
2,468-ID discovery and complete classes on isolated workers, unchanged 20/60
limits, security and native controls. Six runner checks and discovery partition
proof pass; corrected full local shard runs completed PASS on both backends.
All 2,468 native tests passed without skips, including all 195 identities skipped
on SQLite; actual exit/log/coverage/source/cleanup and preflight checks pass.
Development candidate publication is GO only; actual release refs and both
resulting remote aggregate checks must be verified. The first rehearsal's
default-pattern guard defect was repaired with an actual-command regression;
failed evidence remains retained. No primary promotion or incident closure.

Actual v156 MySQL terminal outcome: CANCELLED at `1h0m0s`, completed October 13
14:59:30 UTC on exact `d666f3abd8d7c382582dc0a76dfb1aae0fdfc92a`.
Complete raw job log: 3,309,846 bytes, SHA-256
`5eb26a20de6ae295eb1574d11f2b26b4cb00a7da4a47a8e33b3b001f7034690a`.
All nine annotations and job/step metadata are retained. The 1,108 distinct
current-discovery headers end at
`finance.test_setup_discovery_register.SetupAndDiscoveryWorkRegisterTests.test_uat_viewer_does_not_receive_setup_or_discovery_action_groups`.
There is no suite summary, failure-detail header or unittest FAIL/ERROR marker.
Service initialization, dependency installation and container cleanup succeeded;
six permission annotations map to five completed passing negative cases. Actual
full-context analysis is `.tmp/ci-runtime-v156-terminal-analysis.json`. Its initial
Windows-default JSON decoder failed to match the UTF-8 curly-apostrophe message;
explicit UTF-8 decoding fixed only that reader. Raw evidence and the actual
decoder failure log remain retained; no application change or rerun followed.
Read-only watcher 10156 is terminal exit 1. Both v156 jobs are unaccepted, so
runtime remains HIGH/OPEN and primary/dependent Finance work remains NO-GO.

Resume at 20:25 local confirmed the goal ACTIVE, but the earlier full local test
processes no longer existed. Their logs stopped at 06:59 without terminal summaries;
neither is a pass. Complete interrupted logs were preserved before restarting the
owned disposable MySQL fixture and both full runs at 12:26:37 UTC. The new runs
retain actual process exit codes and complete log hashes. No frozen application or
test source changed. See [current v156 evidence](FINANCE_V156_RUNTIME_VALIDATION.md).
This local environment interruption does not reclassify the actual candidate CI
20/60-minute timeouts or resolve the release blocker.

New full SQLite rerun PASS: 2,468 expected IDs exactly once, 2,273 passed /
195 unchanged native-only skips, 3,465.705s, exit 0 and both stores destroyed.
Frozen 1,133-source proof remains exact. The independent proof initially failed
on raw CP1252 log decoding; documented Python pipe/locale encoding was verified,
then only the reader was corrected. Raw logs/result hashes remain unchanged.
Native subsequently completed PASS: all 2,468 exact IDs, 5,084.954s, zero skips,
exit 0, both stores destroyed. Combined local publication gate PASS, including
actual log/result hashes and all 1,133 frozen source hashes. Candidate publication
is GO; actual new-candidate verify/mysql, primary promotion and resulting checks
remain pending. See the v156 report for exact proof, hashes, commands and limits.

Later actual publication: installed Version Manager executed development v0.7.156
at `d666f3abd8d7c382582dc0a76dfb1aae0fdfc92a`; exact 18 paths and source proof
verified, development push matches. [Run 38409417032](https://github.com/tepong32/grand/actions/runs/38409417032)
is on that SHA; both verify/mysql remain IN_PROGRESS in their full regression
steps. Security/system/drift and native service/setup prerequisites passed.
No full remote pass, primary integration/tag publication or incident resolution
is claimed. Outcome notes are later than the released candidate; raw original
failed/interrupted evidence remains intact. Dependent Finance implementation held.

Later v156 verify outcome: CANCELLED at unchanged 20m0s, actual annotation,
completed 14:19:15 UTC October 13. Complete log/metadata/all five annotations
retained: 2,095,630 bytes, SHA-256
`263ea7a5af3c6d1acc05590fc050adb726cd08385f42d70eb171c97a1f61f399`.
796 unique expected headers, ending in whole-package export; no complete summary
or assertion-failure markers. Security/system/drift passed, Telegram not reached.
Runtime repair remains insufficient; HIGH/OPEN. MySQL is still live, not a pass
or failure inferred from verify. Primary promotion and dependent work remain NO-GO.

**High - OPEN, introduced on the expanded candidate, not the original email
failure.** [Run 38294180301](https://github.com/tepong32/grand/actions/runs/38294180301)
tests exact v0.7.154 SHA `bc8e482bafa7da33550b1aad3380ad293638d3d0`.
Verify job `114961192633` completed CANCELLED; its actual annotation says the
job exceeded 20m0s. Setup, pinned dependency installation, pip check, audit (no
known vulnerabilities), Django system check and migration drift all passed.
Project tests have no terminal passing summary; Telegram did not run. MySQL
job `114961192443` also completed CANCELLED at 19:55:55 UTC; its actual annotation
says the job exceeded 1h0m0s. Container initialization, checkout, Python setup and
dependency installation succeeded; the fresh native test step was cancelled,
with no terminal suite summary. The service reached MySQL 8.4.12 ready-for-connections.
Complete verify log is retained in ignored `.tmp/actions-release-20261012/`
`completed-jobs/38294180301-attempt1-verify-114961192633.log`, 1,638,985 bytes,
SHA-256 `b1bd81f04a05ba95c7d523b5e4b21d877682a70f8a3d08e275424d988362c148`,
with matching metadata and five annotations. PermissionDenied annotations alone
do not establish failed tests: source export-denial scenarios intentionally
exercise those guards. Log timestamps do not establish the exact active test.
No timeout was raised or test/check skipped in this repair.
Complete MySQL log is retained in the same directory as
`38294180301-attempt1-mysql-114961192443.log`, 2,001,511 bytes, SHA-256
`a4d0978db0706392ad254256f0399609155165630fe07d0fb15a44a399b05b0c`,
with matching job metadata and seven annotations. Neither cancellation establishes
a full passing or failing assertion inventory; the suite was interrupted before
its terminal summary. This is a separate runtime blocker on the expanded candidate,
not the original scheduled run's dependency/calendar defect or service-start failure.

The candidate workflow now appends `--verbosity 2` to both full test commands to
retain exact test identities next time. All other workflow bytes, checks, limits,
selection and the two-store native runner remain unchanged. Running local full
suites already use those flags; no application/test producer changed after they
started. Their original fingerprint is retained separately from exact CI-only
provenance for these two diagnostic suffixes.

Profiling the same synthetic retained package establishes redundant joint-actuals
reconstruction as one application bottleneck. A scoped working-tree repair
verifies the original preparation/trial once per snapshot operation while fully
verifying each officer's separate observed actuals/trial. Exact role, actor,
office, source cohort, chronology and complete snapshot reproduction remain.
No persistence, approval, permission, currentness or public bypass flag changed.
Two new regression cases reject rehashed individual observation corruption and
valid later-cohort substitution. Fresh focused SQLite PASS: 49 tests in 19.381s,
no skips, both stores destroyed; the initial nonexistent class label executed
no source tests. Affected native PASS: all 108 actual-discovery IDs exactly once,
301.966s, no skips, exit 0, both stores destroyed. Full repaired SQLite PASS:
2,466 tests in 3,983.312s, exit 0, every discovery ID exactly once, the same
195 native-only skip IDs/reasons and both stores destroyed. Exact source/CI
proof is unchanged. Full repaired native PASS: 2,466 tests in 5,723.615s,
no skips, exit 0, every discovered ID once and both stores destroyed. Both
actual remote jobs remain required. See the
[current validation](FINANCE_V155_RUNTIME_VALIDATION.md) for commands and logs.
All five original full-native failure/error IDs pass within this completed full
suite, including the three officer-return races after the repaired factories.
The exact source/CI and complete local publication gate passed. Its initial
Telegram namespace/root-membership assumptions were corrected against actual
scoped discovery and source; the separate five-test CI step passes unchanged.
Candidate publication is GO; primary/dependent work awaits actual remote passes.
Installed Version Manager executed v0.7.155 / `e6e1cb8e1a65121dcd392271a23f9cf618da3d23`,
exactly twelve repair/metadata paths. Development push and local tag were verified.
Guarded dispatch created [repaired run 38311451830](https://github.com/tepong32/grand/actions/runs/38311451830)
on that exact SHA. Verify completed CANCELLED at its unchanged 20-minute limit;
MySQL also completed CANCELLED at its unchanged 60-minute limit, ending 22:34:36
UTC on October 12 (actual annotation 1h0m0s). Its complete log has 809 distinct
original test headers, ending in the package permission/UAT case, no terminal
summary or method-failure marker. Service/dependency steps passed. All seven
annotations and 2,234,354 raw log bytes are retained; SHA-256
`e193b85977e95c172e4d7b8c7bfc4417a71cbadb2ea0c2eec80994f26bb01622`.
The four denied-access annotations map to completed passing negative-permission
cases; none establishes an assertion failure. Partial native intervals include
340.901s package history and 224.231s account history (setup/body/cleanup included).
These do not establish a whole-suite pass. The complete verify log contains 797 distinct named
test headers and no terminal summary. Its last named test is whole-package export;
that does not establish the sole bottleneck. Full log/metadata/five annotations
are retained in the current validation record. Two denied-export annotations
map to completed passing negative-permission cases. The scoped optimization is
insufficient for CI; runtime remains High/OPEN. The genuine export profile has
since completed: one case PASS / 191.746s under cProfile, 1,840 joint snapshot
reconstructions. The [subsequent bounded repair](FINANCE_V156_RUNTIME_VALIDATION.md)
removes duplicate summary/SPA construction and reuses complete exact pure evidence
within one operation. Its first four-file focus passed 13 SQLite / 16 native cases;
fresh scoped-reuse runs and full new-producer/remote proof remain pending.
Same-package reads now measure 0.915/0.862s with original snapshot/checksum and
both synthetic stores unchanged. This remains diagnostic, not a complete CI result.
Do not raise limits for green.
Master/remote-tag integration and resulting primary checks remain pending.
Do not repeat release/dispatch or reinterpret v154's cancellations as passes.

Controlled fresh-actor reads fell from 5.313/5.379s to 2.420/2.440s; profile calls
fell from 43,828,078 to 20,937,138 (13.764s to 6.591s). Exact original joint
snapshot, package checksum and both synthetic store hashes remain unchanged.
Private before/after logs and profiles are retained under `.tmp/ci-runtime-`
`package-read-*`. This does not establish the entire timeout cause or CI success.
The original v0.7.154 full-test/source evidence is historical; a new producer
requires its own checks and exact-SHA remote run. Primary integration and dependent
Finance implementation remain NO-GO. Next Finance milestone is unchanged: guided
whole Form 1 preparation/intake/review after repaired verify/mysql pass.

## Original remote evidence (retained)

Authenticated GitHub REST reads retained complete run/job metadata, annotations
and full ZIP job logs under ignored `.tmp/actions-incident-20261012`. Credentials
were neither printed nor retained. Public browser observations verified run 139
and its job IDs; unauthenticated UI log expansion was unavailable.

| Run | SHA | Actual result |
| --- | --- | --- |
| [139, October 12](https://github.com/tepong32/grand/actions/runs/38217045795) | `c5bd920a650e5ade538cafd259de1f730fa81eea` | verify dependency audit failed; mysql 1,193 tests, 9 failures/46 errors, 1327.825s |
| [138, October 5](https://github.com/tepong32/grand/actions/runs/37275248892) | same | verify dependency audit failed; mysql 1,193 tests, 9 failures/45 errors, 1422.103s |
| [136, September 28](https://github.com/tepong32/grand/actions/runs/36388391654) | same | both jobs PASS; native 1,193 tests, 1106.057s |

Run 139 verify job `114704106760` failed at Audit Python dependencies. Native job
`114704106984` failed at Run fresh native two-store regression. Both annotations
say exit code 1; notices concern the future Ubuntu runner-image migration.
Job metadata matches the supplied notification exactly: verify 36 seconds,
native 1,505 seconds (25 minutes 5 seconds). Run 138 instead took 23/1,603 seconds,
so the screenshot identifies run 139 rather than relying only on recency.
These are completed assertion/error/audit failures, not job timeouts or failed
MySQL service startup. Python 3.11 setup, dependency installation and native
database/migration startup completed. The failing SHA's workflow was inspected:
verify timeout 20 minutes, native timeout 30 minutes. Development already changed
native timeout to 60 in v0.7.112 (`ce0c724`), before this repair; neither observed
failure reached a timeout. No timeout, check, test or assertion was relaxed here.

The candidate base also has an actual passing comparison:
[development run 36234943262, September 26](https://github.com/tepong32/grand/actions/runs/36234943262),
SHA `61e690e4eb22c8cc3c9fe1d39c9389e2b5e81ac3` (v0.7.153). Both jobs passed:
SQLite 1,593 tests in 686.222s with 125 skips, native 1,593 tests in 2026.716s,
and the five separate Telegram tests passed. Complete metadata, annotations and
job logs are retained with the incident evidence. This does not establish the
current 2,462-test candidate or the patched dependencies; its new fixture defect
is classified separately below.

## Findings and repair state

**Critical on existing master; remediated in candidate pins, remote confirmation
pending.** The actual candidate push returned GitHub's default-branch alert
summary. Authenticated Dependabot reads retain 24 open alerts (one Critical,
15 High, eight Medium) under ignored `.tmp/actions-release-20261012`.
Critical alert 341 is [PyJWT asymmetric-PEM guard bypass](https://github.com/advisories/GHSA-ffc3-869f-jxw9):
affected <=2.13.0, first fixed 2.14.0; this existed in the old master pin.
The candidate's 2.15.1 is outside that range.
The [maintainer advisory](https://github.com/jpadilla/pyjwt/security/advisories/GHSA-ffc3-869f-jxw9)
rates it Critical, CVSS 9.1: a deployment that mixes symmetric and asymmetric
verification algorithms and supplies a public PEM key in a loader-accepted but
guard-missed format can accept a forged token. This is configuration-dependent;
the existing limited application search does not prove all authentication
dependencies or deployments are unaffected. Retain the severity and patched pin.
Exact candidate requirement pins were compared with all 24 returned affected
ranges, with none still matching;
GitHub's exact-version `=` notation was normalized only to PEP 440 `==` for that
comparison. This is a range assessment and local audit evidence, not proof that
master alerts closed or remote checks passed. Primary and affected feature work
remain blocked pending both actual jobs.

Installed Version Manager created v0.7.154 / `bc8e482bafa7da33550b1aad3380ad293638d3d0`;
the exact candidate branch was pushed and explicitly dispatched. [Run 38294180301](https://github.com/tepong32/grand/actions/runs/38294180301)
is in progress with both jobs, not a resolved incident. Primary integration/push
and tag publication remain pending. This actual-results paragraph is a local
documentation follow-up; it is not in the SHA already being tested.

**High: dependency security gate.** Run 139 reports 25 advisories across PyJWT
2.13.0, pypdf 6.16.1 and urllib3 2.7.0. These unchanged master pins predate the
current unpublished checkpoint; audit information changed while the commit did
not. Candidate pins 2.15.1/6.19.0/2.8.0 pass local pip-audit with zero known
vulnerabilities. Primary release notes and actual import verification are in
the candidate validation record. This is not yet a remote repair pass or an
assessment that every advisory has equal severity/exploitability.

Maintainer severity evidence: PyJWT's [BOM algorithm-confusion advisory](https://github.com/jpadilla/pyjwt/security/advisories/GHSA-r6x4-923q-g947)
and [JWKS redirect advisory](https://github.com/jpadilla/pyjwt/security/advisories/GHSA-9v7f-9g4p-ffgj)
are High (CVSS 7.4), with configuration/attacker-controlled endpoint preconditions.
[urllib3's release notes](https://urllib3.readthedocs.io/en/stable/changelog.html#id1)
classify proxy TLS and unbounded chunk-header buffering as High and Deflate looping
as Medium. [pypdf's maintained changelog](https://pypdf.readthedocs.io/en/latest/meta/CHANGELOG.html)
records parser/resource limits. GRAND directly uses pypdf in reporting templates
and retained Form 1 source composition. No direct custom PyJWT/JWKS client was
found in the searched application modules; dependency/allauth routes remain
relevant, and this limited search is not proof of non-exploitability. All audited
pins are remediated together rather than suppressing an allegedly unused finding.

**High release blocker: calendar-dependent native test scenarios.** Complete
run-139 traces show 43 missing AccountingPeriod errors, two absent-open-period
posting errors, nine payable balance assertions and one expired cash-position
error. Existing fixtures create August 2026 and the wall-clock current month,
while return/correction scenarios use explicit September dates. Payment release
uses the current date while the affected assertion reads September 30. Run 138
has the same failures except the later cash-position expiry. Last passing run
uses the identical SHA: these are pre-existing fixture/calendar dependencies,
not evidence that the unpublished Finance changes introduced the incident.
All nine remote balance failures are inherited instances of
`test_exact_reversal_reopens_dv_then_corrected_deduction_and_payment_reconcile`;
the fixed scenario clock repairs their shared date assumption rather than changing
claim arithmetic or nine independent production routes.
Local reproduction FAIL: three cases, 13.839s, one failure/two errors with the
same remote traces. Repair adds the explicit historical September period to the
shared synthetic voucher fixture, reuses it when September is the current month,
and fixes the corrected-settlement/cash-enforcement scenarios at September 15.
The cash test also explicitly rejects issuance on October 6 after the unchanged
35-day limit. Production clocks and period/capacity/age controls are untouched.
Focused repair PASS: six cases, 27.592s on fresh two-store SQLite; this predates
the additional October-6 assertion, which is included in the broader voucher and
fresh full runs. Preserve
all posting-period, dated-capacity and cash-age controls and every assertion.

**High candidate release blocker: actuals-review fixture contamination.** Current
full SQLite/native progress independently shows 24 failures/six errors in earlier
tests inherited by NativeActualsReviewTests, certification and view classes.
The original receipt/deposit assertion expects two journals but gets three from
the review setup's additional receipt. Narrow SQLite reproduction FAIL:
one test, 3.328s, `AssertionError: 3 != 2`; caused by current candidate test setup.
The review setup now adds its receipt only for review/certification/view scenarios
defined on that fixture chain; inherited earlier scenarios retain their original
setup. No test IDs, assertions or production controls were removed. Narrow
validation PASS: five cases, 12.540s. Broader affected modules PASS: 147 cases,
88.680s, seven existing native-only skips on SQLite. Actual discovery still has
2,462 unique IDs. Native verification remains required; other failures must be
checked before declaring repair.

## Remaining validation and next milestone

**High candidate release blocker: native certification concurrency fixture.**
The final native run has reported one FAIL and one ERROR in inherited
`NativeActualsCertificationConcurrencyTests.test_competing_preparation_and_review_retain_single_version_decision`
and `test_successor_and_old_approval_serialize_without_old_current_use`.
The new certification test file is untracked relative to the v0.7.153 base, so
these candidate cases are separate from the original master notification.
Source inspection shows the derived setup creates an already-reviewed preparation
before inherited preparation/version races expect their original empty preparation
fixture. Terminal tracebacks and the fresh five-case reproduction confirm this
diagnosis: both inherited scenarios fail on the unchanged stale-version guard.
The final full native result is 2,462 tests in 9,500.128s, one failure/four errors,
exit 1; all discovered IDs appear exactly once and both stores were destroyed.
The focused reproduction ran five tests in 22.762s, one failure/one error, exit 1.
Certification setup now creates its reviewed preparation only for certification
scenarios, preserving inherited empty-history setup, assertions and test IDs.
The original 1,132-file source snapshot is retained; this fixture file was the first
subsequent source change, followed by the four cleanup repairs described below.
Fresh affected native modules PASS: 138 tests in
184.661s, no skips, exit 0, with complete discovery before selecting the original
test IDs. Both previously failing inherited races and the certification class's
own races pass; all officer-return module cases also pass. Log:
`.tmp/native-release-fixture-and-return-discovery.log`.
Do not treat SQLite's skips of these native cases as evidence they pass, remove
the inherited tests, weaken assertions or declare the release ready.

**High candidate release blocker: leaked Form 1 factory clock.** Three ERROR markers
appeared in `OfficerReturnConcurrencyTests` for replacement/expense capacity,
return-correction/expense capacity, and return-post recovery/case-before-Finance
locking. The existing `vouchers/test_advance_cheque_returns.py` file has no current
diff; its last committed change is v0.7.115 / `36a4974` on September 15. Complete
traces show these errors occur during setup before any race: capacity refuses the
September-12 receipt. All three cases PASS in the fresh five-case reproduction.
Isolated passing cases did not resolve the interaction. A fresh diagnostic performs complete discovery before selecting
actuals certification/preparation and officer-return modules, retaining read-only
capacity evidence on failure (`.tmp/native-release-fixture-and-return-discovery.log`,
handle 40242) completed PASS as above. The next fresh diagnostic selects all 280
non-atomic/simple cases in the original full discovery order, including every
native concurrency case and the intervening SimpleTestCase setup/cleanup:
`.tmp/native-release-all-non-atomic-diagnostic.log`, handle 53639.
It has now reproduced all three errors with the unchanged officer tests and
financial controls. Capacity diagnostics retain actual September 11 releases of
1,000.00, no expense/refund holds, and zero computed released capacity on September
12. Other diagnostics show actual October release timestamps reported as September
18: the process-wide localdate patch is leaking. The run completed FAIL: 280 tests
in 1,259.379s, three errors, exit 1, both stores destroyed. It is not a full-suite
passing result.

Source inspection identifies the responsible candidate isolation defect:
`budget/test_form1_package_concurrency.py` and
`budget/test_form1_package_review_concurrency.py` manually instantiate a source
factory and call its `setUp()` without arranging its `doCleanups()`. That setup
reaches `PlanningContextTests.setUp`, which patches `timezone.localdate` to
September 18 and registers its stop on the factory instance. The outer native
test does not run that instance's cleanups. A September 11 release therefore
appears dated September 18 when the later test checks September 12 capacity, and
the production guard correctly rejects it. This interaction was introduced by
the current new Form 1 test fixtures, rather than the original master incident or
a production capacity defect. The ordered diagnostic retains the actual evidence
before repair. Two other manual Form 1 cash factories also omit cleanup of temporary
settings/directories; include their lifecycle in the bounded fixture isolation
repair. All four manual factory owners now register `doCleanups` before setup;
cleanup failures remain assertion failures. The two native owners also assert
the exact original localdate callable is restored. Every original date, amount,
assertion and discovered test ID is retained. Fresh focused validation completed:
24 native cases (both providers before unchanged officer consumers, certification
races and cash factories), handle 40526 / `.tmp/native-release-cleanup-focused.log`;
31 SQLite cases (cash factories and dependent planning/adoption), handle 84602 /
`.tmp/sqlite-release-cleanup-focused.log` completed PASS in 21.143s, seven existing
native-only skips, exit 0, both stores destroyed. Native PASS: all 24 cases in
435.131s, no skips, exit 0, both stores destroyed; clock restoration assertions
pass before the unchanged officer consumers. Broader fresh ordered native
verification PASS: all 280 non-atomic/simple cases in 1,279.465s, no skips,
exit 0, both stores destroyed, no application instrumentation; handle 77434 /
`.tmp/native-release-cleanup-broad-ordered.log`. Selected log IDs match all 280
retained original-discovery IDs exactly once. All five former failures pass;
all other 1,126 byte hashes are unchanged. Candidate publication is GO;
primary integration and dependent implementation remain NO-GO until actual CI.
Complete candidate verify/mysql CI remains required before primary integration.

Broader voucher SQLite FAIL: 796 cases, 646.353s, two settlement date failures and
97 existing native-only skips. It confirmed the cash-expiry assertion passes and
identified the same September-cutoff/current-payment mismatch in the returned
remittance settlement and its fee variant (the earlier missing-period failures
had masked this assertion). The shared settlement scenario now fixes its clock
at September 15 and also asserts the September-14 liability is still 1,450 before
payment while retaining the original September-30 balance assertion of 500.
Affected settlement/fee modules PASS: all 43 cases, 31.107s, no skips on SQLite.

Original full diagnostic handles 21690/75479 were deliberately stopped after
the required fixture repairs; exit 1, not complete-suite passes. Only their
verified Python workers were stopped. The two disposable schemas were cleaned
after ownership/port checks, and fresh repaired full runs started at verbosity 2:
Intermediate handles 53469/54155 were also deliberately stopped after the final
settlement repair, exit 1, not complete-suite passes. Final fresh full runs are
SQLite handle 9656 (`.tmp/foundation-release-final-full-sqlite.log`) and native
handle 64111 (`.tmp/foundation-release-final-full-native.log`). Both retain all
2,462 tests and include the final setup/scenario changes. The final SQLite run
completed PASS: 2,462 tests in 7,284.909s, 195 existing native-only lock/visibility
skips, exit 0. Logged IDs match all discovered IDs exactly once and the candidate's
1,132 source hashes were unchanged through both completed full runs. The final
native run failed as detailed above; five fixture files have since changed behavior, with one separate EOF-only
cleanup proven to retain its AST, with all other 1,126 byte hashes unchanged. Fresh repaired
broad native verification, actual Version
Manager release, integration and resulting verify/mysql Actions results remain
required. Do not change timeouts or suppress failures to obtain green status.
Once both remote jobs pass, resume the existing Finance foundation checkpoint;
do not restart the project or treat CI green as official LGU output acceptance.
