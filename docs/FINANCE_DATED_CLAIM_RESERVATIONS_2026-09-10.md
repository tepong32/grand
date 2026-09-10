# Dated prior-payable reservations

M02 prerequisite discovered while inspecting historical claim attribution. Development branch: `codex/finance-dated-claim-reservations`, based on pushed v0.7.82 `2cd0177633855fb212eb33e7856d09a39de5d369`. Finance production remains **NO-GO**. This repair does not implement historical attribution or complete M02.

## Reproduced problem and resulting behavior

| Scenario | Previous reservation behavior | Repaired behavior |
|---|---|---|
| Claim 1,000; application 800 on September 4; actual reversal September 8; request 700 effective September 5 | Accepted using the ending balance of 1,000 | Rejected: only 200 is available on September 5 |
| Same application on September 6, reversed September 8; request 700 effective September 5 | Accepted because both starting and ending balances are 1,000 | Rejected because the intervening posted application leaves only 200 |
| Request 200 during that interval | Accepted | Still accepted when no other hold uses it |
| Request 1,000 on September 8 after releasing the earlier unused reservation | Accepted | Accepted using the actual restored balance |
| Existing active reservation has posted applications | Remaining amount held plus amount applied | Whole reservation remains committed once; its own applications do not count twice |
| DV validation asks for more than dated capacity | Could advance a no-deduction DV, or create a deduction request that later fails dated posting | Rejects before validation, request creation or stage advancement; corrected actual later-date validation can proceed |

The existing original-credit lock still serializes reservation and journal posting. `_capacity(..., as_of=...)` checks the requested day and every subsequent posted movement, including temporary shortfalls before a later restoration. Active reservations commit their whole amount; only movements outside those reservations change the remaining dated capacity. Released reservations contribute their actual posted applications. Existing same-key recovery retains its evidence and does not allocate another hold.

This is a reservation eligibility check over current posted evidence. It does not rewrite previous approvals, change posting dates, infer historical invoice allocation, or promise that every future manual posting will preserve every earlier validation assumption. Posting-time dated checks remain required. Existing active holds are conservatively committed for this calculation; no historical release/activation timeline is invented from current status. Daily grouping follows the existing journal date granularity.

## Source-to-output coverage

The new DV scenario uses a 1,500 original claim, a posted 1,000 reduction on August 22 and its exact reversal on August 28. Both deduction and no-deduction validations dated August 25 must fail without Finance reservation/default-store workflow effects. A no-deduction validation dated August 29 then follows the real instrument/advice/release/posting path. Its claim CSV must show `1500.00,1000.00,500.00`. The active reservation's consumption must leave capacity 500 rather than subtracting the payment twice.

## Validation

All final selected checks pass. All test runners ended; the owned MySQL fixture was stopped and port 33308 is closed.

- Reproduction: `.venv/Scripts/python.exe .tmp/earlier_sqlite.py accounting.test_dated_claim_reservations` — three assertion failures in 0.299 seconds on unchanged runtime code, proving each overly permissive reservation. These are deliberate regression reproductions, not dismissed environmental failures. Log: `.tmp/dated-claims-before.log`.
- PASS — `.venv/Scripts/python.exe .tmp/earlier_sqlite.py accounting.test_dated_claim_reservations vouchers.test_prior_payables.PriorPayableDVTests.test_validation_cannot_spend_capacity_restored_after_its_date`: four tests, 8.448 seconds; `.tmp/dated-claims-focused.log`.
- PASS — `.venv/Scripts/python.exe .tmp/prior_native_authority.py accounting.test_dated_claim_reservations accounting.test_payable_reservations_concurrency accounting.test_payable_claim_concurrency vouchers.test_prior_payables vouchers.test_earlier_accruals vouchers.test_deduction_corrections`: 30 tests, 26.580 seconds; `.tmp/dated-claims-native.log`. Fresh MySQL 8.4.11, separate default/Finance schemas; includes five existing native reservation/application/identity races.
- PASS — `.venv/Scripts/python.exe manage.py test vouchers accounting finance reporting departments --noinput`: 588 discovered / 576 passed / 12 native-only skips, 309.604 seconds; `.tmp/dated-claims-regression.log`. This scope covers the shared claim-capacity service used by validation, financial posting, corrections and outputs. Skipped native cases are not counted as passes; the selected five claim/reservation races passed in the separate MySQL run.
- PASS — `manage.py check`, `manage.py makemigrations --check --dry-run`, changed-file compilation, `git diff --check` and local document-link checks. No schema migration is required.
- NOT RUN - OUT OF SCOPE — whole-project/non-Finance suites, full native suite, eGAPS reconnection, exact local forms and human/operational acceptance. This is a bounded claim-eligibility repair, not a major completion or production gate.
- User `db.sqlite3` SHA256 remains `C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C`; unrelated `accounting/test_policy_concurrency.py` is preserved. No eGAPS access or user-store migration.

The ignored local wrappers use the repository's documented test runners and separate log directories. They read only credentials for the owned disposable MySQL fixture, not eGAPS. See [native testing](FINANCE_NATIVE_TESTING.md).

## Next financial work

Historical attribution still needs independently reviewed evidence over unchanged original credits **and prior applications**, plus matching DV selection, source checksums, individual-claim exports and subsidiary/control reporting. A label-only overlay would overstate unpaid capacity. Current journal and subsidiary structures identify one original claim per credit; consolidated historical credits and multi-claim DVs need an explicit supported allocation model. Existing subsidiary identities, reversals and active generated payment cycles must be reconciled rather than silently adopted into a second settlement path.

Continue these M02 functions and the preserved M01/M03, inventory, ordinary-office, exact-output, usability/WFH and operational/LGU gates in [the authoritative order](FINANCE_MODERNIZATION_PRIORITIES.md). eGAPS remains disconnected and untouched. No user-store migration is authorized by this test work.
