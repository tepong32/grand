# Joint actuals reconstruction repair - candidate validation

Status, October 13: **GO for bounded runtime diagnosis; NO-GO for primary integration,
dependent Finance implementation and production.** The installed Version Manager
executed v0.7.155 / `e6e1cb8e1a65121dcd392271a23f9cf618da3d23`, exactly twelve
reviewed repair/metadata paths. Clean HEAD, parent, local tag and exact source
proof passed; the development push was verified. Master and remote tag remain
unpublished. Guarded dispatch created [candidate run 38311451830](https://github.com/tepong32/grand/actions/runs/38311451830)
on that exact SHA; verify completed CANCELLED at the unchanged 20-minute limit;
mysql also completed CANCELLED at its unchanged 60-minute limit. No remote pass is
claimed. These post-publication documentation updates are
later than the released candidate; its original evidence remains retained.
See [handoff](../CONTINUE.md), [CI incident](FINANCE_CI_INCIDENT_2026-10-12.md),
[gap register](FINANCE_GAP_REGISTER.md#fin-gap-038---security-and-native-regression-release-gate)
and the retained [v0.7.154 evidence](FINANCE_V154_RELEASE_VALIDATION.md).

## Problem and bounded change

The v0.7.154 verify job exceeded its existing 20-minute limit. Audit, system and
migration checks passed; its project tests have no passing terminal result.
Repeated pure joint-actuals reconstruction is a measured application bottleneck;
the full timeout cause is not yet established. MySQL also completed CANCELLED at
its existing 60-minute limit; actual job metadata, all annotations and complete
logs are retained in the incident record. Its service started successfully but
the interrupted suite has no terminal summary. Neither job is a pass.

`accounting/budget_actuals_certifications.py` verifies the original preparation
and its trial balance once per snapshot operation instead of repeating them for
each officer and revalidating the same decision list twice. Each separate officer
observation still passes complete native-actuals/trial reproduction through
`trial_balance.project`, which calls `actuals.verify`. Exact role, office, actor,
source cohort, chronology, retained checksums, closure and complete snapshot
equality remain enforced. Public `verify_decision` verifies its own original;
the helper is private and operation-local. Mutation locks, original-source access,
currentness, financial amounts, posting, separate database routing, history and
storage schemas are unchanged. No workflow timeout, security check or test was
relaxed. There is no global cache or public verification-bypass option.

`.github/workflows/security.yml` appends `--verbosity 2` to the two full test
commands so future logs identify exact active tests. Those are the only changed
workflow bytes; every job, timeout, assertion, security step, test selection,
service configuration and separate-store runner remains. Local full suites were
already launched with verbosity 2; their application/test source did not change.

`accounting/test_budget_actuals_certifications.py` adds meaningful corruption and
cohort regressions: each officer's rehashed forged observation is rejected, and
a valid but later posted cohort cannot replace the original certified cohort.
Fresh discovery retains all 2,462 original IDs and adds four IDs, including the
two inherited cases; the full suite now contains 2,466 unique IDs.

## Actual evidence

- FAIL - remaining CI runtime; exact-SHA run 38311451830:
  verify job `115017911166` completed CANCELLED; its actual annotation says
  20m0s. Complete log has 797 distinct named test headers and no terminal suite
  summary, last named case in whole-package export. Log is retained under
  `.tmp/actions-release-20261012/completed-jobs/38311451830-attempt1-verify-115017911166.log`,
  2,101,766 bytes, SHA-256
  `3a61ffcb1562302284de8f4c8d69be9e6389e937fac3e7d947ee37b2b5a0ba67`,
  with matching metadata and all five annotations. The two denied historical
  document-export annotations belong to completed passing negative-permission
  cases; they are not assertion failures. MySQL's terminal result is recorded below.
  Authenticated job metadata confirms verify dependency
  installation/consistency, audit, Django checks and migration drift PASS;
  MySQL container initialization and dependency installation PASS. Its complete
  job log is now retained, with no terminal test summary. These individual step
  results do not establish either job's pass or incident resolution.
  MySQL job `115017911366` completed CANCELLED at 22:34:36 UTC on October 12;
  actual annotation 1h0m0s. Complete log has 809 distinct original test headers,
  ending in `Form1PackageTests.test_three_office_sources_permissions_export_only_and_uat_mutation_denial`,
  with no terminal summary or method-failure marker. Its service/dependency steps
  passed. Log:
  `.tmp/actions-release-20261012/completed-jobs/38311451830-attempt1-mysql-115017911366.log`,
  2,234,354 bytes, SHA-256
  `e193b85977e95c172e4d7b8c7bfc4417a71cbadb2ea0c2eec80994f26bb01622`.
  All seven annotations are retained. Four denied-access annotations map to completed
  passing package history/export and cash-source permission cases; the other three
  are timeout, cancellation and runner notice. Native partial header intervals include
  340.901s package history, 224.231s account history, 170.457s whole print and
  125.981s package retention; these include setup/body/cleanup, not method benchmarks.
  Private parser initially decoded a UTF-8 annotation with Windows' default encoding;
  explicit UTF-8 fixed its matching. Failed parser evidence and original bytes remain.
  Partial header intervals include setup/body/cleanup: account-register case
  162.400s, first whole-export case 82.231s, three assembly cases 41.628–53.118s.
  These are diagnostic intervals, not method timings or operational benchmarks;
  private evidence `.tmp/ci-runtime-v155-verify-header-intervals.log`.
  The scoped optimization was insufficient for CI. A genuine fresh-store export
  case profile completed PASS as handle 89995, exit 0: one test / 191.746s under
  cProfile, 1,840 joint snapshot reconstructions. Log/profile:
  `.tmp/ci-runtime-package-export-case.log` and `.prof`. The subsequent bounded
  repair is recorded separately in [v156 work](FINANCE_V156_RUNTIME_VALIDATION.md);
  its changes and proof are not this released v155 producer. No further release,
  timeout change or complete remote new-producer pass is claimed here.
- PASS - focused fresh SQLite:
  `python .tmp/my_work_sqlite.py accounting.test_budget_actuals_certifications.NativeActualsCertificationTests --verbosity 2`;
  49 tests in 19.381s, no skips, both stores destroyed. Private log:
  `.tmp/ci-runtime-certification-focused-sqlite-corrected.log`. The first attempt
  named a nonexistent class and executed no source tests; its failure is retained.
- PASS - same-package profiling and exact retained evidence:
  `.tmp/profile_ci_package_before.py` and `.tmp/profile_ci_package_after.py`.
  Fresh-actor reads changed from 5.313/5.379s to 2.420/2.440s. Profiled calls
  changed from 43,828,078 to 20,937,138 (13.764s to 6.591s); native actuals
  verification calls fell from 960 to 320. The original complete joint snapshot,
  package checksum and both synthetic store byte hashes remained exact. Private
  logs/profiles: `.tmp/ci-runtime-package-read-before.*` and `after.*`. These are
  controlled synthetic measurements, not operational latency acceptance or full
  CI proof; the two profiled reads' timings are not directly compared with CI.
- PASS - Django system check and migration drift on guarded synthetic settings:
  `.tmp/check_ci_runtime_system.py`; no issues or changes detected, both store
  hashes unchanged. Private log `.tmp/ci-runtime-system-checks.log`.
- PASS - syntax, intended dirty-scope containment and dependency import checks;
  `.tmp/release_static_audit.py`. Patched PyJWT 2.15.1, pypdf 6.19.0 and urllib3
  2.8.0 resolve from the isolated release dependencies. Requirements, Python 3.11
  and Django 5.2.17 are unchanged by this repair.
- PASS - fresh dependency consistency and security audit:
  `python .tmp/check_ci_runtime_dependencies.py check` and `audit`, each exit 0.
  Exact runtime/import/metadata assertions passed; pip reports no broken
  requirements and audit reports no known vulnerabilities. Private logs:
  `.tmp/ci-runtime-pip-check.log` and `.tmp/ci-runtime-security-audit.log`.
  This does not establish default-branch alert closure or replace remote audit.
- PASS - separate Telegram CI step:
  `python .tmp/my_work_sqlite.py telegram_bot --verbosity 2`; five tests in
  0.703s, no skips, unused default/Finance stores not set up. Private log:
  `.tmp/ci-runtime-telegram-tests.log`.
- PASS - full fresh SQLite:
  `python .tmp/my_work_sqlite.py --verbosity 2`, handle 33886, exit 0;
  2,466 tests in 3,983.312s, the same 195 native-only skip IDs/reasons.
  Every discovered ID appears exactly once, terminal `OK (skipped=195)` and
  both test-store destructions are confirmed. Exact source/CI proof passed.
  Private logs: `.tmp/ci-runtime-full-sqlite.log` and
  `.tmp/ci-runtime-full-sqlite-id-proof.log`.
  The 105-version three-office register/paging/revocation/index/backfill case
  has emitted its passing result and the next case began. This is case-level
  evidence within this completed passing suite. Read-only log
  triage records an approximately 202s interval between its first fixture log
  and the next case's first log; it includes setup/cleanup and concurrent workload,
  so it is neither a measured method duration nor operational latency acceptance.
  Private triage: `.tmp/ci-runtime-live-start-intervals.log`.
- PASS - affected fresh MySQL, handle 33042, exit 0,
  `.tmp/ci-runtime-focused-native.log`:
  `python .tmp/retrieval_native.py accounting.test_budget_actuals_certifications accounting.test_budget_actuals_preparations budget.test_native_summary_reconciliation_concurrency budget.test_form1_package_concurrency budget.test_form1_package_review_concurrency --verbosity 2`.
  All 108 tests passed in 301.966s, no skips, both test stores destroyed. Covers
  original review/certification, both new regressions, dependent source and
  whole-package native races. Exact selected discovery (including five imported
  source cases) matches all logged IDs once; a prefix-only comparison omitted
  those imports and was replaced by actual Django discovery, not treated as proof.
  Private ID proof: `.tmp/ci-runtime-focused-native-id-proof.log`.
- PASS - full fresh MySQL:
  `python .tmp/retrieval_native.py --verbosity 2`, handle 9694, exit 0;
  2,466 tests in 5,723.615s, no skips. Every discovered ID appears exactly once,
  terminal `OK` and both test-store destructions are confirmed. Started only
  after the affected runner exited and both stores were destroyed. Private log:
  `.tmp/ci-runtime-full-native.log`. All five original full-native failure/error
  IDs pass in this complete run; original failed logs remain retained.
- PASS - complete candidate publication gate:
  `python .tmp/verify_ci_runtime_candidate_gate.py`; exact full/affected/scoped
  Telegram discovery IDs, original SQLite skip IDs/reasons, native zero skips,
  both store destructions and precise source/CI proof. Private log:
  `.tmp/ci-runtime-complete-candidate-gate.log`. The initial verifier assumed
  a Telegram namespace and root-suite membership that actual Django discovery
  does not use. The separate explicit CI label discovers five IDs from the
  actual `telegram_bot/tests.py`; root discovery does not recurse into that
  plain directory. Source-backed scoped discovery replaces those assumptions.
  Initial verifier failures remain retained; no application/test, assertion,
  coverage or passing log changed.

The repaired application/test producer has its own 1,132-source byte fingerprint under ignored
`.tmp/ci-runtime-complete-source-fingerprint.json`; only the reviewed service and
its test file differ from released v0.7.154. The later CI-only diagnostic suffixes
have exact before/after proof and a separate fingerprint; all 1,131 non-workflow
hashes remain unchanged. `.tmp/ci_runtime_source_gate.py --check-ci-observability`
checks this precise producer, preserving original fingerprints. Original v0.7.154
full-run and repair fingerprints remain untouched. Recheck hashes after each suite and before
release. No operator-store writes or production acceptance were performed.

## Remaining gate and next Finance milestone

Affected/full local regressions, installed Version Manager execution and repaired
development publication are complete. Both exact-SHA jobs from run 38311451830
were inspected and CANCELLED at their limits; do not repeat release/dispatch or
promote this failed candidate. Continue the separately fingerprinted
[subsequent repair](FINANCE_V156_RUNTIME_VALIDATION.md). Only its actual complete
local validation and resulting verify/mysql passes permit primary integration,
primary/tag publication and inspection of the resulting primary run. Record actual
commits, logs, tests and URLs when available.
Default master still contains the Critical dependency finding until the patched
candidate is integrated; neither the candidate audit nor this measurement closes it.

Then resume guided whole Form 1 preparation/intake/review using existing governed
services. LGU earmark semantics, local forms/printers, statutory named signatories,
Chief Executive decisions, physical custody and witnessed operational acceptance
remain deferred tonight and open. Finance completion and production remain NO-GO.
