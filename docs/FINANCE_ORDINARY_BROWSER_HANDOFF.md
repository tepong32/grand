# Ordinary browser handoff and recoverable action forms

Development checkpoint, 2026-09-22. Base v0.7.123 / draft PR #85 has passing remote
verify, native MySQL and GitGuardian checks on `a31d26d3201956e5d7b0bb6509ea0bd50dd087da`.
This checkpoint adds actual browser interaction to the existing service/output proof.

## Defects observed and repaired

An Accounting reviewer submitted a reason and recognition basis but omitted the
required obligation-adjustment basis. The existing error redirect discarded all
entered text. Most ordinary voucher actions had the same behavior; only two
specialized consolidated forms retained their bound submissions.

The shared action handler now renders the submitted action form and deduction
formset on field or service validation errors. Field errors and financial-service
errors remain beside the retained entries. Successful actions still redirect.
Original state-version and idempotency tokens are retained; this does not silently
rebase a stale submission or bypass permission, stage, maker-checker, balance or
posting validation. Current case visibility and action visibility still govern
which form can be shown. Deduction formset-wide errors are now rendered too.

The wet-signature selector exposed internal object labels. It now identifies the
retained signatory and position/role, round and step. Its scoped pending-task query
is unchanged; no signature, custody or acknowledgement is inferred.

## Browser rehearsal

A fresh two-store SQLite fixture was initialized through the existing
`VoucherWorkflowTests` setup and `authoritative_payable_for_review` helper. Thus
Budget authorization, ARO, OBR and submitted payable were service-created setup;
they were not newly entered through browser screens in this checkpoint.

Using separate preparer, validator and Treasury accounts in the real browser:

1. Reproduced the lost-review-text defect, then verified preserved values and inline
   error after repair. Corrected only the missing basis and accepted the payable.
2. Prepared the DV using the fixture's explicit synthetic 1% rule. A deduction of
   99 against a reviewed 1,000 base was rejected with expected amount 10. The
   entered DV and deduction values survived. Correcting to 10 created the DV.
3. Selected the two named signature tasks in order, recording explicitly simulated
   paper returns. Independently validated the DV, created/submitted its JEV and
   posted it as the separate validator through Accounting screens.
4. Entered check 009901 for 1,001. The net-capacity rejection retained the number
   and amount. Corrected it to 990, issued it and sent it for bank advice. The
   error form fit a 390px viewport with document width 390px.
5. Prepared and independently reviewed advice, recorded explicitly synthetic
   submission/response references, then recorded the synthetic claimant/receipt.
   No actual bank submission, acknowledgement, payment or wet signature occurred.
6. Created/submitted the separate payment JEV and independently posted it. The
   case resumed automatically to Released / completed with both JEV links retained.
7. Downloaded the payment register through the Treasury page. It contains exactly
   one 990 released instrument, its synthetic receipt and posted payment JEV.

Read-only fixture verification confirms one case, one instrument, gross 1,000,
withholding 10, net 990 and two posted voucher JEVs (recognition 1,000 and payment
990 debit/credit each). The earlier v0.7.123 service replay deliberately used a
separate 100-deduction example; do not conflate its figures with this browser case.

## Retained evidence

Under `output/playwright/`:

- `ordinary-review-retained.png`, `ordinary-dv-retained.png` and
  `ordinary-check-retained-narrow.png`: correction context survives rejection.
- `ordinary-signature-choice.png`: named retained task selection.
- `ordinary-completed-case.png`: completed case and retained OBR allocation.
- `ordinary-payment-register.csv`: actual browser-downloaded synthetic register.
- `ordinary-browser-facts.json`: asserted final fixture facts.

Ignored reproducibility helpers are `.tmp/ordinary_browser.py` and
`.tmp/ordinary_browser_proof.py`; fixture stores are under
`.tmp/ordinary-browser-20260922`. The seed refuses to overwrite an existing fixture
and asserts both store paths before any migration. Operator stores and eGAPS were
not used. Browser, server and owned native MySQL fixture are stopped.

## Validation and remaining scope

Three new automated checks cover invalid payable review followed by a successful
correction, DV field/service failures with retained deduction rows followed by one
valid DV, and a Treasury field failure without added instruments or events. Fresh
native MySQL passes all three in 6.516s. The initial broader run found one obsolete
302-redirect expectation: 770 passed, 97 skipped and one failed among 868. The
signature-order assertion now checks the retained error page and unchanged state.
Final affected regression passes 120/120, no skips, in 68.688s. Exact commands and
scope are in CONTINUE.md; no full-project pass is inferred from these results.
The signature label was also verified in the browser for both pending steps.

This fixture used an existing template with controlled printing disabled. Actual
printer/stock use, TracePoint physical custody, real wet signatures, external bank
acceptance, exact official forms and named-LGU acceptance are not proved. Neither
are all correction/exception paths or all office roles. FG-07 remains partial.
Continue the foundation gate and required-output fidelity without expanding
unconfirmed local certificate semantics or treating synthetic acceptance as real.
