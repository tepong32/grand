# Historical payable claim attribution

M02 development v0.7.84 on `codex/finance-historical-claims`, based on pushed v0.7.83 `47a5c7514c968b54d8d30acc211cc4a0ae2364ed`. Finance production remains **NO-GO**. The full Finance modernization goal remains active.

## Financial behavior

Accounting can submit an attribution from an original posted liability credit's journal page. The preparer selects a governed payee, records the original invoice/claim reference and supporting reconciliation schedule, and identifies every historical application and exact reversal. A different authorized Accounting reviewer approves or returns it. The original journal lines and stored subsidiary details are unchanged.

| Path | Result and retained evidence |
|---|---|
| Original credit without individual claim fields | Approved identity makes the original credit selectable in the existing claim register, manual application form and prior-payable DV validation |
| Earlier partial payment, deduction or reduction | Its whole liability line applies to the original claim; existing applications reduce available and dated capacity |
| Earlier returned payment | Requires the actual, exactly mirrored posted reversal and its original application; unfinished reversal drafts must be resolved first |
| Later application or reversal | Uses the existing journal's original-claim link, independent posting and dated capacity checks |
| Existing legacy payee label | New subsidiary reports project the approved identity over the original detail and retain that original detail in report source evidence |
| Missing historical subsidiary detail | New reports derive the reviewed detail from the unchanged liability line; no journal or stored subsidiary row is fabricated |
| Correct an attribution | Submit a successor based on the current approved version; retain older proposals/decisions and issued export files |
| Identity already retained by native applications or DV reservations | Relabelling is refused; old financial links cannot silently switch invoice/payee |
| Historical application already used by a later reversal | Removal is refused, preserving the reversing entry's original financial basis |
| Competing approvals or claim reservation | Fund and original/application row locks protect invoice identity, exclusive application attribution and available capacity |

Claim totals, payable subsidiary schedules and GL control reconciliation share the reviewed projection. Reporting sources identify original journal lines and the selected attribution version/checksum; the CSV archive audit retains selected attribution versions too. Existing tax/withholding details remain separate and cannot be converted into payable attribution.

Each new DV reservation pins the attribution's public ID, version, approval checksum and source checksum. Later compatible attribution versions do not rewrite or invalidate that earlier evidence. Payment/deduction payloads retain the reservation's original approval version; live claim/schedule calculations use the current approved reconciliation.

Each generated claim output captures its selected approved records before calculating amounts. A payable schedule reuses one reviewed projection for its rows, reconciliation and retained source evidence. An approval completed during generation cannot replace only its labels or version evidence. This is consistency of the selected attribution evidence; it does not claim a global point-in-time capture across all financial writers or replace the operational report/recovery gates.

## Boundaries and decisions

Migration `accounting/0019_reviewed_historical_claim_attribution.py` adds immutable proposal/decision records and one current approved pointer per source line in Finance. It does not rewrite any historical journal or move Finance data into the default store. Named actor/department permissions and Finance UAT mutation denial reuse Accounting controls; payee selection reads the existing department-scoped Finance Setup registry.

The current claim representation is one original claim per complete liability credit. Historical applications may settle part of that claim, but each selected application line belongs wholly to one claim. Consolidated credits and payment lines split across several claims still need explicit allocation support; this workflow must not be used to assign their whole amount to one invoice. Consolidated multi-claim DVs remain next work rather than an assumed capability.

Generated voucher/remittance sources and their reversal ancestry are excluded from retrospective adoption here. Their default-store payment workflows must be reconciled before historical links could become a second settlement route. Original manual, adjusting and opening credits are supported when they satisfy the source/chronology controls. An opening credit represents its documented opening amount; it does not invent the original invoice's pre-opening payment history.

Approval cannot infer whether a preparer omitted an unlinked payment. The screen requires an explicit complete-history confirmation and supporting reconciliation evidence; the reviewer must check those facts. Automatic checks reject duplicate attribution, inconsistent office/fund/account, impossible dated consumption, incompatible subsidiary evidence and unproved restoring credits. This is not an automatic migration or evidence-free conversion of legacy balances.

## Validation record

Final selected checks pass. Earlier runs below retain the actual sequence; they do not replace the final evidence or establish the full Finance/production gate.

- Initial focused SQLite: five tests, 9.798 seconds; four passed and the completed DV scenario failed only its final expectation that an unauthorized foreign user would get 404. The existing permission gate correctly returned 403. The test now separately checks permission denial and a permitted foreign-office user's 404.
- Corrected focused SQLite: five tests PASS, 10.241 seconds. Includes actual HTTP submission/review, self-review and UAT denial, original-source immutability, old payments, exact reversals, projected subsidiary/control amounts, reviewed corrections and retained CSV files.
- Initial native MySQL: 29 tests PASS, 36.260 seconds, including attribution/payment exclusivity, duplicate native recognition and amendment-versus-reservation races. This preceded the final approval-version provenance and ordinary-reversal-label preservation changes.
- Preliminary broad SQLite run was deliberately stopped during setup to complete reservation approval-version provenance before final regression. It is **NOT RUN - OUT OF SCOPE for final validation**, not a pass or an environment failure.
- PASS — main focused SQLite: 5 tests, 11.119 seconds; `.tmp/historical-claims-sqlite-verified.log`. Includes the final retained-approval-version and deduction/payment scenario.
- PASS — main MySQL 8.4.11: 41 tests, 70.842 seconds; `.tmp/historical-claims-native-verified.log`. Includes three attribution races and three existing claim-reservation races, plus claim/DV, dated-reservation, earlier-accrual and deduction-correction regression.
- PASS — broad Finance SQLite: 596 discovered / 581 passed / 15 native-only skips, 654.448 seconds; `.tmp/historical-claims-regression-final.log`. These three main runs preceded the final report-version repair. Skips are not passes.
- FAIL - CAUSED BY CURRENT WORK — two deterministic approval-during-generation tests reproduced mismatched payee/version evidence in 0.977 seconds; `.tmp/historical-projection-before.log`. The repair captures the approved records once for each output.
- PASS — final affected SQLite: 172 discovered / 171 passed / 1 native-only skips, 136.659 seconds; `.venv/Scripts/python.exe .tmp/earlier_sqlite.py accounting.test_claim_projection accounting.test_claim_attributions accounting.test_payable_claims accounting.test_dated_claim_reservations vouchers.test_prior_payables reporting`; `.tmp/historical-projection-regression.log`. Covers all reporting plus the affected claim/attribution/DV paths after the last repair.
- PASS — final native: 17 tests, 26.140 seconds; `.venv/Scripts/python.exe .tmp/prior_native_authority.py accounting.test_claim_projection accounting.test_claim_attributions vouchers.test_prior_payables`; `.tmp/historical-projection-native.log`.
- PASS — `manage.py check`, `manage.py makemigrations --check --dry-run`, changed-file compilation, `git diff --check` and local document links.
- NOT RUN - OUT OF SCOPE — repeat of the five-app broad suite after the final read-only projection plumbing change (the affected reporting/claim regression above covers it), whole-project/non-Finance and full native suites, live eGAPS, production migration, browser/human usability and exact local form/operational/LGU acceptance. This implements a financial workflow, not a release gate.
- All runners ended; the owned MySQL fixture was stopped and port 33308 closed. User `db.sqlite3` SHA256 remains `C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C`; the unrelated policy-concurrency draft is preserved.

Relevant commands and scope: `.venv/Scripts/python.exe .tmp/earlier_sqlite.py accounting.test_claim_attributions vouchers.test_prior_payables.PriorPayableDVTests.test_historical_attribution_http_to_dv_payment_and_claim_export`; native `.venv/Scripts/python.exe .tmp/prior_native_authority.py accounting.test_claim_attributions accounting.test_claim_attribution_concurrency vouchers.test_prior_payables accounting.test_payable_claims accounting.test_dated_claim_reservations accounting.test_payable_reservations_concurrency vouchers.test_deduction_corrections vouchers.test_earlier_accruals`; broader `manage.py test vouchers accounting finance reporting departments --noinput` because claim identity, capacity, reversals, reporting and selection forms change together. Ignored wrappers use isolated test logs and the [fresh native runner](FINANCE_NATIVE_TESTING.md).

## Next work

Complete consolidated claim allocation/settlement and remaining post-instrument/remitted-withholding corrections, then the preserved M01/M03 functions and inventory, ordinary-office, exact-output, usability/WFH and operational/LGU gates in [the authoritative order](FINANCE_MODERNIZATION_PRIORITIES.md). eGAPS remains disconnected and untouched; no user-store migration is performed by this work.
