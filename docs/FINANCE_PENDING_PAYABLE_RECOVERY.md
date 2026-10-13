# Pending payable handoff recovery — development checkpoint

The v0.7.120 OBR handoff correctly linked interrupted pending cases back to the
retained payable. The case page, however, rendered recovery only for a failed link.
A process interruption after default-store intake creation could therefore leave
an authorized requester without the visible action already supported by the service.

## Repair

Use the existing `reconcile_authoritative_obligation` action for both pending and
failed links. The view retains requesting-office preparation permissions, UAT denial
and the pre-DV/corrected-advance boundary. It does not introduce another recovery
service, automatic retry, allocation or financial state. A linked case loses the
recovery button. The next-action label and empty allocation guidance prioritize
reconciling the retained source rather than adding a replacement allocation.

Tests simulate process interruption before the Finance allocation and after that
allocation but before the default projection is rebuilt. HTTP recovery and repeated
submission must retain exactly one case, one active allocation, one reconciliation
event and the original obligation movement. Separate checks deny recovery to another
office and UAT, even with operational permission.

## Validation

- PASS: focused SQLite, `python .tmp/earlier_sqlite.py budget.test_payable_handoff`,
  7/7, 10.840s, exit 0; `.tmp/pending-recovery-focused.log`.
- PASS: fresh native MySQL, `python .tmp/retrieval_native.py budget.test_payable_handoff`,
  7/7, 14.112s, exit 0; `.tmp/pending-recovery-native.log`. Both native stores destroyed.
- PASS: final dependent SQLite, `python .tmp/earlier_sqlite.py budget.test_payable_handoff vouchers.tests finance.test_work_tasks.FinanceBudgetWorkTaskContractTests`,
  102/102, no skips, 64.933s, exit 0; `.tmp/pending-recovery-regression.log`.
  Both test stores destroyed. Scope covers new handoff tests, all voucher workflow
  tests and Budget work-queue contracts. The final badge CSS was browser-verified.
- PASS: touched Python compilation and `git diff --check`. Operator database SHA256
  remains `C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C`.
- PASS: synthetic browser recovery before allocation and a separate disposable-fixture
  pending-after-allocation state both reconcile the retained case. Final next-action
  wording prioritizes recovery and the button disappears after success. Screenshots:
  `output/playwright/pending-obligation-before.png` (retained existing allocation),
  `pending-obligation-recovered.png`, `pending-obligation-narrow.png`.
- Browser inspection found the case heading's long status badge widened a 390px page
  to 405px. A page-scoped wrapping rule restores a 390px document width; financial
  tables remain internally scrollable. No shared stylesheet changed.
- Owned browser/server/MySQL stopped. No operator data or schema migration. Existing
  allocation locks, capacity checks, independence, idempotency and cross-store recovery
  remain authoritative. This change exposes the existing recovery service; it does
  not alter its financial writes or claim new concurrency guarantees.
- NOT RUN — OUT OF SCOPE: another full-project suite for this bounded view/template
  change, production deployment and exact local-form/LGU acceptance. v0.7.120 remote
  verify and MySQL checks pass on its exact published head; these are baseline evidence.

This is one corrected ordinary workflow continuation, not complete FG-07 or actual
LGU/form/production acceptance. Certificate capacity remains unconfirmed. Next work
remains the existing foundation gate and required-output mapping.
