# Treasury source-to-output rehearsal

Development evidence checkpoint, 2026-09-22; branch
`codex/finance-treasury-output-rehearsal`, based on v0.7.136 /
`967c3f8b4a28ba774af39f392ba6d2e23cf6ef75` / PR #97.
See [ordinary cross-office replay](FINANCE_CROSS_OFFICE_OUTPUT_REPLAY.md),
[required output map](FINANCE_REQUIRED_OUTPUT_MAP.md) and
[foundation gate](FINANCE_FOUNDATION_GATE.md).

## Scenario and actual evidence

A fresh isolated default/Finance fixture replayed the existing ordinary service
workflow: 1,000 approved Budget obligation, linked payable, Accounting recognition,
100 deductions, 900 check, independent bank-advice review/acknowledgement,
recorded claimant/receipt release, independent payment JEV posting and bank
reconciliation. Existing Budget/Accounting/Treasury report assertions also ran.
All data and physical actions are synthetic; no real bank, paper, signature,
claimant delivery or LGU acceptance is claimed.

Treasury's permission-checked payment-register and individual-advice download
routes were captured at three points:

| Point | Payment register evidence | Bank-advice evidence |
| --- | --- | --- |
| Bank acknowledged, before release | Release/receipt/payment-JEV fields blank | Exact instrument, fund, 900 amount, reviewed snapshot checksum and acknowledgement reference |
| Release recorded, before JEV creation | Actual retained release timestamp/claimant/receipt, reserved JEV number, Waiting for JEV creation | Same acknowledged advice evidence |
| Payment posted/reconciled | Same release evidence and JEV number, now JEV posted | Same acknowledged advice evidence |

The initial verifier wrongly required the reserved JEV number to be blank before
journal creation and exited 1 after the complete workflow. Source inspection
confirmed number reservation occurs when the posting request is created; the
separate status correctly distinguishes pending from posted. Corrected read-only
verification passed against the same retained workflow and exports. No sources
were rewritten and no second workflow was fabricated to satisfy the check.

All six CSVs match archived bytes, SHA256 headers and manifest lengths/hashes.
Case/instrument IDs, instrument number, advice reference/checksum, fund, 900
amount, receipt and posted payment JEV agree with sources. All three advice
exports have the same hash; later release/posting does not rewrite bank advice.
Earlier payment exports remain unchanged. The generated Treasury report shows
900 released and its source reference matches the check.

## Retained artifacts

- [Verification and source facts](../output/playwright/treasury-output-rehearsal-facts.json)
- Acknowledged: [payment](../output/playwright/treasury-acknowledged-payment.csv), [advice](../output/playwright/treasury-acknowledged-advice.csv)
- Released, unposted: [payment](../output/playwright/treasury-released-unposted-payment.csv), [advice](../output/playwright/treasury-released-unposted-advice.csv)
- Posted: [payment](../output/playwright/treasury-posted-payment.csv), [advice](../output/playwright/treasury-posted-advice.csv)

## Validation and limits

Application code is unchanged. The committed ordinary-workflow test now checks
all three export stages, source identities, amounts, archive manifests and retained
prior bytes. PASS: 9/9 affected SQLite tests, no skips, 12.740s, exit 0:

```text
python .tmp/earlier_sqlite.py vouchers.tests.VoucherWorkflowTests.test_authoritative_budget_to_reconciled_treasury_report_replay vouchers.tests.VoucherWorkflowTests.test_payment_release_creates_event_jev_resumes_and_exports_register vouchers.test_advice_register
```

Fresh default/Finance stores destroyed; log `.tmp/treasury-output-tests.log`.
Standalone rehearsal log `.tmp/treasury-output-rehearsal.log` retains the initial
assertion failure; corrected read-only verifier `.tmp/verify_treasury_outputs.py`
exited 0. Durable automated reproduction is the committed ordinary workflow test.
`git diff --check` PASS. Operator DB SHA256 unchanged:
`C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C`.
All runners are terminal; no fixture server is running. Remote CI is separate.

This is HTTP/service and artifact evidence, not a new browser or physical-output
acceptance run. Native MySQL is NOT RUN - OUT OF SCOPE for a test/evidence-only
checkpoint; no database behavior, schema, posting, permission or lock changes.
No new UX improvement is claimed. The CSVs are controlled data interchange,
not proof of an accepted bank or official local form.

Next reconcile the full requested foundation requirements against the gap register
and prepare the A-K checkpoint report, separating remaining implementation from
local semantics and human/operational acceptance. Full goal remains incomplete,
production NO-GO. eGAPS stays closed; no master merge, deployment or operator edits.
