# Finance release and Actions incident

Engineering incident remains OPEN. Release and production **NO-GO** until the
relevant application regressions and both resulting remote jobs actually pass.
Finance functionality/office acceptance remain separate required gates. See
[handoff](../CONTINUE.md), [foundation gap register](FINANCE_FOUNDATION_GATE.md)
and [candidate validation](FINANCE_V154_RELEASE_VALIDATION.md).

## Original remote evidence

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
