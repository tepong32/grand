# Earlier payable accrual generation

Checkpoint v0.7.81, `codex/finance-earlier-accrual`, based on pushed v0.7.80 (`f80042f`). Implements the next M02 functional gap under the [modernization priorities](FINANCE_MODERNIZATION_PRIORITIES.md). Finance production remains **NO-GO**.

## Implemented behavior

| Step | Supported behavior and retained control |
|---|---|
| Requesting-office intake | Existing authoritative Budget allocation and documentary checks remain required. Accepted allocations must reconcile to the full claim. |
| Accounting review | Earlier accrual requires an explicit actual recognition date, supporting reference and a reviewed delivery/acceptance or billing-validation recognition rule. Missing/future dates, closed periods, wrong office and UAT mutation are rejected. Invoice date is retained separately and is not substituted for recognition date. |
| Recognition | Existing immutable posting requests pin the claim, invoice, documentary references, obligation identities/checksums, reviewer, date, amounts and rule. No DV is manufactured. The supported recipe debits each allocation and credits gross payable in one fund. |
| Independent posting | Existing JEV preparation/posting and maker-checker controls create one named original liability credit. Posting synchronization unlocks DV preparation. Repeated requests and interrupted default/Finance handoffs retain one source JEV. |
| DV settlement | The generated original claim is the permitted/default selection. The prior-payable reservation, deduction and payment route reduces that exact liability without recognizing the expense again. Claim CSV exports show dated applications and outstanding amounts. |
| Corrections | A pre-DV draft must be discarded before its payable evidence can be returned/re-reviewed; a pending request can be cancelled by the return. The successor retains a new controlled number/version. Posted accrual evidence cannot be returned and rewritten. Later DV correction retains the posted original claim. |
| Accounts and work queues | Existing office/role checks apply. The review form records recognition evidence, the case displays it, and My Work retains the completed review action. |

## Architecture and limits

No new database model or schema migration. The existing request/JEV/journal-line/claim mechanisms remain authoritative across the separate default and Finance stores. Earlier-accrual source creation, pre-DV return and posting synchronization take the default case lock before modifying the source handoff. Finance drafts survive a default-link failure and are recovered by immutable source identity. Validation failures retain their default-store failure reason; raising the error does not roll that evidence back. A native discard followed by an interrupted default status update can be reconciled by the supported pre-DV return after verifying that no active native JEV remains. Native JEV presence blocks a source return even if its default link was interrupted.

This supports one claim and one fund, with the full reviewed claim allocated before intake acceptance. Prior-payable settlement breadth and remaining correction limitations are documented in [the v0.7.80 integration report](FINANCE_PRIOR_PAYABLE_DV_2026-09-10.md). Delivery/acceptance and billing-validation are locally configured recognition points, not an assertion that one recognition policy applies to every transaction. No statutory calculation or universal policy is introduced here.

Historical source attribution, governed correction of already-posted deduction adjustments and consolidated multi-claim settlement remain incomplete. A posted original claim cannot be casually rewritten; financial correction requires retained journal lineage. Exact local forms, eGAPS inventory, ordinary office scenarios, usability/WFH and operational/LGU acceptance remain separate gates. See D-074 in [implementation decisions](IMPLEMENTATION_DECISIONS.md) and [the continuation handoff](../CONTINUE.md).

## Validation

Final PASS: `.venv/Scripts/python.exe .tmp/earlier_sqlite.py vouchers.test_earlier_accruals`, all six tests in 7.230 seconds. Final PASS: `.venv/Scripts/python.exe .tmp/prior_native_authority.py vouchers.test_earlier_accruals vouchers.test_earlier_accrual_concurrency`, all seven tests in 31.708 seconds. These cover the final code, actual review-to-claim-to-payment/CSV, deductions and corrected DV signatures, form/authority/policy checks, failed creation evidence, interrupted materialization/posting/discard handoffs and concurrent review/materialization/return.

PASS: `.venv/Scripts/python.exe manage.py check`; `.venv/Scripts/python.exe manage.py makemigrations --check --dry-run`; `.venv/Scripts/python.exe -m compileall -q vouchers finance`; `git diff --check`; 251 local document links across 14 files. No schema changes detected.

NOT RUN - OUT OF SCOPE: full-project/full-native regression, actual printing, statutory/local form comparisons, operational recovery/WFH and human acceptance. The affected Finance regression and real-source/native recovery/concurrency checks were selected for this feature. The broad run's two fixture failures were repaired and pass in the final focused runs; the entire broad suite was not repeated after those corrections and the narrow final recovery changes.

Initial PASS: `.venv/Scripts/python.exe manage.py test vouchers.test_earlier_accruals --noinput`, 13 tests in 9.711 seconds. Four new scenarios plus nine prior-payable tests were discovered because a test class was imported directly; the import was changed to a module to avoid duplicate discovery in subsequent runs. This initial run preceded the added HTTP/deduction/native-concurrency coverage.

No eGAPS access, user-store migration, live record change or actual office printing is part of these tests. The user's modified `db.sqlite3` and unrelated `accounting/test_policy_concurrency.py` remain outside the checkpoint.

Initial native run: FAIL - CAUSED BY CURRENT WORK (test fixtures), `.venv/Scripts/python.exe .tmp/prior_native_authority.py vouchers.test_earlier_accruals vouchers.tests.VoucherWorkflowTests.test_authoritative_budget_to_reconciled_treasury_report_replay`: seven tests, five passed and two failed, 48.960 seconds. The HTTP fixture sent `expected_version` instead of the actual form field `state_version`; the wrong-source assertion expected a later error even though the existing mapping guard already rejected it. Both fixtures were corrected. The earlier-accrual source/payment/recovery scenarios and the original Budget-to-reconciled-Treasury replay passed in this run.

The native wrapper invokes the committed fresh two-store runner with isolated development logs and the owned loopback MySQL 8.4.11 fixture. The ignored SQLite wrapper invokes Django's ordinary test command with its own log filenames, avoiding the previously observed Windows shared-log rotation contention. Neither wrapper changes application logging configuration or user data.

Broader affected regression: `.venv/Scripts/python.exe manage.py test vouchers accounting finance reporting departments --noinput`, 576 discovered, 564 passed, ten native-only skips and the same two initial fixture assertion failures, 337.920 seconds. No other failures. This run preceded the final failure-reason/discard-handoff changes and corrected fixtures; final focused runs cover those changes. Budget behavior is also covered by the reused actual authoritative Budget-to-payable setup and the original full-cycle replay on MySQL.

Second native run: `.venv/Scripts/python.exe .tmp/prior_native_authority.py vouchers.test_earlier_accruals vouchers.test_earlier_accrual_concurrency vouchers.tests.VoucherWorkflowTests.test_authoritative_budget_to_reconciled_treasury_report_replay`, eight tests, seven passed and one test-fixture error, 27.608 seconds. The native concurrency scenario passed competing review retries, materializers and return/materialization without duplicate sources. The remaining fixture attempted to return old, already-signed tasks during the corrected DV's second signature round. The local helper now returns only pending tasks with task-specific idempotency keys.

The corresponding SQLite command `.venv/Scripts/python.exe .tmp/earlier_sqlite.py vouchers.test_earlier_accruals vouchers.test_earlier_accrual_concurrency` discovered seven tests: five passed, one native-only skip and the same signature-fixture error, 7.561 seconds. This run included the final interrupted-discard recovery path; that scenario passed.

All test runners ended; the owned MySQL server was stopped and port 33308 verified closed. The user's `db.sqlite3` retains SHA-256 `C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C`. No eGAPS access or user-store migration occurred. The unrelated policy-concurrency draft remains untouched and uncommitted.
