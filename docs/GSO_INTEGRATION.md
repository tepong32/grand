# GSO integration into GRAND

## Authorized scope and base

2026-10-17: user requests reviewed GSO checkpoint, trial integration based on
GRAND v0.7.173, combined tests/review, actual VM release/master integration, then
pause with bullet reporting. Future development uses parallel branches of GRAND.
No deployment, operator migration, prototype account import or grant change.

Base: a53348207b924ef995adf2533642c0ae54ffaa6c (latest paused Finance work).
GSO source: a76a351f106b25828f1573d1641b2217e12cf13d (reviewed VM checkpoint).
Source native147/147 PASS, zero skips,64.560s; source featureCI38996343497 PASS.
Source primary CI38996500321 PASS. Trial local review/test gate is complete; VM candidate publication follows.

## Transfer and review

181 tracked product files copied with hashes; all inventory migrations through0029
and adapter migrations through0007 retained. See gso/SOURCE_MANIFEST.json.
Native GSO test modules renamed test_grand_* and relative imports adapted for
GRAND full discovery:147 source cases retained.43 standalone-shell test files
remain in GSOv2 history, not silently claimed as destination coverage.
No source user/home/src shell, runtime files, databases, passwords or uploads copied.

Actual settings install inventory/inventory_finance; both route to default.
Native auth/session/profile/department authorities remain. Routes /gso/inventory/
and /gso/claim-support/ use their existing namespaces. Native dashboard links use
same explicit read helpers as views; UAT read access never supplies mutations.
GSO header links back to GRAND home. No business service/schema redesign.

Protected root is explicit in production; startup and system checks reject relative
or public media/static locations. Native test runner uses isolated private storage.
Private downloads retain existing grants/scope and evidence checks. Add protected
uploads to approved file backup/restore: database capture alone is insufficient.
See DATABASE_BACKUP.md and gso/security-and-recovery.md. No production acceptance.

Existing v173 CI38976836601 passed security/mysql. SQLite shards2/4/6 exceeded
the20-minute ceiling and were cancelled; verify correctly failed. Set SQLite
budget45minutes while preserving complete discovery, whole classes, coverage
aggregation and zero-skip native requirement. Do not infer a code pass from timeout.
GitHub annotation117228201051 explicitly confirms the20-minute timeout.
Adding GSO changes sorted shard allocation; full combined coverage is required.
Final discovery:2724 distinct cases, including152 GSO (147 transferred plus5
destination cases), partitioned exactly once across all8 whole-class shards.

## Validation chronology

- PASS: destination Django system check; no issues.
- FAIL - CAUSED BY CURRENT WORK: initial test rename left relative module imports
  unchanged; corrected all module references before execution. Full discovery then
  found2719 cases, including all147 GSO cases, no import errors; all8 partitions
  satisfied existing runner constraints. Five destination tests subsequently added.
- NOT RUN - ENVIRONMENTAL: first native invocation refused absent MySQL timezone
  tables before creating test schemas. Loaded the retained official2026c archive
  (verified MD5 per Finance native-testing record) into the verified disposable
  server only and restarted. No application time-zone change.
- FAIL - CAUSED BY CURRENT WORK: first combined native185-test run had35 errors,
  all the new home link using obsolete home_redirect. Corrected template and new
  test to actual department_dashboard. Both schemas cleaned up; rerun required.
- PASS: production-storage/startup3 tests (including missing/private/public paths),
  migration drift (no changes), CI coverage unit9 tests, pip consistency and
  requirements vulnerability audit (no known vulnerabilities).
- PASS: synthetic browser native login -> office dashboard -> property register ->
  PAR placeholder POST/print -> native home. Mobile390px has no document overflow;
  inspected mobile/print screenshots under output/playwright/gso-integration/.
  Preview/browser stopped. Initial preview logo404 fixed by copying existing
  public defaults into isolated media; favicon404 is existing noncritical behavior.
- NOT RUN - ENVIRONMENTAL: container build; local Docker engine unavailable.
  Production settings boot tested separately; no container build pass claimed.
- PASS: scripts/run_mysql_tests.py gso_integration_tests
  departments.test_dashboard_presets home.tests_backup --verbosity1;
  disposable loopback33317, final log .tmp/gso-combined-native-final.log.186/186, zero skips,66.331s, exit0.
  Both schemas destroyed and owned MySQL33317 stopped normally.
- Pending: VM candidate release, exact combined hosted security/verify/mysql,
  primary integration/ref/CI verification and final publication handoff.
  No separate human/independent review, production deployment or Docker build pass claimed.

Finance functional completion, confirmed municipal forms/semantics, physical
signatures, production deployment and operational/LGU acceptance remain NO-GO.

Review:179 transferred product files match source bytes; only apps.py (storage
validation) and base template (native navigation/title) differ, plus checks.py.
Container/env example configure protected runtime directory, excluded from image
build context and Git. Original Finance source files remain unchanged.
