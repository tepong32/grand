# Direct-bank collections — implementation boundary

2026-09-15. Required by the user's confirmed Treasury methods: cash, cheques and
bank transfers. This document records verified source gaps and the next implementation;
it distinguishes implementation from completed validation and acceptance.

## Current implementation

The direct-bank route is included in development v0.7.108: ordinary and
multi-charge receipt capture, officer refunds, reviewed bank mapping, pinned posting
account, exclusion from cash deposit availability/selection, and bank evidence in
detail/CSV/retained printable output. It reuses the existing source, correction and
posting models; no migration or parallel ledger is introduced.

Focused SQLite session 57488 passed 4/4 in 2.642s (exit 0). The dependent 39-test
runs exposed six setup fixture errors after adding model validation: the synthetic
rules were still in an active release, whose edit guard correctly rejected validation.
SQLite 95543: 28 passed, five native-only skips, six errors, 39.434s, exit 1.
Native 51582: 33 passed, six errors, 52.858s, exit 1. These are
FAIL - CAUSED BY CURRENT WORK (test setup), not production permission regressions.
The fixture now validates in draft and restores active status before receipt actions.
Final SQLite 56117 passed 34 tests with five native-only skips (27.940s, exit 0).
Final native 80199 passed all 39 (92.273s, exit 0), including seven bank scenarios
and five existing collection/refund races. Logs: `.tmp/bank-collections-final-sqlite.log`
and `.tmp/bank-collections-final-native.log`. Both runners are terminal; owned MySQL
is stopped. System/migration-drift checks pass and the operator DB hash is unchanged.
The preceding fee/multi-charge full SQLite run 83114 passed 1,161 tests with 86
native-only skips (1,247 discovered, 600.759s, exit 0). That full run predates the
bank implementation and does not validate it.

## Verified gap before this implementation

- `vouchers/collections.py:receipt_rows` accepts two fixed-account lines only.
  `record_receipt` has no explicit payment method, receiving bank or bank transaction
  identity. `remaining_receipts` treats every posted receipt as awaiting deposit.
- `vouchers/collection_views.py:DepositShareForm` offers every posted receipt in the
  Treasury office. Both this selector and service-level capacity must exclude direct
  bank credits; a UI-only exclusion would leave duplicate deposit posting possible.
- `vouchers/receipt_banks.py` already resolves an approved, date-effective bank setup
  to one active bank mapping and retains its ledger identity. Deposit capture already
  uses this mechanism. Later mapping edits must not reroute an approved receipt.
- `vouchers/advance_refunds.py:record` resolves and locks the original default-store
  case before Treasury/Finance work, reserves dated officer capacity, and credits the
  original advance subsidiary. It currently requires a fixed-account cash debit.
- Multi-charge receipts preserve each reviewed credit recipe and group cash debits
  by purpose on one common account. Bank receipts must retain this behavior.
- Collection corrections already reproduce the original posted journal exactly;
  retained output generation pins source/posting checksums and rendered bytes.

## Implemented route and demonstration scope

Add explicit bank-transfer capture with receiving bank and actual transaction
reference. Require a reviewed bank-mapping debit recipe, not silent substitution of
a fixed cash account. Keep legacy receipts unchanged and do not infer their method
from account codes or free text. Independent review must check the captured mapping;
materialization/recovery must use its approved account identity.

Carry the mode through ordinary and multi-charge receipts and original officer
refunds. Preserve independent approval, current department/UAT boundaries, exact
source correction, officer capacity and subsidiary evidence. Show the receiving bank
and transaction reference in the detail and retained printable source copy; preserve
previously issued copies. Direct bank credits must never become cash deposit capacity.

Demonstrate actual receipt → independent posting → output → exact correction →
successor, with no intervening deposit or duplicate revenue. Also demonstrate mixed
charge purposes, officer refund capacity/correction, changed bank mapping before and
after approval, interrupted handoff recovery, forged deposit allocation rejection and
legacy cash receipt/deposit regression on SQLite and native MySQL.

Cheque receipt, clearing and dishonour remain subsequent required work. A source-error
correction alone does not demonstrate a cheque return lifecycle. Statutory/local form
and operational acceptance remain open; this extension introduces no official account
code or legal calculation assumption.

See [priorities](FINANCE_MODERNIZATION_PRIORITIES.md),
[multi-charge validation](FINANCE_COLLECTION_CHARGES_IN_PROGRESS.md), and
[continuation state](../CONTINUE.md).

## Reproduction scope

Commands: `.venv/Scripts/python.exe .tmp/run_bank_collection_regression.py sqlite`
and the same command with `native`. The local wrapper passes the following labels
to the documented two-store test environment (see `FINANCE_NATIVE_TESTING.md`);
they can also be supplied directly to the respective SQLite/native runner. No operator
store is migrated. Native schemas are recreated fresh and native runs must not overlap.

```text
vouchers.test_collection_charges.CollectionChargeTests.test_receipt_deposits_corrections_replacement_and_retained_copy
vouchers.test_collection_charges.CollectionChargeTests.test_charge_total_and_incompatible_cash_account_are_rejected
vouchers.test_collection_charges.CollectionChargeTests.test_review_detects_recipe_change_and_posting_pins_approved_recipe
vouchers.test_collection_charges.CollectionChargeTests.test_http_charge_entry_and_review_detail
vouchers.test_collection_charges.CollectionChargeTests.test_mixed_cash_purposes_keep_their_amounts_through_deposit
vouchers.test_collection_workflow.CollectionWorkflowTests.test_receipt_and_partial_deposits_preserve_cash_and_recognize_revenue_once
vouchers.test_collection_workflow.CollectionWorkflowTests.test_interrupted_receipt_handoff_recovers_one_finance_journal
vouchers.test_collection_workflow.CollectionWorkflowTests.test_preparer_cannot_review_own_receipt_even_with_review_permission
vouchers.test_collection_workflow.CollectionWorkflowTests.test_balanced_manual_edit_cannot_replace_approved_receipt_rows
vouchers.test_collection_workflow.CollectionWorkflowTests.test_deposit_cannot_predate_collection
vouchers.test_collection_workflow.CollectionWorkflowTests.test_collection_only_policy_does_not_bypass_payment_cycle
vouchers.test_collection_workflow.CollectionWorkflowTests.test_receipt_http_capture_register_export_and_office_boundary
vouchers.test_collection_workflow.CollectionWorkflowTests.test_partial_deposit_web_review_posting_and_register
vouchers.test_collection_workflow.CollectionWorkflowTests.test_unposted_withdrawal_preserves_approval_and_requires_discard
vouchers.test_collection_workflow.CollectionWorkflowTests.test_unposted_deposit_withdrawal_releases_hold_and_keeps_lineage
vouchers.test_collection_workflow.CollectionWorkflowTests.test_posted_deposit_then_receipt_correction_retains_exact_reversals
vouchers.test_collection_workflow.CollectionWorkflowTests.test_future_correction_cannot_fund_earlier_deposit
vouchers.test_collection_workflow.CollectionWorkflowTests.test_retained_printable_copy_survives_correction_and_checks_integrity
vouchers.test_collection_workflow.CollectionWorkflowTests.test_posted_correction_reconciliation_failure_keeps_allocation_until_retry
vouchers.test_collection_workflow.CollectionWorkflowTests.test_historical_correction_keeps_recipe_and_uses_current_numbering
vouchers.test_collection_workflow.CollectionWorkflowTests.test_collection_role_has_navigation_without_disbursement_or_posting_authority
vouchers.test_collection_sources.CollectionSourceStorageTests.test_source_and_independent_decision_evidence_are_retained
vouchers.test_collection_sources.CollectionSourceStorageTests.test_document_version_and_positive_amount_have_database_constraints
vouchers.test_collection_concurrency.CollectionConcurrencyTests.test_competing_deposits_cannot_consume_the_same_receipt
vouchers.test_collection_concurrency.CollectionConcurrencyTests.test_receipt_correction_and_deposit_share_one_source_boundary
vouchers.test_collection_concurrency.CollectionConcurrencyTests.test_duplicate_correction_materialization_recovers_one_reversal
vouchers.test_advance_refunds.AdvanceRefundTests.test_correction_releases_refund_hold_only_from_its_actual_date
vouchers.test_advance_refunds.AdvanceRefundTests.test_interrupted_refund_materialization_recovers_one_hold_and_uat_cannot_prepare
vouchers.test_advance_refunds.AdvanceRefundTests.test_web_refund_retains_printed_officer_source_and_unposted_withdrawal
vouchers.test_advance_refunds.AdvanceRefundTests.test_refund_expense_deposit_and_exact_corrections_retain_original_advance
vouchers.test_advance_refund_concurrency.AdvanceRefundConcurrencyTests.test_refund_and_expense_cannot_consume_the_same_original_advance
vouchers.test_advance_refund_concurrency.AdvanceRefundConcurrencyTests.test_two_refunds_cannot_reserve_the_same_released_balance
vouchers.test_bank_collections.BankCollectionTests.test_bank_credit_correction_successor_and_retained_copy
vouchers.test_bank_collections.BankCollectionTests.test_bank_mapping_is_reviewed_then_pinned
vouchers.test_bank_collections.BankCollectionTests.test_bank_receipt_requires_actual_reference_and_bank_recipe
vouchers.test_bank_collections.BankCollectionTests.test_multi_charge_bank_receipt_preserves_cash_purposes
vouchers.test_bank_collections.BankCollectionTests.test_web_bank_capture_export_and_deposit_selection
vouchers.test_bank_collections.BankCollectionTests.test_interrupted_bank_receipt_recovers_one_posting
vouchers.test_bank_collections.BankAdvanceRefundTests.test_bank_refund_preserves_officer_capacity_and_exact_correction
```

Actual payer refunds and bank-reversed incoming collections are not established by
source-error correction. Those dispositions, cheque lifecycle, exact official forms
and operational acceptance remain open.
