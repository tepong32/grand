# Complete CI workload distribution - candidate validation

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

Actual native workers 6/7 passed 354 tests / 684.491s and 325 / 704.581s,
respectively, both zero skips. Final complete raw-worker verification passes all
sixteen logs. Aggregate verify job 115423827781 and mysql job 115429096779 passed
every step, including original same-run coverage artifact download and complete
union verification. MySQL's 24,368-byte terminal log SHA-256 is
`8a423b46523572fc52c4e24448327f36e185e70e3979dbc3cf86be7df4562d45`;
verify's 24,482-byte hash is
`9ade4fe084e4fcfdb79062fe30e2323118b071ad85b4deef2522d318d36961f2`.
Security passed all 13 steps: no known vulnerabilities, six runner tests and five
Telegram tests. Evidence is retained in ignored
`.tmp/actions-release-20261012/completed-jobs` and the primary promotion receipt.

LOW maintenance: successful artifact v4 actions emit a Node runtime migration
warning; Ubuntu image migration notices are informational. Expected permission
denials in passing negative tests do not establish failed assertions. All
annotations and complete source contexts are retained; no assertion or permission
check was suppressed.

Primary completion: verify job 115437541048 and mysql job 115445856552 passed
every step and their complete 2,468-ID coverage gates. MySQL's 24,090-byte full
log hash is `dfad5c920854111aa066b8e9863930594e7dc1c6cdab89a44359d59ef7ea5633`;
verify's 24,205-byte hash is
`6f5b8170666d9bb022b0bd2ac6efe6bf8fc6ac1c0fc73aaf5a941a08fc717bc7`.
All sixteen full worker logs and twelve failure-level annotations were checked;
each annotation maps to a completed passing negative permission case. Exact
master/tag refs match `739e3657`. Acceptance receipt is retained under ignored
`.tmp/ci-v157-primary-acceptance.json`. Historical promotion receipt retains its
then-pending primary status rather than rewriting that earlier evidence.

The post-push authenticated Dependabot snapshot still returns 24 open alerts
(one Critical, 15 High, eight Medium). The exact released pins fall outside
every returned affected range, including Critical PyJWT GHSA-ffc3-869f-jxw9;
the actual security audit passes. Provider alert refresh is unresolved separately;
no alert was manually dismissed or downgraded. The accepted-primary snapshot still returns the same 24 alerts; exact pins
are outside all returned affected ranges. Preserve both snapshots. This provider
state remains OPEN separately from the now-resolved Actions incident.

## Evidence and bounded repair

The actual v156 verify job was cancelled at its unchanged 20-minute limit after
796 named test starts; this is not a passing count. MySQL subsequently completed
CANCELLED at its unchanged 60-minute limit, 14:59:30 UTC October 13: 1,108 named
starts, no terminal summary or unittest failure markers. Its complete log and
all nine annotations are retained; six permission annotations map to five
completed passing negative cases. Both old-candidate jobs remain unaccepted.
The complete local sequential v156 suites passed all 2,468 IDs (195 native-only
SQLite skips; native zero skips), but do not establish a remote pass. Test
discovery has grown from the original master incident's 1,193 IDs. Current
genuine export profiling passed one test in 96.329s under instrumentation,
versus the prior producer's 191.746s. Fresh migration setup is separate;
overlapping profile times are not added or described as ordinary latency.
Those historical runtime and dependency blockers were HIGH and CRITICAL,
respectively; the released v157 repair and complete primary validation resolve
the source/Actions findings as recorded above. Provider refresh remains separate.

The workflow candidate retains security audit, dependency consistency, system,
migration and explicit Telegram checks in `security`. Eight `sqlite` workers
and eight `native` workers each perform full discovery, selecting complete test
classes by sorted class identity modulo eight. Tests remain sequential within
each worker and retain Django's original relative order. There are no test
exclusions, new skips, weakened assertions, production settings or financial
service changes. Matrix concurrency is bounded at four per backend and sibling
failures do not cancel other diagnostic workers. Each native worker has its own
pinned MySQL service with separate default/Finance stores and the existing
strict/time-zone/fresh-store runner. Job limits remain 20/60 minutes.

The existing `verify` and `mysql` names are aggregate gates. They require every
worker (and security for verify) to succeed and verify immutable per-worker
JSON evidence: exact revision/discovery, every shard, completed test count,
complete union without duplicates, whole-class ownership and native zero skips.
Coverage records are written once after suite execution; failed/cancelled jobs
cannot satisfy the aggregate gate. The ordinary unsharded native command is
unchanged unless `--ci-shard` is explicitly selected.

Implementation: `.github/workflows/security.yml`, `scripts/run_mysql_tests.py`,
`scripts/ci_test_runner.py`, `scripts/verify_ci_coverage.py` and the explicit
`scripts/test_ci_test_runner.py` regression checks. The scripts directory is a
namespace package; these six runner checks run explicitly in security and do
not replace any original application test.

Primary references: [Django 5.2 custom runners](https://docs.djangoproject.com/en/5.2/topics/testing/advanced/),
[GitHub matrix jobs](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/run-job-variations)
and [coverage artifacts](https://github.com/actions/upload-artifact).

## Retained local and interim validation

The dated progress records below retain each producer's actual outcomes. Earlier
pending/NO-GO statements describe those earlier gates; current complete primary
acceptance is recorded above and must not overwrite failed historical evidence.

PASS: YAML parsing and structural comparison preserve the original security
steps, triggers, permissions, pinned MySQL service and limits, with mandatory
aggregate dependencies and no `continue-on-error`. Validation uses isolated
PyYAML 6.0.3 under `C:/xxx/_INSTALLS/_HERE/_xxx/grand-ci-workflow-validation`;
no shared virtual environment or application requirement changed. The latest
six-test rerun passed in 0.005s. Logs are retained under
`.tmp/ci-shards-v157-runner-checks.log` / `ci-shards-v157-workflow-check.log`.

- PASS: six explicit runner/coverage tests, 0.013s. Missing/duplicate/failed/
  incomplete/wrong-revision records, omitted/repeated/split classes, native
  skips and filtered/retained/parallel discovery are rejected. Actual Django
  command defaults are tested.
- PASS, discovery only: all 2,468 original application IDs retained exactly
  once, class-preserving counts 206/205/369/204/413/392/354/325. This is a plan
  check, never execution evidence. Frozen corrected producer has 1,136 source
  hashes: only workflow/native-runner changes and three new CI scripts versus
  the v156 producer; all application sources and tests remain unchanged.
- FAIL - CAUSED BY CURRENT WORK: the first new-runner rehearsal rejected
  Django's standard CLI `test*.py` discovery pattern before application tests
  ran. All failed logs/result records remain under `.tmp/ci-shards-full-*`;
  original 1,488-file preliminary fingerprint and plans remain retained. The
  guard now accepts the exact default pattern and rejects narrowed patterns;
  the actual-command regression covers the repair.
- IN PROGRESS: corrected complete local shard rehearsals under
  `.tmp/ci-shards-v157-full-sqlite` / `ci-shards-v157-full-native`. Launchers
  retain actual PIDs, commands, local source fingerprint identity, parent SHA,
  exits, full raw log hashes and completed coverage. Local SQLite concurrency
  is two with independent stores/artifacts; native is one because local test
  schema names share one disposable server. Both complete backends and actual
  aggregate verification remain required.
- First corrected SQLite shard (index 0) PASS: 206 tests / 224.221s,
  176 passed and 30 existing native-only skips, actual exit 0 and both stores
  destroyed. Completed coverage has all 206 selected/executed IDs. The private
  progress reader initially missed the first header joined to buffered migration
  stdout; it now recognizes that actual header without altering raw logs.
  This one-shard pass is not a complete backend or candidate pass.
- Corrected SQLite index 1 PASS: 205 tests / 327.746s, 173 passed and 32
  existing native-only skips, exit 0 and both stores destroyed. Native index 0
  PASS: all 206 tests / 428.834s, zero skips, exit 0 and both stores destroyed.
  Remaining shard runs are still live; no full-backend pass is claimed.
- Corrected SQLite indices 2/3 PASS: 369 tests / 777.457s / 13 existing
  native-only skips and 204 tests / 388.046s / 40 existing native-only skips,
  respectively. Both actual exits are 0 and both stores were destroyed.
  Independent publication-gate inspection verifies all four completed shards'
  exact actual headers, summaries, source identity, result/log hashes and cleanup;
  it correctly refuses publication while shard 4 has no completion record.
  Partial gate logs remain retained; this is an expected pending-data refusal,
  not an application-test failure or candidate GO. Remaining full local and
  actual remote checks remain required.
- Corrected native index 1 PASS: all 205 tests / 979.954s, zero skips, exit 0,
  both test stores destroyed, completed 15:05:13 UTC October 13. Raw log SHA-256
  `aaf05463071d9e8be538a22c5e9a4fbe3f3cba2fd6d757ef5dd568cd0bd12807`.
  Exact unique headers match all 205 planned IDs. Native index 2 has started;
  local native execution remains sequential and all remaining proof is required.
- Corrected SQLite indices 4/5 PASS: 413 tests / 759.467s / 20 existing
  native-only skips and 392 tests / 537.048s / 22 existing native-only skips,
  respectively. Actual exits 0 and both stores destroyed. The independent gate
  verifies exact headers, summaries, source/result/log evidence and cleanup
  for all six completed SQLite shards and correctly refuses missing shard 6.
  Indices 6/7 are now running; no full SQLite or candidate GO is claimed yet.
- Complete corrected SQLite rehearsal PASS: indices 6/7 subsequently passed
  354 tests / 570.508s / 30 existing native-only skips and 325 tests / 515.982s /
  eight existing native-only skips. Launcher 21064 completed exit 0, after the
  actual aggregate verifier passed complete 2,468-ID coverage across all eight
  successful shards and unchanged 1,136-source proof. Independent publication
  inspection verifies every actual unique log header, result/log hash, exact
  original skip identity/reason, terminal summary and both-store cleanup.
  Total: 2,273 passed / 195 unchanged native-only skips. That gate then verifies
  completed native indices 0/1 and correctly refuses unfinished native index 2.
  Retained `.tmp/ci-shards-v157-sqlite-complete-gate.log` is partial overall
  publication proof, not candidate GO. Only native launcher 26124 remains live;
  never repoll/restart completed SQLite 21064. No remote v157 pass or release yet.
- Corrected native index 2 PASS: all 369 tests / 747.520s, zero skips, actual
  exit 0, both stores destroyed, completed 15:20:41 UTC October 13. Raw log
  SHA-256 `5e654e5aab6886752ba0245bd6652bede904dd6f20b92a37085870d547038320`.
  Independent gate verifies every actual unique header and all completed native
  indices 0/1/2 after complete SQLite proof, then correctly refuses missing
  native index 3. This establishes 780 completed native tests, not full native
  or publication acceptance. Native launcher 26124 continues sequentially.
- Read-only release inspection PASS: exact 12 intended paths, expected
  `d666f3ab` parent/branch, empty index, absent v157 tag, installed-tool preview
  and unchanged producer hashes. No staging, commit or push occurred. Private
  `.tmp/execute_ci_shard_release.py` and the installed Version Manager adapter
  each require the complete local publication gate before actual execution;
  the expected actual scope is these 12 paths plus VERSION/CHANGELOG. Inspection
  evidence is `.tmp/ci-shards-v157-release-scope-inspection.log` and does not
  substitute for unfinished native or actual remote checks.
- Fresh preflight PASS: all six runner tests, YAML/control validation, Django
  system/migration checks with synthetic-store hashes unchanged, dependency
  consistency, security audit (no known vulnerabilities) and all five explicit
  Telegram tests. Actual per-command exit codes, commands, timestamps and raw
  hashes are retained under `.tmp/ci-shards-v157-preflight`. Preflight launcher
  13291 completed exit 0. The audit's Windows short-path/junction notice is
  retained; it is not an advisory. All 1,136 producer hashes still match.
- Corrected native index 3 PASS: all 204 tests / 557.104s, zero skips, actual
  exit 0, both stores destroyed, completed 15:32:34 UTC October 13. Raw log
  SHA-256 `74afad8557bc9d0edb25b4f01d197ec437ca72379ae02e054f0e7a4bf8763176`.
  Completed native coverage now totals 984 tests across indices 0/1/2/3.
  Exact identity comparison against all SQLite coverage records establishes
  that 115 of its 195 native-only skips executed in successful native shards.
  Remaining 80 await their actual native results; SQLite skips are never passes.
  Launcher 26124 is confirmed live; remaining native and remote checks are required.
- Corrected native index 4 PASS: all 413 tests / 616.114s, zero skips, actual
  exit 0, both stores destroyed, completed 15:45:23 UTC October 13. Raw log
  SHA-256 `b2ef9407e8b07afeae44c456a549ef67716034b94d785a999901613dc5dc1b60`.
  Independent gate verifies full SQLite and completed native indices 0–4,
  then correctly refuses unfinished index 5. Retained partial evidence is
  `.tmp/ci-shards-v157-five-native-gate.log`; no candidate GO is claimed.
  These 1,397 completed native tests include 135 of the original SQLite skips;
  remaining 60 await native completion. Native launcher 26124 continues.
- User-requested documentation refresh also updates README and the Finance
  roadmap with current development/acceptance boundaries and the bounded CI
  attempt direction. Fresh read-only release inspection PASS: exactly 14 intended
  paths, empty index and unchanged 1,136 source hashes; installed Version Manager
  adds VERSION/CHANGELOG for an expected 16-path release. Earlier 12/14-path scope
  inspection remains historical evidence. No staging, release or push occurred.
- Corrected native index 5 PASS: all 392 tests / 703.266s, zero skips, actual
  exit 0, both stores destroyed, completed 15:59:43 UTC October 13 (23:59:43
  October 13 local time). Raw log SHA-256
  `bf6bc48407ed0c8dc711afe6ceb1360bf6836ac4ca6694fd4a4192615696a44a`.
  Independent gate verifies full SQLite and completed native indices 0–5,
  then correctly refuses unfinished index 6. Retained partial evidence is
  `.tmp/ci-shards-v157-six-native-gate.log`. Native totals: 1,789 passed,
  including 157 original SQLite-skipped identities; remaining 38 await native
  completion. Exact original 195 identities, the 157 executed identities and
  the 38 pending identities are retained in
  `.tmp/ci-shards-v157-native-only-six-results.json`; it explicitly records
  `full_native_complete: false`. Launcher 26124 remains live; no candidate or
  remote pass yet.
- Corrected native index 6 PASS: all 354 tests / 743.888s, zero skips, actual
  exit 0, both stores destroyed, completed 16:15:00 UTC October 13 (00:15:00
  October 14 local time). Raw log SHA-256
  `4dd6769f1b476c34d51d594a2de32596d59a164be188d65ae01bcc98f3e303a5`.
  Independent gate verifies all SQLite and completed native indices 0–6,
  then correctly refuses unfinished index 7. Partial gate evidence is
  `.tmp/ci-shards-v157-seven-native-gate.log`. Exact identity evidence is
  `.tmp/ci-shards-v157-native-only-seven-results.json`: 187 original SQLite skips
  executed in successful native shards, eight pending, full native incomplete.
  Total: 2,143 native tests passed without skips. Launcher 26124 started the final
  native shard; full publication/remote acceptance remains pending.
- Operator preservation recheck, October 14 PASS: canonical checkout remains
  at `ce0c7243` with its existing dirty SQLite file, untracked policy test and
  nine historical output artifacts. Both database SHA-256 hashes exactly match
  the previously recorded operator baseline; no operator checkout/database
  mutation was performed. Release scope remains the isolated candidate only.
- Complete corrected native rehearsal PASS: index 7 passed all 325 tests /
  618.849s, zero skips, exit 0 and both stores destroyed, completed 16:28:51 UTC
  October 13 (00:28:51 October 14 local). Raw SHA-256
  `c6136a4c23b5b7bb3743109034fa4079296399fae3c9d995e9bd41ce2198aa3c`.
  Launcher 26124 completed exit 0 after aggregate exact 2,468-ID coverage and
  unchanged 1,136-source verification. Do not poll/restart that terminal handle.
  `.tmp/ci-shards-v157-native-only-complete-results.json` proves all original 195
  SQLite-skipped identities executed in successful native shards, none pending.
  Independent full gate `.tmp/ci-shards-v157-local-publication-gate.log` PASS:
  both backend coverage/actual logs/hashes/summaries/cleanup, unchanged original
  SQLite skip identities/reasons, six preflight checks and source integrity.
  GO for development candidate publication only; remote/primary NO-GO remains.
- NOT RUN at local acceptance: new candidate GitHub CI and resulting primary
  checks. Actual installed Version Manager/ref/remote evidence must be verified;
  local PASS does not establish incident resolution or production acceptance.

Release formatting follow-up: the first actual release guard stopped at staged
`git diff --check` (exit 2) for one extra EOF blank line in the new CI runner;
no Version Manager commit/tag was created. Removed only the final CRLF pair.
Original tested bytes/fingerprint remain retained; exact byte-difference and
identical Python AST checks prove no executable change. The other 1,135 sources
remain byte-identical. Six runner regression tests reran PASS / 0.005s.
Full application suites were not repeated for this formatting-only change;
their original complete evidence is preserved rather than relabelled as a rerun.
The source guard permits only this exact verified EOF difference, with no other
source exception. Guard-owned staging is recovered without changing working files.

Actual GitHub native worker 0 PASS: 206 tests / 302.162s, zero skips. Complete
828,708-byte raw log retained, SHA-256
`9b365f8ffa44e1d7d68bbb7623ca550dad1e0fe1307c81e5ddbc7163aec44126`.
Independent raw-log inspection confirms all 206 exact planned identities once,
passing terminal summary and both database teardowns. Its two annotations are
Node action maintenance and Ubuntu migration warnings/notices; no financial
or assertion failure. Remaining native workers and both aggregate gates pending.

Subsequent GitHub worker results PASS: SQLite 2, 369 tests / 578.945s / 13
expected native-only skips, raw SHA-256
`5de37fe9eeb6bc1244a1f4ee979833aed597829bc176d448928e7f1a408f1c37`;
native 1, 205 tests / 572.315s / zero skips, raw SHA-256
`d18ee86a492420d0041842a11ff1f38175c82fcfb808ee0b585127e805c82af7`.
Complete logs/metadata/annotations retained. Independent collected-log verifier
PASS for all six completed worker logs: exact planned IDs once, actual passing
summaries, original skip identities and both-store cleanup. This establishes
four SQLite workers / 984 tests and two native workers / 411 tests, not full
remote coverage or either aggregate gate. Source and required checks unchanged.

Further GitHub workers PASS: SQLite 4, 413 tests / 482.517s / 20 expected skips;
SQLite 5, 392 / 412.273s / 22 expected skips; native 2, 369 / 815.325s / zero
skips; native 3, 204 / 685.612s / zero skips. Complete raw logs/metadata/all
annotations retained. The collected-log verifier passes all ten completed workers:
exact planned identities once, expected skip identities, terminal summaries and
both-store cleanup. Totals: six SQLite workers / 1,789 tests; four native workers /
984 tests without skips. Remaining workers and both aggregate gates remain pending.

GitHub SQLite 6 PASS: 354 tests / 588.758s / 30 expected native-only skips,
raw SHA-256 `8001d9d05538068ff3b46448dd8083f94cd376e0641546a18f087eea3b9e3aa3`.
The collected-log verifier passes eleven completed workers. Current totals:
seven SQLite workers / 2,143 tests; four native workers / 984 tests without skips.
SQLite 7, native 4–7 and both aggregate gates remain pending.

Finance next milestone remains guided whole Form 1 preparation/intake and
independent review through existing governed services, after the CI gate.
Earmark semantics, named statutory/Chief Executive decisions, local output and
custody/human acceptance remain OPEN and deferred tonight. Passing engineering
checks cannot establish production or LGU acceptance.
