# Partial payment, bank return and replacement output replay

October 14, 2026 development checkpoint. This extends the existing
[ordinary cross-office replay](FINANCE_CROSS_OFFICE_OUTPUT_REPLAY.md) and
[Treasury stage rehearsal](FINANCE_TREASURY_OUTPUT_REHEARSAL.md) with a named
Accounting/Treasury settlement scenario. It does not introduce a report family,
posting recipe, schema, permission or workflow change.

## Scenario and expected controls

Two independently posted original invoices of 1,500 each supply explicit claims.
The existing consolidated DV reserves 600 from the first and 400 from the second.
Two 500 cheques each retain allocations of 300 / 200. Both are released through
reviewed, acknowledged bank advice and independently posted payment requests.
One cheque is subsequently returned unpaid; independent Accounting review and
its exact posted payment reversal precede replacement and a fresh actual release.
The other cheque and both original invoice journals remain intact.

| Stage | Journal debit and credit movement totals, each | Original claims outstanding | Treasury historical issued / released totals, each |
| --- | ---: | --- | ---: |
| Both original partial payments posted | 4,000 | 900 / 1,100 | 1,000 |
| Exact reversal of one returned payment posted | 4,500 | 1,200 / 1,300 | 1,000 |
| Replacement released and posted | 5,000 | 900 / 1,100 | 1,500 |

Treasury totals describe actual historical instrument issue and physical-release
events. A replacement therefore increases those gross totals; it does not mean
1,500 of net invoice settlement. Accounting retains the original 3,000 expense
recognition, the exact 500 payment reversal and 1,000 final net settlement.
The original invoice shares and reservation evidence are reused unchanged.
Never erase the original release or count its replacement as another expense.

At every stage the test generates existing trial-balance, general-ledger and
payment-instrument report workbooks through the real report service. It compares
complete journal/instrument source identities and visible workbook totals, then
downloads retained bytes through each authorized office's HTTP route. The case
payment-register CSV is compared with the same instruments, SHA256 header and
archive manifest. All earlier workbooks and CSV archives remain byte-identical
after return and reissue.

## Validation and limits

Reproduction: `vouchers.test_consolidated_payables.ConsolidatedPayableTests.test_partial_return_reissue_outputs_preserve_gross_history_and_net_settlement`.
PASS: focused SQLite one case / 4.544s; native one case / 5.500s, zero skips.
PASS: final dependent scope, 23 exact cases on both backends: SQLite 30.263s;
native 42.722s, zero skips, exit 0 and both stores destroyed. This includes the
full consolidated/prior-payable classes, existing authoritative ordinary replay,
trial-balance controls and general-ledger source coverage. Final assertions also
verify net bank movement and exact status/release/receipt/replacement CSV evidence.

Actual commands use Python 3.11 with isolated settings:

```text
python -X utf8 .tmp/intake_primary_sqlite.py vouchers.test_consolidated_payables vouchers.test_prior_payables vouchers.tests.VoucherWorkflowTests.test_authoritative_budget_to_reconciled_treasury_report_replay reporting.test_finance_reporting.FinanceAccountabilityReportingTests.test_trial_balance_run_pins_reconciled_controls_and_source_drillthrough reporting.test_finance_reporting.FinanceAccountabilityReportingTests.test_posted_general_ledger_retains_line_level_controls_and_entry_sources --verbosity 2
python -X utf8 .tmp/intake_primary_native.py <the same labels> --verbosity 2
```

Logs and actual exit receipts are retained in `.tmp/partial-output-dependent-*`;
`.tmp/partial-local-acceptance.json` verifies identical exact IDs on both backends,
frozen test source and unchanged operator database hashes. Test-run wall times
including fresh migration/setup were approximately 2m11s SQLite and 3m27s native;
the suite durations above exclude those startup costs. `git diff --check` PASS.
Installed VM v0.7.169 / `a1cc3a39` is integrated/pushed to master with its tag;
exact remote refs verified. [Candidate 38557656916](https://github.com/tepong32/grand/actions/runs/38557656916)
passed all 19 jobs, including verify/mysql: native 2,545 / zero skips and SQLite
2,346 / 199 unchanged native-only skips. Original logs, exact identities and
both-store/container cleanup verified in `.tmp/ci-proof-38557656916/acceptance.json`.
All previous 2,544 test identities are retained; one new unskipped case is added.
The [resulting primary run](https://github.com/tepong32/grand/actions/runs/38563345675)
started after promotion; its terminal result and matching retained receipt own
primary acceptance. The handoff links the live verification source for subsequent
notes-only releases; no future status is inferred from the candidate result.
Broader browser/physical acceptance is NOT RUN — OUT OF SCOPE for this test-only
checkpoint; production code and rendering behavior are unchanged.

The initial native invocation was NOT RUN — ENVIRONMENTAL: the isolated loopback
MySQL fixture was stopped and refused the connection before test setup. Its log
is retained separately. The existing owned fixture was restarted after verifying
its data directory, loopback binding and strict mode; operator databases/settings
were not used. The owned MySQL fixture was shut down after successful dependent
validation. No server or native test remains active.

These are synthetic service/HTTP/output checks. Existing fixture Budget
certification is the legacy pilot route; this test does not establish a second
authoritative appropriation/ARO/OBR replay. The linked ordinary replay owns that
separate proof. No browser file-save, official layout, actual bank action, physical
signature, printer or LGU acceptance is claimed. No additional cheque exception
policy is introduced. FG-06/07 remain partial; production remains NO-GO.

See [remaining foundation work](FINANCE_REMAINING_WORK_2026-10-14.md),
[required office outputs](FINANCE_REQUIRED_OUTPUT_MAP.md) and
[current handoff](../CONTINUE.md) for the wider scope and next checkpoint.
