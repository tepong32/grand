# Netted remittance receipt — current checkpoint

Combined checkpoint gate (2026-09-15): `.venv/Scripts/python.exe .tmp/earlier_sqlite.py`
passed 1,161 tests with 86 native-only skips (1,247 discovered, 600.759s, exit 0,
session 83114). Log: `.tmp/receipt-breadth-full-sqlite.log`. This broad gate covers
the fee and multi-charge checkpoint before subsequent direct-bank changes.

Included in development v0.7.108, `codex/finance-collection-clearing`, based on integrated
v0.7.107. This is not a Finance-completion or production claim. See
[current combined validation](FINANCE_CHEQUE_COLLECTIONS_IN_PROGRESS.md).

Checkpoint review on 2026-09-15 reproduced an oversized service-level fee (`1E+100`)
raising `decimal.InvalidOperation` before the controlled amount check. The web form
already enforced 18 digits; the service now enforces the same maximum before centavo
quantization. `ReceiptFeeInputTests` passes oversized, non-finite, negative, fractional
centavo and zero-fee cases (one test with subcases, 0.003s). Logs:
`.tmp/receipt-fee-limit-reproduction.log` (expected error) and
`.tmp/receipt-fee-limit-final.log` (PASS). This database-independent guard was added
after the combined full-suite launch and is validated separately; it does not alter
posting, reservations, mappings or supported amounts.

## Integration prerequisite completed

Version Manager patch v0.7.107 is commit `1932735b3ff6ffa6051691e60eec0a80514a3904`.
Master and tag were verified at that commit; PR #69 is merged.
[CI run 34857416703](https://github.com/tepong32/grand/actions/runs/34857416703) passed:
full committed SQLite 1,193 discovered / 1,109 passed / 84 skipped, 463.107s;
Telegram 5/5, 0.067s; fresh MySQL 1,193/1,193, 1528.255s; dependency/security and
system/migration checks. The earlier local 1,195 count includes two unrelated untracked
tests excluded from the release, explaining the discovery difference. The operator DB
and unrelated files were preserved. No deployment or live migration was performed.

## Concrete source-to-ledger scenario

A documented gross refund of 100 with a deducted bank charge of 5 records actual bank
credit 95, expense 5 and original withholding credits 100. Gross original-liability
allocations retain capacity controls; net cash cannot masquerade as gross restored
withholding. The original outward remittance is unchanged. A subsequent receipt error
uses the existing independently reviewed exact reversal, including both cash and fee.

The existing immutable proposal holds optional fee amount, net receipt, explicit active
Accounting expense account and bank advice. Independent Accounting review checks that
account against the captured proposal; later mapping/account changes cannot silently
reroute posting. The existing form and retained CSV expose gross, fee and net distinctly.
CSV gross/fee/net fields are receipt-level totals repeated with each allocation row;
allocation amounts remain per original liability. No-fee proposals keep their original
shape and posted history is not backfilled.

Submission/posting, materialization recovery and reconciliation validate the fee-bearing
journal against the retained proposal, source fund, cash purpose and subsidiary identities.
No new ledger, approval engine, permission or database schema is introduced. Account
selection is an explicit reviewed operational input, not a hard-coded statutory account
recommendation or an assertion that local forms/legal interpretation have been accepted.

## Validation

FAIL - baseline gap: SQLite runner 94244, one test, 2.541s, exit 1; `propose_return`
rejected the unsupported `fee_amount` input. Log: `.tmp/receipt-fees-baseline.log`.

PASS: focused SQLite 25640, 4/4, 4.475s, exit 0; native MySQL 35269, 4/4,
5.931s, exit 0. Each exercises four new scenarios:
netted receipt plus exact correction; invalid fee/nonexpense account; changed review or
balanced-but-altered journal; HTTP capture and retained gross/net export. Logs:
`.tmp/receipt-fees-focused.log`, `.tmp/receipt-fees-focused-native.log`.

Commands use `.venv/Scripts/python.exe .tmp/earlier_sqlite.py` and the documented fresh
native runner through `.tmp/prior_native_authority.py`, with the four named methods in
`vouchers.test_receipt_fees.ReceiptFeeTests`. Both focused runs are complete.

PASS: dependent SQLite 62859, 30 discovered / 23 passed / seven native-only skips,
29.138s, exit 0. PASS: native 53462, all 30 passed including seven races, 60.322s,
exit 0. Commands:
`.venv/Scripts/python.exe .tmp/run_receipt_fee_regression.py sqlite` / `native`.
The retained `.tmp/receipt-fees-regression-labels.json` selects 30 directly declared tests
across receipt fees, original returns, receiving banks, receipt corrections, filings,
withdrawal, corrected settlement and seven native races; inherited duplicates are omitted.
Logs: `.tmp/receipt-fees-regression-sqlite.log`, `.tmp/receipt-fees-regression-native.log`.
All dependent runs have ended. System/migration-drift/diff checks pass. Owned MySQL
was stopped after the final native run; the protected operator DB hash is unchanged.
This checkpoint is local and uncommitted; no second release or deployment is claimed.

Full project regression on this new fee change: NOT RUN - OUT OF SCOPE. The shared
Accounting hook is conditional only on the new optional deducted-fee evidence; all
existing no-fee paths retain their prior behavior. Focused plus dependent receipt and
native concurrency suites cover the changed contracts. The full-project CI results
above apply to the preceding v0.7.107 integration, not to this uncommitted feature.

## Remaining boundaries

This receipt route requires positive net cash. All-fee/no-cash dispositions, actual agency
credits/offsets/repayments, wider collection instruments and generated-history adoption
remain separate functional paths. Exact statutory/local presentation, ordinary-office
scenarios, actual eGAPS inventory, usability/WFH and operational/LGU acceptance remain
open. Cash lines retain the actual net money movement; this checkpoint does not fabricate
a separate gross bank credit/debit or claim statutory cash-flow presentation acceptance.


## Reproducing the selected scope

For a fresh checkout without ignored helper files, use Python 3.11 and the committed
`manage.py test` / `scripts/run_mysql_tests.py` runners. The exact 30 labels used above
are below (the native runner requires the documented disposable-server environment).

```text
[
  "vouchers.test_receipt_fees.ReceiptFeeTests.test_netted_receipt_and_exact_correction_preserve_gross_fee_net",
  "vouchers.test_receipt_fees.ReceiptFeeTests.test_fee_cannot_exceed_receipt_or_use_nonexpense_account",
  "vouchers.test_receipt_fees.ReceiptFeeTests.test_review_and_posting_reject_changed_fee_evidence",
  "vouchers.test_receipt_fees.ReceiptFeeTests.test_http_fee_entry_and_retained_gross_net_export",
  "vouchers.test_remittance_returns.RemittanceReturnTests.test_partial_returns_restore_only_allocated_withholding_then_allow_correction",
  "vouchers.test_remittance_returns.RemittanceReturnTests.test_interrupted_return_materialization_reuses_exact_journal",
  "vouchers.test_remittance_returns.RemittanceReturnTests.test_http_entry_independent_review_and_retained_exports",
  "vouchers.test_remittance_returns.RemittanceReturnTests.test_discarded_return_draft_preserves_approval_and_allocation",
  "vouchers.test_receipt_banks.ReceiptBankTests.test_http_bank_selection_posting_correction_and_exports",
  "vouchers.test_receipt_banks.ReceiptBankTests.test_changed_mapping_requires_fresh_proposal_before_review",
  "vouchers.test_receipt_banks.ReceiptBankTests.test_approved_bank_is_not_rerouted_by_later_mapping_changes",
  "vouchers.test_receipt_banks.ReceiptBankTests.test_unmapped_or_inactive_bank_cannot_be_selected",
  "vouchers.test_receipt_corrections.ReceiptCorrectionTests.test_http_exact_correction_and_replacement_retains_receipt_and_outputs",
  "vouchers.test_receipt_corrections.ReceiptCorrectionTests.test_consumed_withholding_blocks_correction_and_rejection_releases_hold",
  "vouchers.test_receipt_corrections.ReceiptCorrectionTests.test_rejection_retains_proposal_and_releases_hold",
  "vouchers.test_receipt_corrections.ReceiptCorrectionTests.test_discard_and_interrupted_materialization_recover_exact_correction",
  "vouchers.test_receipt_corrections.ReceiptCorrectionTests.test_nonmirrored_financial_lines_cannot_submit",
  "vouchers.test_receipt_corrections.ReceiptCorrectionTests.test_unposted_withdrawal_preserves_review_and_releases_hold",
  "vouchers.test_remittance_return_filings.RemittanceReturnFilingTests.test_verified_filing_is_retained_and_amendment_remains_available_after_return",
  "vouchers.test_remittance_return_withdrawal.RemittanceReturnWithdrawalTests.test_http_withdrawal_retains_approval_and_corrected_receipt_can_post",
  "vouchers.test_remittance_return_withdrawal.RemittanceReturnWithdrawalTests.test_live_draft_blocks_withdrawal_but_discarded_chain_can_close",
  "vouchers.test_remittance_return_withdrawal.RemittanceReturnWithdrawalTests.test_posted_finance_receipt_cannot_be_withdrawn_before_or_after_handoff",
  "vouchers.test_returned_remittance_settlement.ReturnedRemittanceSettlementTests.test_actual_return_corrected_dv_payment_and_retained_outputs",
  "vouchers.test_remittance_return_concurrency.RemittanceReturnConcurrencyTests.test_competing_actual_returns_cannot_allocate_the_same_original_amount",
  "vouchers.test_remittance_return_concurrency.RemittanceReturnConcurrencyTests.test_competing_review_decisions_retain_one_posting_request",
  "vouchers.test_receipt_correction_concurrency.ReceiptCorrectionConcurrencyTests.test_receipt_and_deduction_corrections_cannot_consume_same_restored_withholding",
  "vouchers.test_receipt_correction_concurrency.ReceiptCorrectionConcurrencyTests.test_duplicate_receipt_correction_materialization_keeps_one_reversal",
  "vouchers.test_receipt_correction_concurrency.ReceiptCorrectionConcurrencyTests.test_withdrawal_cannot_bypass_independent_correction_posting",
  "vouchers.test_remittance_return_withdrawal_concurrency.RemittanceReturnWithdrawalConcurrencyTests.test_withdrawal_and_materialization_share_the_batch_lock",
  "vouchers.test_remittance_return_withdrawal_concurrency.RemittanceReturnWithdrawalConcurrencyTests.test_withdrawal_cannot_race_past_independent_posting"
]
```


## Full corrected-payment scenario follow-up — 2026-09-15

The prior selected settlement regression used an ordinary no-fee receipt. The additional
`ReceiptFeeSettlementTests.test_actual_return_corrected_dv_payment_and_retained_outputs`
uses the actual 100 gross / 5 fee / 95 cash receipt before deduction correction, revised
DV/signatures/recognition/payment and a corrected 50 remittance. It checks final zero
withholding, the retained original outgoing journal, the untouched fee-bearing incoming
journal, the payable balance and all original/receipt/corrected exports. Runtime code
is unchanged; this establishes broader daily-office evidence rather than another framework.

PASS: SQLite 67829, 1/1, 3.421s, exit 0; native 34276, 1/1, 6.372s, exit 0,
execute this exact label through the same isolated runners as above. Logs: `.tmp/receipt-fees-settlement-sqlite.log` and
`.tmp/receipt-fees-settlement-native.log`. Both runners ended, and owned MySQL was stopped.
The post-push master CI run 34860643656 also passed on the integrated v0.7.107 source.


A review then isolated the fee-specific `propose` fixture override to this one scenario;
inherited ordinary partial-return tests keep their original no-fee helper. PASS: SQLite 91133, 2/2, 9.365s, exit 0, exercises the full netted settlement and
inherited partial-return scenario on that final fixture shape (`.tmp/receipt-fees-settlement-isolated-sqlite.log`). Production code is
unchanged. Native results above cover the same financial-service calls before this
fixture-only isolation; no additional native rerun is needed for the Python test binding.


The test module now imports fixture modules rather than exposing imported TestCase
classes to discovery; this removes duplicate imported test discovery without changing
base classes or financial calls. Compilation and diff checks pass. All scenario runners
have ended. Remaining implementation and acceptance boundaries above remain open.
