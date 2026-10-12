# Finance v0.7.154 checkpoint validation

Release candidate, 2026-10-12. The user requested the next vm-commitable checkpoint,
actual Version Manager commit/master integration/push. Latest steering prioritizes
the [Actions incident](FINANCE_CI_INCIDENT_2026-10-12.md) and then resumes the Finance
goal after both remote jobs pass. This record does not establish Finance completion
or production acceptance. Candidate publication is GO: full SQLite and focused
repair checks pass, and all 280 ordered native follow-up cases pass without skips.
The original full native FAIL remains retained; five test fixtures changed behavior
afterward, with a separate byte-exact EOF cleanup that preserves the AST, with all other 1,126 byte hashes unchanged. Primary integration and
dependent implementation remain NO-GO until both complete resulting remote jobs pass.
See [handoff](../CONTINUE.md), [foundation gate](FINANCE_FOUNDATION_GATE.md),
[source contract](FINANCE_FORM1_SOURCE_CONTRACT.md) and
[whole-package review/delivery](FINANCE_FORM1_PACKAGE_REVIEW_DESIGN.md).

## Intended scope and controls

The current Budget attribution work depends on 47 Finance development commits
beyond origin/master v0.7.109. Integrate that intended dependency chain together;
preserve the canonical operator checkout and unrelated files. Current changes
retain governed Budget actual/source attribution, joint cash/actual certification,
historical schedules, receipt forecasting, source/account/SPA/stock/PhilHealth
composition, immutable whole-package internal review and complete draft delivery.
The bounded final checkpoint adds office-indexed whole-draft history/detail with
original source permission checks, truthful counts and complete financial columns.
The index is never authorization. Unknowns, financial history, independent actors,
separate stores, currentness/issuance distinctions and export grants remain intact.

Migration 0022 preflights original root checksums and office identities before
native DDL, then rechecks before candidate-index backfill. It does not rewrite
history. Full original arithmetic and access are checked on retrieval. No operator
database migration, role provisioning or financial posting is part of this release.

## Validation state

During the completed full regressions, file-time inspection found no application,
test, template, requirements or workflow file modified after the native worker
started. A read-only SHA-256 snapshot of 1,132 source files is retained at
`.tmp/final-release-source-fingerprint.json`. All source hashes remained unchanged
through both terminal outcomes. The subsequent certification concurrency fixture
repair initially changed only `accounting/test_budget_actuals_certifications.py`.
The confirmed leaked-factory lifecycle repair additionally changes the four
manual Form 1 factory owners. All other 1,126 original byte hashes remain
unchanged; `.tmp/cleanup-repair-source-fingerprint.json` records the new producer
separately. Preserve the original snapshot and compare these exact exceptions.
The original
`--check` must now reject the changed fixture rather than misrepresent old native
FAIL as a current pass. The router, base/production settings
and Dockerfile have no diff from origin/master: separate environment-driven
stores, Django 5.2.17 and Python 3.11 remain in place.

Before recording full-suite PASS, run
`python .tmp/verify_final_release_coverage.py --require-terminal` and collect both
worker exit codes. The read-only checker compares logged IDs against the retained
2,462-ID discovery, rejects unexpected/duplicate/missing IDs, requires the exact
terminal count and an OK summary, and rejects failure/error headers. Both completed
logs contain every discovered ID exactly once. Native's terminal FAILED summary
correctly fails this strict gate. SQLite terminal coverage verification passed:
all 2,462 IDs exactly once, no missing/unexpected/duplicate IDs, terminal OK and
worker exit 0. All 195 skip reasons require native MySQL locks or read visibility.
Report the actual skipped cases separately; discovery
and an in-progress ID match are not a passing execution.

| Check | Actual outcome |
| --- | --- |
| Focused 105-version register, SQLite | PASS: one case, 642.272s, both test stores destroyed; before final denial-cache refinement |
| Focused 105-version register, native MySQL 8.4.11 | PASS: one case, 684.450s, both test stores destroyed; before final denial-cache refinement |
| Latest full fresh-store SQLite regression | PASS: 2,462 tests in 7,284.909s, 195 existing native-only skips, exit 0; all test IDs and unchanged source hashes verified; `.tmp/foundation-release-final-full-sqlite.log`, handle 9656 |
| Latest full fresh-store native regression | FAIL: 2,462 tests in 9,500.128s, one failure/four errors, exit 1; all discovered IDs exactly once, both stores destroyed; `.tmp/foundation-release-final-full-native.log`, handle 64111 |
| Five-case fresh native reproduction | FAIL: five tests in 22.762s, one failure/one error, exit 1; both candidate certification fixture defects reproduce, all three officer-return cases PASS in isolation; `.tmp/native-release-five-failure-repro.log`, handle 97370 |
| Certification fixture repair and officer-return diagnostic | PASS: 138 affected native cases in 184.661s, no skips, exit 0; complete discovery before selecting affected modules; `.tmp/native-release-fixture-and-return-discovery.log`, handle 40242; officer-return interaction was subsequently reproduced and classified in the ordered diagnostic below |
| All non-atomic/simple native diagnostic | FAIL: 280 tests in 1,259.379s, three errors, exit 1; all three officer-return errors reproduced with leaked clock/source evidence; `.tmp/native-release-all-non-atomic-diagnostic.log`, handle 53639; both stores destroyed |
| Cleanup repair focused native | PASS: 24 tests in 435.131s, no skips, exit 0, both stores destroyed; both repaired clock providers before unchanged officer consumers, certification races and manual cash factories; `.tmp/native-release-cleanup-focused.log`, handle 40526 |
| Cleanup repair broad ordered native | PASS: all 280 non-atomic/simple cases in 1,279.465s, no skips, exit 0, both stores destroyed; complete discovery order, no application instrumentation; `.tmp/native-release-cleanup-broad-ordered.log`, handle 77434; all selected IDs exactly once, all five former failures pass |
| Cleanup repair focused SQLite | PASS: 31 tests in 21.143s, seven existing native-only skips, exit 0, both stores destroyed; manual cash factories and dependent planning/adoption; `.tmp/sqlite-release-cleanup-focused.log`, handle 84602 |
| Accounting fixture repair | PASS: focused five cases (12.540s), affected 147 cases (88.680s), seven native-only SQLite skips; all 2,462 unique suite IDs preserved |
| Calendar scenario repair | PASS: focused six SQLite cases (27.592s); subsequent cash-expiry assertion passed in broader voucher/full runs |
| Broad voucher and final settlement repair | Broad 796-case SQLite FAIL (two date failures, 97 existing native-only skips; cash-expiry assertion PASS); final affected settlement/fee modules PASS: 43 cases, 31.107s, no skips |
| System check / migration drift | PASS: final isolated patched-environment check has no issues; `makemigrations --check --dry-run` reports no changes; `.tmp/foundation-release-final-system-checks.log`, exit 0 |
| Dependency consistency | PASS: `python -m pip check` with patched dependency target first on PYTHONPATH, no broken requirements; shared environment preserved |
| Updated pinned dependency audit | PASS: `python -m pip_audit -r requirements.txt`, no known vulnerabilities, exit 0 |
| Exact dirty scope / syntax / JSON sensitive-key check | PASS: 400 intended files, including the updated gap register and artifact-byte Git attribute; 228 Python files parsed, 91 synthetic artifacts and seven new JSON files checked for sensitive keys; no operator/private databases or temporary files in the candidate scope; this is scoped inspection, not a complete secret-scanner guarantee |
| Local documentation links | PASS: 601 local links across 22 unique documents, including the updated gap register; anchors not checked |
| Current whole-package browser/mobile | JSON native browser download PASS; authenticated PDF/ZIP HTTP bytes/hash/parser and all 11 PDF pages inspected; ZIP matches original JSON and all six original document hashes; native PDF/ZIP saving canceled (independent control PDF also fails with isolated official CLI 0.1.22); final desktop/mobile controls and three-office register/detail reads verified |
| Human office/forms/operational acceptance | NOT RUN; remains required; production NO-GO |

A read-only synthetic package profile completed without capture, export archival
or financial writes: `.tmp/profile_package_read.py`, exit 0, retained
`.tmp/whole-package-read-profile.log` / `.prof`. With profiler overhead and both
regressions running concurrently, one original `_read` took 16.201s and made
43,849,797 function calls; repeated pure source reproduction included 960 native
actuals verifications and extensive deep copies. This is diagnostic evidence for
the existing varied-source latency gap, not a representative response-time
benchmark or an established cause of the original CI failures. No timeout,
assertion, source check or producer was changed as a result of this probe.

Git `core.autocrlf=true` was confirmed. `.gitattributes` now disables text
normalization for captured `output/**` artifacts, preserving recorded JSON/PDF/ZIP
bytes across Windows checkouts. Explicit binary rules for captured PDFs/ZIPs
override the installed PDF text-diff handler; PDF syntax whitespace is retained
as original evidence, not rewritten to satisfy a source whitespace check.
Captured JSON whitespace uses `cr-at-eol` to recognize its original CRLF bytes
without normalizing them. The staged check also found one extra EOF newline in
`accounting/test_budget_receipt_sources.py`; exactly that final byte was removed,
with original bytes retained privately and the Python AST proven identical.
This formatting-only exception does not change any test, assertion or application
behavior and does not warrant rerunning unchanged application suites.
All 19 current captured JSON files have identical
filtered/raw Git blob hashes; no historical tracked output file became modified
and pre-release staging is limited to the inspected intended scope. Verify the published checkout's retained
artifact hashes after integration; this does not change application output bytes.

Full runs cover affected and dependent package, review, export, print, assembly,
native concurrency and wider release regressions. A skipped native-only test in
SQLite is not a native pass. Command roots use the documented Python 3.11 runtime:
`python .tmp/my_work_sqlite.py --verbosity 2` and
`python .tmp/retrieval_native.py --verbosity 2`.
Release dependency imports are isolated under
`C:/xxx/_INSTALLS/_HERE/_xxx/grand-release-20261012-dependencies`; probes verified
the intended versions and actual module locations. The shared project virtual
environment was preserved. The original full-suite handles 1191/21898 were
deliberately stopped after dependency audit required the patched environment;
they are not passes. Only their verified workers/disposable native test schemas
were stopped/cleaned before restarting. The owned MySQL server remains live until
the final native runner reaches terminal cleanup.

## Dependency release gate

The first audit failed with 25 advisories in unchanged baseline pins: PyJWT 2.13.0,
pypdf 6.16.1 and urllib3 2.7.0. `git diff origin/master -- requirements.txt`
was empty before remediation, confirming a pre-existing release dependency gap.
The release now pins PyJWT 2.15.1, pypdf 6.19.0 and urllib3 2.8.0. Reviewed primary
release notes cover [PyJWT validation changes](https://pyjwt.readthedocs.io/en/stable/changelog.html),
[pypdf parser hardening](https://pypdf.readthedocs.io/en/latest/meta/CHANGELOG.html)
and [urllib3 TLS/streaming fixes](https://urllib3.readthedocs.io/en/stable/changelog.html).
This is required release remediation, not a waiver or a claim that every external
network/proxy configuration has been accepted. Full project tests exercise the
application with these pins; deployed environments still need their normal checks.

## Resolved validation defects and remaining boundaries

Initial copied-history fixtures omitted retained attachments, attempted unbounded
large native bulk inserts and assumed native bulk-created models received PKs.
Those runs failed; bounded inserts, fetched persisted identities and complete
attachment copies fix the fixtures. Retained logs and outcomes remain in the
handoff. Superseded workers deliberately stopped after producer changes are not
passing assertion runs. Operator data hashes remained unchanged.

The browser exposed compressed mobile financial headings. The final table uses a
readable minimum width inside its existing horizontal scroll container and keeps
amounts together. Fresh desktop and mobile verification passed for Budget,
Accounting and Treasury readers; the binary browser-save limitation remains
separate from authenticated response validation. Financial arithmetic and
authority are unchanged.

Whole-package intake/review actions, representative varied-source history latency,
statutory signing/Chief Executive approval/issuance, official LGU form acceptance
and the remaining foundation/Finance gates remain open. Synthetic screenshots and
draft downloads do not establish those gates. eGAPS remains untouched.

## Release workflow

Installed Version Manager README/core and the repository's historical-preservation
adapter approach were inspected. The repository adapter now invokes the installed
`version_manager.py` entry point with a process-local plan adjustment preserving
historical evidence. Dry-run PASS: v0.7.154 and managed VERSION/CHANGELOG updates
only. Explicitly stage intended reviewed files after actual validation; use that
entry point for the real commit/tag and publish the intended candidate branch.
Dispatch `security.yml` on that branch (a development push alone does not trigger
it), check the released SHA and require both verify/mysql jobs to pass before
master integration. Integrate in the clean isolated checkout, push primary/tag
and verify the remote identities and the resulting primary run. The user's latest
instruction requires both actual CI jobs to pass, then continuation of the
existing Finance goal. This record does not claim a resulting remote CI pass or
completed primary integration; record the actual SHA/run results in the handoff.
Preserve historical PR 114's existing baseline. Master currently has no returned
branch protection/rulesets; CI/review evidence must still be assessed honestly.
Pre-release remote inspection on October 13 reports master `c5bd920a`; neither the
candidate branch nor `v0.7.154` existed remotely, the local tag was absent and the
staging index was empty. Refresh these checks immediately before release; this
observation does not reserve a tag or publish the candidate.
