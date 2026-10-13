# Form 1 repeated integrity reconstruction - v0.7.156 candidate validation

Status, October 13: **GO for candidate publication after complete local validation;
NO-GO for primary integration, dependent Finance implementation and production.**
This report records the v0.7.156 source candidate before publication, based on
development parent v155 / `e6e1cb8e`. Inspect Git/tag/Actions for actual later release
state; no primary integration or remote pass is claimed here. The parent's verify
and MySQL jobs both timed out at their unchanged 20/60-minute
limits, without terminal suite summaries. Complete metadata/logs/annotations
are retained; both are CANCELLED, neither PASS. See the
[incident](FINANCE_CI_INCIDENT_2026-10-12.md), [v155 evidence](FINANCE_V155_RUNTIME_VALIDATION.md),
[handoff](../CONTINUE.md) and [gap register](FINANCE_GAP_REGISTER.md).

## Evidence and current changes

The complete genuine export profile passed one test in 191.746s under cProfile,
exit 0, both disposable SQLite stores destroyed. Profile total 873,287,954 calls /
346.394s includes 152.674s of fresh migration/setup work; instrumented timings are
not normal latency. The test body accounts for 110.880 cumulative seconds and
fixture setup 78.944s. Function cumulative totals overlap and must not be added.
There are 1,840 joint snapshot reconstructions. Retained private artifacts:
`.tmp/ci-runtime-package-export-case.prof`, its `.log` and profile summary.

Native `summary_sources.verify` verified a snapshot, then called a public projector
that verified it again. Its private projector now consumes the body freshly
verified by the same operation. Public projection still verifies fully, and exact
identity/scope/rows/totals/checksum comparisons and joint-certification requirements
remain. `form1_spa_output.package` likewise constructed an original account flow
inside snapshot verification and immediately reconstructed it again. A private
helper now returns that already verified flow to the same caller; public snapshot
verification retains its original return contract and complete checks.

New genuine-source regressions reject rehashed projection scope/row/total drift
and a genuine pending successor. The existing SPA tamper case additionally
rejects a rehashed invalid account allocation through both public entry points.
No test or original assertion was removed. The original first seven-case SQLite
run passed in 22.956s before the additional SPA repair and corrected receipt-total
field assertion; it is intermediate evidence, not final-producer validation.
The subsequent four-file producer fingerprint contains 1,132 sources and discovers
2,468 root-suite IDs, preserving all prior 2,466 IDs with two new cases.

Read-only measurements on the same retained synthetic package preserve its original
joint snapshot, package checksum and both store hashes. After summary projection
reuse: 1.817/2.000s, 15,422,610 profiled calls / 4.746s; after both repairs:
1.806/1.772s, 13,753,014 calls / 4.922s. These later measurements ran while focused
tests were active; they are diagnostic comparisons, not an operational SLA or proof
the full CI budget is satisfied. A separate ignored read-only experiment reuses
only exact JSON evidence for two pure validators within one package read:
1.980s ordinary / 0.950s experimental; four of five account verifications and ten
of twelve summary-source verifications repeat identical evidence. Original package
and both synthetic stores remain exact. This experiment is not application code,
an authorization cache, regression proof or release acceptance.

## Remaining gate

The first four-file repair passed all 13 focused SQLite cases / 230.332s and
all 16 native cases / 259.031s, no skips, both stores destroyed, exit 0.
Its source hashes stayed exact. The subsequent scoped-reuse producer now contains
1,133 source hashes (ten changed/new source files, all other v155 bytes unchanged)
and the same 2,468 discovered IDs. Preserve both fingerprints.

`form1_integrity` holds only successful verification keys in an operation-local
ContextVar. Two pure validators (account draft and summary source) participate;
keys hash the complete actual JSON input, including claimed checksums. JSON-coercible
non-JSON shapes, non-string keys/subclasses and nonfinite numbers receive original
uncached verification. Nested operations reuse the same keys; the outer `finally`
resets the context even on failure. Hits return this caller's own payload, never
a retained mutable result. No model/authorization/currentness result participates.
Operation boundaries cover whole-package reads/preparation/verification, SPA
snapshot/output/review integrity, assembly and PhilHealth inventory. All original
checks and source/attachment/decision/currentness operations remain.
The genuine source regressions also cover changed nested evidence with its old
claimed checksum, tuple-to-JSON coercion, caller-copy isolation and a changed
nested account draft after the original account flow has already been verified.

On the same retained package, actual scoped reuse measured 0.915/0.862s,
7,119,351 profiled calls / 2.495s. Original snapshot/package checksum and both
synthetic store hashes remain exact. Measurements ran beside focused tests;
do not claim operational latency acceptance or a complete remote result.
System check and migration drift PASS, both guarded synthetic stores unchanged.
Dependency audit PASS, no known vulnerabilities; Python 3.11, Django 5.2.17
and exact isolated patched dependency imports/metadata verified.

Fresh scoped-reuse focus PASS: SQLite handle 53991, exit 0, 13 tests / 184.787s;
native handle 96320, exit 0, 16 tests / 214.341s. Neither skips any case; both
default/Finance stores were destroyed. Logs are
`.tmp/ci-summary-reuse-focused-sqlite.log` and `focused-native.log`.
Separate Telegram PASS: five tests / 0.482s, no database setup. Dependency consistency
PASS: no broken requirements. These do not replace full/new-producer remote proof.

Earlier full fresh scoped-reuse runs used SQLite handle 18438, native handle 15756;
logs `.tmp/ci-summary-reuse-full-sqlite.log` and `full-native.log`. Source remains
frozen; neither earlier run produced a full terminal result. Native uses the documented
fresh two-store runner and the owned disposable loopback server. Do not start a
second native runner on its schemas. Source capture/discovery evidence is
`.tmp/ci-summary-reuse-source-fingerprint.json` / `ci-summary-reuse-test-discovery.json`.
Full new-producer regressions, dependency/system checks, actual Version Manager
preview/execution and exact-SHA remote verify/mysql remain required. Neither v155's
local passes nor the diagnostic experiment prove this producer. No timeout, source
authority, currentness observation, financial guard, approval, lock, history,
database routing or purchased scope is relaxed. Manual overnight items remain
deferred in the handoff, not accepted.

Installed Version Manager preview PASS: v0.7.156, uniform commit subject
`Release v0.7.156: fix(finance): reuse verified Form 1 evidence within each operation`;
only VERSION and CHANGELOG updates, preserving historical release evidence.
Actual execution, primary integration, push/tag verification and exact-SHA remote
checks remain pending. Preview log `.tmp/version-manager-preview-v156.log`.

Resume check October 13, 20:25 local: app goal ACTIVE. Earlier full handles
18438/15756 no longer exist; no test process or owned MySQL listener remained.
Both logs stopped at 06:59 local, 817 SQLite / 803 native started cases, with no
terminal summary. Outcome: INTERRUPTED - ENVIRONMENTAL; precise interruption
cause remains unknown, and no application failure or pass is inferred.
Read-only OS inspection reports last boot at October 13, 20:14:50 local; this
confirms an environment restart, not the exact reason the earlier logs stopped.
Complete interrupted logs are preserved under
`.tmp/ci-summary-reuse-full-*-interrupted-20261013-0659.log`. Their SHA-256 values
are SQLite `b2bf1871764fe5403a1557fa55c448d9cd737ef74d319edb2bc11286641de2a3`,
native `d73d25c607f3befdf1516dd9d80f932c4476826067238bf69b2b93afc31b3bf7`.
All 1,133 frozen source hashes still match. Owned MySQL was restarted with verified
loopback/strict-mode/data-directory identity. Full fresh reruns began 12:26:37 UTC:
SQLite handle 98606 / PID 33156, native handle 84146 / PID 28224. The wrapper
`.tmp/rerun_full_reuse.py` retains separate start/result metadata and actual exit
codes/log hashes. Missing terminal metadata or started-case counts are never PASS.
Do not overlap another native runner. Actual v156 release, remote verification,
primary integration and dependent feature implementation remain pending the gates.

After resume, refreshed dependency consistency and audit both PASS, exit 0;
no broken requirements / no known vulnerabilities. Actual imported versions and
metadata still verify Python 3.11, Django 5.2.17 and all three isolated patched
dependencies. Commands: documented Python running
`.tmp/check_ci_runtime_dependencies.py check` / `audit`; new logs
`.tmp/ci-summary-reuse-resume-pip-check.log` and
`.tmp/ci-summary-reuse-resume-security-audit.log`. Earlier successful logs remain
unchanged. The audit's Windows short-path/junction notice is retained; imports
and versions were verified, and the actual audit exited successfully.

Live observation now checks individual unittest FAIL/ERROR markers as well as
failure-detail headers; detail headers appear only at the end of a full run.
The detector was checked against the retained v154 full-native diagnostic and
identifies all five actual failures. Current partial logs have neither marker
type. This improves early observation only; the complete-suite/exit-code/source
and exact-ID release gates remain required, and no partial pass is inferred.

## Actual full SQLite result

PASS: documented Python `.tmp/rerun_full_reuse.py sqlite` executed the fresh
`.tmp/my_work_sqlite.py --verbosity 2` runner. Handle 98606 completed exit 0 at
13:26:39 UTC, October 13. All 2,468 expected test IDs appear exactly once;
2,273 passed and the 195 native-only skipped IDs/reasons match the prior producer
exactly. Summary: `Ran 2468 tests in 3465.705s`, `OK (skipped=195)`. Both default
and Finance test stores were destroyed; all 1,133 source hashes still match.
Complete raw log SHA-256:
`59c906aa4b124ea71f862b36cd883835ccbd0ffb2b7a28041da4b41b62e81354`.
Original start/result metadata and independent completion proof are retained in
`.tmp/ci-summary-reuse-full-sqlite-rerun-*.json` and
`.tmp/ci-summary-reuse-sqlite-completion-proof.json`.

The first independent proof command failed in its strict UTF-8 decoder, not in
the application or test suite. New wrappers capture raw Windows Python pipes:
stdout/stderr/locale all report CP1252, UTF-8 mode 0. Both new full logs contain
CP1252 byte 0x92 in the expected `Use this package’s original office...` denial.
The readers now strictly decode these new full captures as CP1252; earlier
scoped captures remain UTF-8. No raw log bytes, result metadata, assertions or
source were changed, no decoding error is discarded, and no rerun was used to
obtain this pass. Native handle 84146 remains live and its full result is pending.
v156 execution, primary promotion and remote confirmation remain pending; this
SQLite pass alone does not close the incident or establish Finance acceptance.

## Actual full native result and local publication gate

PASS: documented Python `.tmp/rerun_full_reuse.py native` executed the fresh
`.tmp/retrieval_native.py --verbosity 2` wrapper over the committed two-store
MySQL runner. Handle 84146 completed exit 0 at 13:54:51 UTC, October 13.
All 2,468 expected IDs appear exactly once; all passed, no skips. Summary:
`Ran 2468 tests in 5084.954s`, `OK`. Both default and Finance test stores were
destroyed. Complete raw CP1252 log SHA-256:
`172794e6c1418e4971202328624d3cd5e1def3f888b5b2786384dcafa2f11fef`.
Original start/result metadata remains in
`.tmp/ci-summary-reuse-full-native-rerun-*.json`; no completed handle is polled again.

Combined local publication gate PASS, exit 0:
`.tmp/verify_ci_summary_candidate_gate.py` verifies both actual exit codes and
complete log hashes, exact full IDs, unchanged SQLite skip identities/reasons,
zero native skips, both-store cleanup, genuine focus IDs (13 SQLite / 16 native),
all five explicit Telegram tests, system/drift/dependency/audit results and all
1,133 frozen source hashes. Log `.tmp/ci-summary-reuse-local-publication-gate.log`.
GO applies to publishing this candidate for actual GitHub verification only.
Neither earlier interrupted logs nor v155's results substitute for these passes.
Primary integration, remote tag publication and dependent implementation still
require actual new-candidate verify/mysql success and the resulting primary checks.
Installed Version Manager preview was refreshed successfully without any file/Git
change; `.tmp/version-manager-preview-v156-resume.log`. Actual release identity
must be verified from Git and retained execution evidence, not inferred from preview.

## Actual development publication (later observation)

Installed Version Manager executed v0.7.156 / `d666f3abd8d7c382582dc0a76dfb1aae0fdfc92a`,
parent `e6e1cb8e`. Exact 18 intended paths, uniform subject, clean release HEAD,
local tag and unchanged source proof were verified. Development push matches;
master remains `c5bd920a`, remote v156 tag unpublished. Guarded dispatch preview
passed; one actual dispatch returned HTTP 204 at 13:58:40 UTC, October 13 and
created [run 38409417032](https://github.com/tepong32/grand/actions/runs/38409417032)
on that exact SHA. Jobs verify `115337497255` / mysql `115337496904` are
IN_PROGRESS in the project/native test steps. Verify installation, consistency,
audit, system and drift prerequisites passed; native service/setup prerequisites
passed. Neither full job is PASS yet. Source remains unchanged; these outcome
notes postdate the candidate and do not rewrite its committed evidence.
Default-branch push warning still reports 24 alerts (one Critical/15 High/eight
Moderate); development publication does not close them. Primary/tag integration,
resulting primary checks and incident resolution remain pending.

Later verify outcome: CANCELLED, actual annotation `20m0s`, completed October 13
14:19:15 UTC. Complete log has 2,095,630 bytes, SHA-256
`263ea7a5af3c6d1acc05590fc050adb726cd08385f42d70eb171c97a1f61f399`;
all five annotations/step metadata retained under
`.tmp/actions-release-20261012/completed-jobs/38409417032-attempt1-verify-115337497255*`.
796 distinct expected test headers; last is the complete reviewed whole-package
export case. No full summary, failure-detail headers or unittest FAIL/ERROR markers.
Project tests were interrupted; Telegram was not reached. Security/system/drift
prerequisites passed. Two separate-source permission annotations require their
test-context interpretation, not an assumption of failed assertions. MySQL remains
live. Runtime is HIGH/OPEN and the measured repair remains insufficient for CI;
primary/dependent implementation and production remain NO-GO.

Subsequent actual profile completion: the current-producer complete reviewed
export case PASS, 96.329s under cProfile, actual process exit 0 and both stores
destroyed. Full profile time 254.811s includes fresh setup (156.405s); deepcopy
has overlapping cumulative cost 56.386s. Previous producer's same instrumented
case was 191.746s; the measured improvement does not establish complete CI or
an ordinary retrieval SLA. All 1,133 frozen source hashes still matched before
the subsequent CI-only repair began. The two denied-export annotations map to
completed `ok` cases in NativeCashCertificationViewTests and
NativeCashPreparationViewTests. Exact methods and compact profile analysis are
retained in `.tmp/ci-runtime-v156-export-profile-analysis.json`; raw log/profile
remain unchanged. Further workload distribution is tracked separately in
[candidate v157 evidence](FINANCE_V157_CI_VALIDATION.md).

Actual MySQL terminal outcome: CANCELLED at the unchanged `1h0m0s` limit,
completed October 13 14:59:30 UTC. Complete 3,309,846-byte raw log SHA-256
`5eb26a20de6ae295eb1574d11f2b26b4cb00a7da4a47a8e33b3b001f7034690a`;
all nine annotations and step metadata retained. It has 1,108 distinct expected
named starts, no terminal summary, no failure-detail headers or unittest failure
markers. Last started case is the setup/discovery UAT-viewer register case.
Six permission annotations map to five completed passing negative cases; they
are not six failed assertions. Both current jobs are now terminal CANCELLED.
Watcher 10156 completed exit 1 and must not be repolled/restarted. Current full
local passes do not replace the required actual remote checks; primary/tag and
dependent implementation remain NO-GO. The incident record contains exact final
scope and the retained UTF-8 diagnostic-reader repair/failure evidence.
