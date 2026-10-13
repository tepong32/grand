# Complete CI workload distribution - candidate validation

Status October 14: **IN PROGRESS; NO-GO for primary promotion and production.**
The v157 repair is based on v0.7.156 / `d666f3ab`. Full SQLite rehearsal passed;
all eight native shards passed all 2,468 tests without skips. Complete independent
local publication gate PASS; development candidate publication is GO, while
actual GitHub and primary acceptance remain unproven.
Dependent Finance implementation is held for the current bounded CI attempt;
if verify remains unaccepted, the latest user direction permits independently
validated Finance work while keeping the failed release gate explicit.
Inspect actual release refs and run evidence for publication state. Follow
[handoff](../CONTINUE.md), [incident](FINANCE_CI_INCIDENT_2026-10-12.md) and
[gap register](FINANCE_GAP_REGISTER.md#fin-gap-038---security-and-native-regression-release-gate).

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
Runtime remains HIGH/OPEN; old-master dependency findings remain CRITICAL/OPEN.

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

## Actual validation so far

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

Finance next milestone remains guided whole Form 1 preparation/intake and
independent review through existing governed services, after the CI gate.
Earmark semantics, named statutory/Chief Executive decisions, local output and
custody/human acceptance remain OPEN and deferred tonight. Passing engineering
checks cannot establish production or LGU acceptance.
