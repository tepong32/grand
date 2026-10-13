# Treasury cash and remittance retrieval — 2026-09-22

Development branch `codex/finance-treasury-register-retrieval` begins at v0.7.139,
`cc152fada4ea0407fee03e8cdfe6cfeb308da331`, draft PR #100. Continues FG-11 and
the [foundation requirement audit](FINANCE_FOUNDATION_REQUIREMENT_AUDIT.md).

## Existing behavior and repair

Cash policies, work items, open instrument exceptions and ageing instruments each
stopped at 100 records. Work-item counts described all matches while the screen
offered no way to reach later ones. The remittance workspace likewise sliced its
already-scoped status/action result at 100.

Each register now uses stable 50-row pages with full matching counts and ranges.
Cash work, policies, exceptions and instruments have separate page parameters and
anchors. Moving one list preserves the other lists' pages and current action filter.
Submitting the filter form resets page selection. Remittances preserve existing
status/action semantics; action selection continues to take precedence over status.
The page helper accepts already-scoped querysets and reuses the existing voucher
pagination template. Remittance rows load their displayed preparer/variant together
with the batch, avoiding extra queries per row.

Cash policy availability still uses all applicable reservations, including instruments
on other pages. No amount, source, approval, release, exception, permission or
export service changed. Existing cross-office reviewer and UAT read boundaries
remain distinct from mutation authority. Cash export retains its full authorized
evidence scope; its button now says "Export cash evidence". It is not a current-page
or work-group-only export. Existing remittance batch exports are unchanged.

## Validation

Baseline — FAIL - PRE-EXISTING: two regression tests failed before application edits,
both observing 100 rows instead of a 50-row navigable page. 2.683s, exit 1, no errors.
Log `.tmp/treasury-register-baseline.log`.

PASS — SQLite, 30 tests, 20.058s, no skips, exit 0. Command:

```text
python .tmp/earlier_sqlite.py vouchers.test_cash_register vouchers.test_remittance_register vouchers.tests.VoucherWorkflowTests.test_f83_cash_enforcement_reservation_ageing_and_portable_export vouchers.tests.VoucherWorkflowTests.test_remittance_batch_versions_allocations_and_completes_only_after_posting vouchers.tests.VoucherWorkflowTests.test_remittance_review_rejects_foreign_office_and_uat vouchers.tests.VoucherWorkflowTests.test_remittance_uat_cannot_change_allocations_submit_or_release
```

PASS — native MySQL 8.4.11, 26 tests, 15.605s, no skips, exit 0. Command:
`python .tmp/retrieval_native.py vouchers.test_cash_register vouchers.test_remittance_register`.
The wrapper invokes the committed [fresh two-store runner](FINANCE_NATIVE_TESTING.md)
with private disposable credentials. Logs `.tmp/treasury-register-sqlite.log` and
`.tmp/treasury-register-native.log`; both fresh test stores destroyed, native server stopped.

New tests traverse 109 policies, 107 policy work items and the last of 107 position
work items; 105 instruments and 105 open exceptions; and all 111 matching remittances.
Identity-set assertions detect duplicates and omissions. They verify foreign-office,
draft/cancelled and resolved exclusions, retained action/status filters, independent
cash page parameters, reviewer visibility and unchanged cash events/reservations.
All 105 reserved amounts (210.00) still affect availability on every instrument page.
Existing tests cover UAT mutation denial, maker/checker, work-task counts and scopes;
dependent workflow tests cover actual cash enforcement/export and remittance release
through independent posting. Directly seeded volume rows are projection fixtures,
not actual approved transactions.

PASS — Playwright CLI at 1440×1000 and 390×844 on disposable copied synthetic stores.
Cash final pages show 101–107 of 107 work items and 101–109 of 109 policies. Work-list
Previous changes only `work_page`, retaining `policy_page=3` and the action filter.
Remittance final page shows 101–111 of 111; Previous preserves preparation scope.
Tables retain horizontal scrolling at narrow width; filter controls remain available.
Browser/session and fixture server stopped. Visually inspected evidence:

- [Cash desktop](../output/playwright/treasury-cash-page3-desktop.png)
- [Cash narrow view](../output/playwright/treasury-cash-page3-mobile.png)
- [Remittance desktop](../output/playwright/treasury-remittance-page3-desktop.png)
- [Remittance narrow view](../output/playwright/treasury-remittance-page3-mobile.png)
- [Remittance narrow navigation](../output/playwright/treasury-remittance-navigation-mobile.png)

PASS — diff whitespace and changed-document local links. Operator DB hash unchanged:
`C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C`.

NOT RUN - OUT OF SCOPE: full cross-module regression, new concurrency races, physical
printing and LGU acceptance. Read-only pagination does not change persistence or
financial locks; both register modules and directly dependent workflow tests are the
selected scope. Native register checks add backend evidence, not production acceptance.

## Remaining foundation work

No new Finance domain or statutory rule. FG-11 remains partial: shadow-cycle retrieval
and bounded history displays still need review/repair. Complete those before more
output breadth. Budget certified-actual coverage, local earmark semantics, exact
required forms and operational acceptance remain open. No master merge/deployment;
production NO-GO. eGAPS remains untouched and may stay closed.
