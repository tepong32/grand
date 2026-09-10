# Cash-flow calculation and source classification

Initial implementation validated in v0.7.75 on `codex/finance-cash-flow`, based on remotely verified v0.7.74 (`a951737`). This is M01 financial functionality. It does not complete Finance parity, historical cash classification, mixed-purpose generated payments, full statement-package integration or LGU acceptance. Production remains NO-GO.

## Concrete behavior

The comparative direct-method Cash Flow report uses posted cash/cash-equivalent lines, rather than interpreting every asset movement, voucher recognition or accounting expense as cash. It presents operating, investing and financing receipts and payments separately, keeps exchange effects separate and reconciles opening cash plus flows plus exchange effects to closing cash for each fund and the same period one year earlier.

Accounting selects an explicit cash-account inventory through the existing independently reviewed statement-mapping workflow. Selecting all assets is refused. Known bank mappings and accounts with classified posted cash movements cannot be silently omitted. Local review must establish the actual cash/equivalent scope; the code does not infer it from account names. The initial implementation supports asset cash accounts, not liability-classified overdraft arrangements.

Manual journal lines expose a cash-flow purpose. Existing Finance posting-rule instructions can carry the same purpose for bank/fixed cash-account lines, and generated voucher-payment/remittance JEVs preserve it. The classification is shown on the journal and configuration review screens. Approved rules, generated journals and posted lines retain their existing immutability boundaries. Actual reversals retain the original purpose and reduce its receipt/payment row. Blank legacy classifications do not add a new JSON key to old posting-rule snapshots, preserving their previous checksum calculation.

Internal-transfer cash legs must sum to zero within their source JEV; a one-sided external receipt cannot be hidden by marking it internal. A mixed manual payment can split its cash line between purposes, such as principal and interest. Gross receipts and payments remain separate even when recorded in a combined JEV or their net amount is zero. Unrelated unclassified receipts/payments cannot clear each other's exceptions. A same-period original and actual reversal can neutralize an unclassified movement before a correctly classified replacement, while retaining all source evidence.

The report reuses the existing posted-ledger/opening-evidence calculation rather than creating another source register. Its cash controls do not require non-cash equity adjustments to be classified. Missing cash scope, opening/comparative evidence, cash purpose or exact reconciliation keeps the output in exception. Prior reports retain their own source/mapping/template snapshots and files.

## Numerical proof

The source-to-posting-to-XLSX scenario starts with 400.00 cash. It records 1,000.00 tax receipts, a 600.00 non-cash asset acquisition followed by 200.00 cash settlement, 500.00 borrowing, an 80.00 principal plus 10.00 interest repayment, a 150.00 transfer between cash accounts, 30.00 non-cash depreciation and a 5.00 exchange gain on cash.

Expected operating cash is 990.00, investing cash -200.00 and financing cash 420.00: net cash flows 1,210.00, with closing cash 1,615.00 after the exchange effect. Comparative closing cash is 400.00. A returned 200.00 asset payment reverses its original classification and produces a new closing balance of 1,815.00. The test checks workbook values and byte-for-byte preservation of the original XLSX.

Separate checks cover a misleading internal-transfer label, unclassified movement correction, gross receipt/payment presentation and unrelated offsetting unclassified entries. Existing payment-release and remittance scenarios now also assert that the actual generated bank line retains the reviewed source classification. The Finance setup scenario checks both a changed classification checksum and exact restoration of the original blank-classification snapshot/checksum.

## Reference boundary

The [Municipality of Coron 2024 accomplishment report](https://coron.gov.ph/wp-content/uploads/2025/10/Accomplishment-Report-CY-2024.pdf), printed pages 131–132 (PDF pages 139–140), provides a primary municipal cash-flow example: gross operating receipts/payments, investing purchases, borrowing proceeds and an opening-to-closing cash bridge. Its exact line detail and accepted local form are not asserted to match this implementing LGU.

[XRB's PBE IPSAS 2 text](https://standards.xrb.govt.nz/standards-navigator/pbe-ipsas-2/?version=228), incorporating amendments through January 2021, supports the conceptual distinctions: cash-equivalent transfers are excluded from activities, a repayment may split principal and interest, and cash flow is distinct from non-cash accounting activity. This is a comparative primary standard reference, not Philippine municipal legal authority or a claim that all current IPSAS amendments were implemented. The [IPSASB standards inventory](https://www.ipsasb.org/standards-pronouncements) identifies its newer handbook separately.

## Validation

- FAIL - CAUSED BY CURRENT WORK: first three-test attempt, 1.902 seconds, stopped in the new user fixture because both users had the same empty unique email. Fixed with distinct synthetic addresses; no accounting calculation failed in that attempt.
- PASS: corrected focused Cash Flow tests, 3 tests in 6.353 seconds, with actual independent posting, cash-scope review, XLSX amounts, reversal and retained-file checks.
- PASS: gross/offsetting-cash presentation tests, 2 tests in 0.001 seconds.
- PASS: targeted native MySQL 8.4.11 run, all 6 tests in 20.660 seconds. This executes all three cash-flow cases and the real payment-release, remittance and posting-rule snapshot scenarios against fresh separate test stores.
- PASS: broad Finance/Accounting/reporting/voucher regression, 509 discovered / 506 executed / three native-only skips in 539.571 seconds. The two additional pure presentation tests listed above ran separately. System, migration-drift, compilation and diff checks passed. No migration was applied to the user's stores; the user database SHA-256 remains C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C. All test processes ended and the owned MySQL fixture was shut down.

Commands:

```powershell
.venv/Scripts/python.exe manage.py test reporting.test_cash_flows --noinput
.venv/Scripts/python.exe manage.py test reporting.test_cash_flow_math --noinput
.venv/Scripts/python.exe manage.py test reporting accounting vouchers finance --noinput
.venv/Scripts/python.exe .tmp/portable_mysql.py test reporting.test_cash_flows vouchers.tests.VoucherWorkflowTests.test_payment_release_creates_event_jev_resumes_and_exports_register vouchers.tests.VoucherWorkflowTests.test_remittance_batch_versions_allocations_and_completes_only_after_posting finance.tests.FinanceSetupCenterTests.test_typed_transaction_variant_and_document_rule_are_department_scoped_and_locked_with_release
.venv/Scripts/python.exe manage.py check
.venv/Scripts/python.exe manage.py makemigrations --check --dry-run
git diff --check
```

The broad regression is appropriate because journal source classification, posting-rule snapshots, source bridges, mappings, generated reports and review screens cross Finance/Accounting/voucher/reporting boundaries. The native run covers both new field migrations and real source materialization; native concurrency, full-project/production gates and human printer acceptance remain outside this functional checkpoint and are not claimed as passed.

## Remaining functional work — do not skip these

1. Add a controlled classification path for older posted cash lines without changing their original ledger entries or inventing financial reversals solely to attach reporting metadata. The current blank-field behavior intentionally reports exceptions. Same-period reversal/replacement support is not a substitute for historical classification, especially across closed periods.
2. Support reviewed purpose splits for mixed generated payment events. A fixed-purpose bank instruction works for a homogeneous payment; the present scalar event-amount rule cannot allocate one generated payment between principal/interest or operating/capital purposes. The mixed-payment example above proves manual JEV support only.
3. Confirm cash/equivalent and any applicable overdraft scope, exact local line granularity, classifications and output layout against actual LGU evidence. Do not infer complete coverage from the known-bank mapping check.
4. Integrate Cash Flow and Net Assets into the complete statement-note/package and signed-reference paths. Those currently assume the older Position/Performance pair in places.
5. Continue M02 earlier-payable linkage and the retained broader transaction/office/output/operational acceptance queue. No further general UX/framework work is substituted for these functions.

Next implementation target: independently reviewed purpose allocations attached to the immutable posted cash source. Each source line's positive allocated amounts must equal its posted debit or credit exactly; source identity/checksum and the chosen allocation version must be retained in each report. This should cover both historical blank classifications and a mixed generated cash line without editing the journal or fabricating a financial reversal. Preserve original inline purposes as source evidence, current office/UAT boundaries, independent approval and prior-output reproduction. Prove closed-period classification, mixed generated payments and conflicting approval behavior on the appropriate stores before treating that path as complete.
