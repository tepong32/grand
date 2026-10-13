# One receipt covering multiple reviewed collection charges

Combined checkpoint gate (2026-09-15): `.venv/Scripts/python.exe .tmp/earlier_sqlite.py`
passed 1,161 tests with 86 native-only skips (1,247 discovered, 600.759s, exit 0,
session 83114). Log: `.tmp/receipt-breadth-full-sqlite.log`. This broad gate covers
the fee and multi-charge checkpoint before subsequent direct-bank changes.

Included in development v0.7.108 on `codex/finance-collection-clearing`, alongside the
validated netted-remittance-receipt and bank/cheque-clearing work. Base is integrated
v0.7.107; see [current combined validation](FINANCE_CHEQUE_COLLECTIONS_IN_PROGRESS.md).

## Concrete gap and implementation

Source inspection found `collections.receipt_rows` accepts exactly two posting-rule
instructions, with the entire receipt amount credited to one revenue/liability account.
There was no source breakdown for one payment covering multiple collection types.
This is a concrete collection breadth limitation; it is not a claim about an unobserved
eGAPS screen or acceptance of a local official receipt layout.

The new optional breakdown uses existing approved collection types and their two-line
recipes. Each explicit charge has a positive amount; the sum equals the one actual
receipt total. Types must share the approved Accounting release, fund, collection cash
account. Distinct cash-flow purposes retain their separate cash debit amounts. The source retains type labels, amounts and each rule
snapshot/checksum. Independent review checks current recipes against that captured
proposal. Materialization uses the approved snapshots; later rule edits cannot silently
reroute a charge. Existing no-breakdown receipts keep their original proposal shape.
Officer advance refunds remain separate source-linked transactions.

Cash debits are grouped by their reviewed purpose and sum to the one receipt total,
with explicit revenue/liability credits for the charges. Existing partial deposits consume the same receipt cash once. Exact receipt
correction requires deposits corrected first, then reverses every original credit.
The form, review detail and retained printable copy expose the charge breakdown; old
issued bytes remain unchanged. No new ledger, rule engine, permission or schema is added.

## Validation results

Initial SQLite runner 97955 completed four direct scenarios in `CollectionChargeTests`:
receipt → partial deposits → deposit corrections → receipt correction → revised receipt
and retained copy; invalid total/incompatible cash purpose; review-time changed recipe
and post-approval retained recipe; HTTP capture/detail. Log:
`.tmp/collection-charges-focused-sqlite.log`. Result: three passed / one fixture error,
3.156s, exit 1. FAIL - CAUSED BY CURRENT WORK: the HTTP test used a nonexistent route
name; it now uses the actual `collection_create` route. No runtime route was changed.

Source review then extended combined receipts to retain separate cash purposes within
the common cash account. Deposit capture validates/sums those source cash lines rather
than assuming only one line. PASS: SQLite 7883, 5/5, 3.726s, exit 0. Native 37237 passed the same five scenarios, 4.661s, exit 0, including mixed
tax/service purposes and deposit. Logs:
`.tmp/collection-charges-final-sqlite.log`, `.tmp/collection-charges-final-native.log`.
Both focused runs have ended.
System checks, migration drift and diff checks pass. The final native/dependent collection, advance-refund, correction, output and
concurrency results are recorded below.

## Boundaries and next work

Mixed cash accounts, different funds/releases, cheque/electronic collection
instrument handling and wider collection scenarios remain separate work. This uses
reviewed locally configured recipes, without inventing statutory rates or account codes.
Exact official receipt layout/printing, actual eGAPS inventory, ordinary office acceptance
and later usability/WFH/operational gates remain open. eGAPS and operator databases
are untouched; all validation uses disposable separate stores.


PASS: dependent SQLite 35497, 32 discovered / 27 passed / five native-only skips,
18.454s, exit 0, over directly declared collection, storage,
advance-refund and native-concurrency tests. Command:
`.venv/Scripts/python.exe .tmp/run_collection_charge_regression.py sqlite`.
PASS: native counterpart 83346, all 32 passed including five concurrency cases,
61.792s, exit 0. It started after focused native 37237 ended, preserving exclusive
use of the disposable test schemas. Its log is `.tmp/collection-charges-regression-native.log`. Labels are retained in
`.tmp/collection-charges-regression-labels.json`; log:
`.tmp/collection-charges-regression-sqlite.log`. All runners have ended; owned MySQL was stopped. System/migration-drift, JavaScript
syntax and diff checks pass. The operator database hash remains unchanged. This
checkpoint remains local and uncommitted alongside the netted-receipt work.


Full-project tests on this extension: NOT RUN - OUT OF SCOPE. The selected regression
covers the changed receipt/deposit source, web form, output, correction and advance-refund
contracts, including native concurrency. The earlier full project CI applies to v0.7.107,
not this uncommitted extension. Official form/printer acceptance remains unperformed.

Exact selected labels for reproduction with Python 3.11 `manage.py test` or the committed
fresh native `scripts/run_mysql_tests.py` runner (native environment as documented):

```text
[
  "vouchers.test_collection_charges.CollectionChargeTests.test_receipt_deposits_corrections_replacement_and_retained_copy",
  "vouchers.test_collection_charges.CollectionChargeTests.test_charge_total_and_incompatible_cash_account_are_rejected",
  "vouchers.test_collection_charges.CollectionChargeTests.test_review_detects_recipe_change_and_posting_pins_approved_recipe",
  "vouchers.test_collection_charges.CollectionChargeTests.test_http_charge_entry_and_review_detail",
  "vouchers.test_collection_charges.CollectionChargeTests.test_mixed_cash_purposes_keep_their_amounts_through_deposit",
  "vouchers.test_collection_workflow.CollectionWorkflowTests.test_receipt_and_partial_deposits_preserve_cash_and_recognize_revenue_once",
  "vouchers.test_collection_workflow.CollectionWorkflowTests.test_interrupted_receipt_handoff_recovers_one_finance_journal",
  "vouchers.test_collection_workflow.CollectionWorkflowTests.test_preparer_cannot_review_own_receipt_even_with_review_permission",
  "vouchers.test_collection_workflow.CollectionWorkflowTests.test_balanced_manual_edit_cannot_replace_approved_receipt_rows",
  "vouchers.test_collection_workflow.CollectionWorkflowTests.test_deposit_cannot_predate_collection",
  "vouchers.test_collection_workflow.CollectionWorkflowTests.test_collection_only_policy_does_not_bypass_payment_cycle",
  "vouchers.test_collection_workflow.CollectionWorkflowTests.test_receipt_http_capture_register_export_and_office_boundary",
  "vouchers.test_collection_workflow.CollectionWorkflowTests.test_partial_deposit_web_review_posting_and_register",
  "vouchers.test_collection_workflow.CollectionWorkflowTests.test_unposted_withdrawal_preserves_approval_and_requires_discard",
  "vouchers.test_collection_workflow.CollectionWorkflowTests.test_unposted_deposit_withdrawal_releases_hold_and_keeps_lineage",
  "vouchers.test_collection_workflow.CollectionWorkflowTests.test_posted_deposit_then_receipt_correction_retains_exact_reversals",
  "vouchers.test_collection_workflow.CollectionWorkflowTests.test_future_correction_cannot_fund_earlier_deposit",
  "vouchers.test_collection_workflow.CollectionWorkflowTests.test_retained_printable_copy_survives_correction_and_checks_integrity",
  "vouchers.test_collection_workflow.CollectionWorkflowTests.test_posted_correction_reconciliation_failure_keeps_allocation_until_retry",
  "vouchers.test_collection_workflow.CollectionWorkflowTests.test_historical_correction_keeps_recipe_and_uses_current_numbering",
  "vouchers.test_collection_workflow.CollectionWorkflowTests.test_collection_role_has_navigation_without_disbursement_or_posting_authority",
  "vouchers.test_collection_sources.CollectionSourceStorageTests.test_source_and_independent_decision_evidence_are_retained",
  "vouchers.test_collection_sources.CollectionSourceStorageTests.test_document_version_and_positive_amount_have_database_constraints",
  "vouchers.test_collection_concurrency.CollectionConcurrencyTests.test_competing_deposits_cannot_consume_the_same_receipt",
  "vouchers.test_collection_concurrency.CollectionConcurrencyTests.test_receipt_correction_and_deposit_share_one_source_boundary",
  "vouchers.test_collection_concurrency.CollectionConcurrencyTests.test_duplicate_correction_materialization_recovers_one_reversal",
  "vouchers.test_advance_refunds.AdvanceRefundTests.test_correction_releases_refund_hold_only_from_its_actual_date",
  "vouchers.test_advance_refunds.AdvanceRefundTests.test_interrupted_refund_materialization_recovers_one_hold_and_uat_cannot_prepare",
  "vouchers.test_advance_refunds.AdvanceRefundTests.test_web_refund_retains_printed_officer_source_and_unposted_withdrawal",
  "vouchers.test_advance_refunds.AdvanceRefundTests.test_refund_expense_deposit_and_exact_corrections_retain_original_advance",
  "vouchers.test_advance_refund_concurrency.AdvanceRefundConcurrencyTests.test_refund_and_expense_cannot_consume_the_same_original_advance",
  "vouchers.test_advance_refund_concurrency.AdvanceRefundConcurrencyTests.test_two_refunds_cannot_reserve_the_same_released_balance"
]
```
