# Reporting local-form and source retrieval

Development checkpoint, 2026-09-22. Branch `codex/finance-reporting-source-retrieval`
starts at v0.7.128 (`90957df0a330599c1b3ff649bfd8521c2b9cb010`).

## Scope

The local-form register silently stopped at 100 rows. Report detail displayed an
explicit 100-source preview but provided no navigation to later sources. Both now
use 50-row pages with complete counts, ranges and retained query parameters.
Local-form ordering has a stable primary-key tie breaker; report sources retain
their existing immutable ordering. Changing form filters resets the page.

Existing department/report visibility and source-page permissions remain in place.
Paging does not change generated output bytes, checksums, approvals or financial
sources. Register exports continue to include all matching rows. No schema,
posting, acceptance or persistence contract changes.

## Validation

PASS: focused SQLite tests, 2/2, no skips, 5.065s, exit 0. Synthetic fixtures
include 111 independently posted journal sources and 111 draft local forms.
Tests cover all three pages, source access, department isolation, malformed and
empty requests, full matching CSV export and unchanged report bytes/checksums.

Command (documented Python 3.11 environment):
`python .tmp/earlier_sqlite.py reporting.test_finance_reporting.FinanceAccountabilityReportingTests.test_source_drillthrough_retrieves_all_posted_journals_without_changing_output reporting.test_local_form_acceptance.FinanceLocalFormAcceptanceTests.test_local_form_register_retrieves_all_candidates_and_exports_all_matches`
Log: `.tmp/reporting-source-focused.log` (local, ignored).

Full Reporting regression PASS: 150 passed, 1 skipped (151 discovered),
50.619s, exit 0. Both test stores destroyed and runner terminal. Command `python .tmp/earlier_sqlite.py reporting`.
Log: `.tmp/reporting-source-regression.log` (local, ignored).

NOT RUN - OUT OF SCOPE: native MySQL for this read-only view/template change;
no schema, financial write, locking or conditional identity changes.
NOT RUN: interactive browser/physical print acceptance for this checkpoint.
Django response checks establish rendered navigation and actual source retrieval,
not visual or LGU acceptance. No eGAPS access, production migration or deployment.

## Pause and remaining work

User requested implementation pause after the current checkpoint. Resume only on
request. Office rarely uses eGAPS reporting because it is not user-friendly;
this does not establish that reporting is unnecessary or approve every eGAPS form.
Required outputs remain grounded in actual Budget–Accounting–Treasury work.
Earmark reservation basis remains unconfirmed. Next work includes browser proof
for these pages, ordinary printing/custody and exact-output qualification.
The full Finance Completion Gate remains incomplete and production remains NO-GO.
