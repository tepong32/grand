# General-ledger retrieval checkpoint — 2026-09-22

Development branch `codex/finance-ledger-retrieval`, based on v0.7.138
`a03f82d16e18276d30ab7396b4e67b833a6e8990` and draft PR #99.
Continues FG-11 and the [full A–K audit](FINANCE_FOUNDATION_REQUIREMENT_AUDIT.md).

## Observed defect and repair

The ledger screen silently loaded only its first 1,000 posted lines, while the
CSV included the full department/account scope. Page navigation was absent.
An invalid or foreign account ID silently selected all department lines; a
superscript digit passed `isdigit()` and raised a conversion error.

The screen now has stable 50-line pages with full matching counts and preserved
account selection. Display and CSV share the same strict scope selector. Invalid,
foreign and oversized account values return HTTP 400 with a recovery instruction;
the screen displays no lines/export link, and export does not create an archive.
An empty selection still deliberately means all accounts in the user's department.

Running balances include previous pages. SQL aggregates preceding posted debits
and credits only for accounts present on the requested page. The boundary follows
the display/export order: entry date, entry ID, line sequence, line ID. Each page
loads at most 50 line objects; earlier lines are not materialized in Python.
Credit-normal signs are applied after accumulating debit-minus-credit values.
Same-date journals, earlier dates and reductions retain their exact contribution.

Existing journal permissions, department scope, posting services, immutable history,
archive format and full CSV scope are retained. No migration or financial write
was added. Like the existing register pagination, this is a current view rather
than a frozen cross-request snapshot; later independent postings can change counts.
No production-volume performance benchmark or broader fund/date/search filtering
is claimed by this account-scoped retrieval repair.

## Actual validation

Baseline — FAIL - PRE-EXISTING, reproduced before application edits. Two new tests
ran in 3.051s, exit 1: 12 failing assertions/subtests and two Unicode conversion
errors. The first page had 1,000 rather than 50 rows; invalid account exports
incorrectly succeeded and recorded export events. Log `.tmp/ledger-baseline.log`.

PASS — SQLite: all 57 `StandaloneAccountingTests`, 13.400s, no skips, exit 0.
Command: `python .tmp/earlier_sqlite.py accounting.tests.StandaloneAccountingTests`.
This includes the four new ledger tests, existing independent posting and archived
ledger/trial-balance exports, and dependent standalone Accounting view/service tests.
Log `.tmp/ledger-sqlite.log`; fresh default and Finance test stores destroyed.

PASS — native MySQL 8.4.11: six affected tests, 5.305s, no skips, exit 0.
Command: `python .tmp/retrieval_native.py` followed by each of these labels prefixed
with `accounting.tests.StandaloneAccountingTests.`:

- `test_ledger_retrieves_beyond_one_thousand_with_continuous_balances`
- `test_ledger_invalid_account_never_widens_view_or_export`
- `test_ledger_date_order_reductions_and_department_boundaries`
- `test_ledger_empty_selection_and_read_permission`
- `test_ledger_shows_posted_entries_only`
- `test_ledger_and_trial_balance_exports_are_trace_sync_ready`

The wrapper supplies private disposable credentials to the committed fresh-store
runner described in [native testing](FINANCE_NATIVE_TESTING.md). SQL aggregation
and pagination were exercised on native MySQL despite no persistence change.
Log `.tmp/ledger-native.log`; both test stores destroyed and owned server stopped.

Coverage includes 1,002 posted synthetic lines, final-page balances and full CSV
agreement, debit/credit-normal accounts, account-filtered page two, draft exclusion,
foreign department exclusion from opening balances, earlier/same/future date order,
reductions, empty results, invalid pages, invalid account input and read permission.
Synthetic projection fixtures do not claim independent approval of those rows;
existing workflow tests separately exercise actual submit/post operations.

PASS — Playwright CLI desktop 1440×1000 and narrow 390×844 against a disposable
two-store fixture. Final all-account page showed lines 1001–1002 and balances
1002.00. Previous navigation reached page 20. Selecting the actual cash account
reset pagination; its final page showed line 501 of 501, balance 1002.00, and
Previous preserved the account filter. Invalid account selection visibly failed
closed. The first rehearsal URL omitted `/finance/` and returned 404; corrected
route was used. An initially assumed account ID was invalid and correctly returned
400; the fixture's actual account was then selected through the form.

Retained, visually inspected screenshots:

- [Final ledger page, desktop](../output/playwright/ledger-page21-desktop.png)
- [Final account page, narrow width](../output/playwright/ledger-filtered-mobile.png)
- [Invalid account, narrow width](../output/playwright/ledger-invalid-account-mobile.png)

The narrow table retains horizontal scrolling; counts and navigation remain
reachable. Browser and disposable server stopped. Operator DB SHA256 stayed
`C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C`.
PASS — `git diff --check` and changed-document local link validation.

NOT RUN - OUT OF SCOPE: full cross-module regression, concurrency tests, production
and LGU acceptance. This read-only change does not modify locks or posting paths;
targeted native aggregation plus the complete standalone Accounting class are the
selected scope. A targeted pass does not establish the complete Finance gate.

## Next and remaining gaps

FG-11 stays PARTIALLY IMPLEMENTED: Treasury cash work, remittance batches and
Finance shadow cycles still have 100-record caps. Continue cash/remittance retrieval,
then history reachability. Budget actuals coverage, earmark semantics, required
forms and office acceptance remain explicit in the foundation gate. No master
merge/deployment; Finance production remains NO-GO. eGAPS remains untouched.
