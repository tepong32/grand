# Incoming cheque collections — work in progress

Included in the v0.7.108 development checkpoint; not master/production acceptance.
Full SQLite PASS: 1,362 discovered / 1,266 passed / 96 native-only skips, 689.398s,
exit 0. The local count includes two unrelated policy tests excluded from the checkpoint.
The later fee-input boundary test passes separately; final clearing entry-form presentation
is browser-verified. Native combined 50/50 and final source 2/2 pass. All runners ended;
owned MySQL and browser/server stopped. The operator DB remains unchanged.

The approved LGU return/redemption accounting reference has been requested and remains
unprovided. This blocks finalizing those ledger effects; keep the remaining lifecycle open.

Required scope confirmed by the user: cash, cheques and bank transfers. Continue
the complete cheque lifecycle; capture/deposit support alone is not completion.

## Current local implementation

Bank clearing is now being implemented as a separately retained proposal/decision
over the original posted cheque receipt and its whole posted deposit. Treasury records
the actual clearing date, bank reference and evidence location; Accounting independently
confirms or returns it. Reviewed withdrawal retains the decision and permits a new
version. Receipt/deposit correction shares the Treasury lock and requires resolution
of active clearing evidence first. Clearing neither creates another bank credit nor
changes the original collection/deposit journals. Officer cheque refunds remain blocked.

Migration vouchers/0033 adds clearing evidence in the default store only. No operator
database migration has been performed. Web entry/review and retained printable evidence
are under test; this does not complete dishonour, redemption or custody handling.

An ordinary or multi-charge receipt can retain the drawee bank, drawer/account
reference, number and issue date. Its identity is checked under the existing Treasury
department lock. A duplicate active receipt is rejected; a corrected source retains
its old evidence. Future-dated instruments are not treated as current collected money.
This does not yet provide a separate future-dated custody register.

Cheque deposit allocations must equal the entire receipt amount at capture, review
and materialization. Ordinary cash partial deposits retain their existing behavior.
Details, CSV and retained printable copies show cheque evidence, and explicitly avoid
claiming clearing from receipt/deposit posting. Capture adds no schema; the subsequent
clearing evidence uses vouchers/0033. Neither operation introduces a second ledger.

Officer cheque refunds are not yet accepted: treating an uncleared instrument like
cash would prematurely release the original officer's expense/refund capacity. Extend
that source route when clearing/disposition evidence is implemented, preserving the
original case-first locks, subsidiary and dated capacity. Do not silently record these
as cash or claim this blocked route as completed coverage.

## Outstanding lifecycle

Implement independently reviewed bank clearing and actual dishonour, dated return
effects, original cheque/receipt/deposit links, custody/notice evidence and governed
settlement. Preserve the original collections and deposits. An actual dishonour is
not a source-error correction; ordinary payer refunds and reversed incoming transfers
also remain separate functional work. Multiple instruments or mixed cash/cheque payment
on one receipt and required forms must be demonstrated before full collection parity.

## Authority reviewed

The [BLGF LTOM Book 2](https://blgf.gov.ph/wp-content/uploads/2022/10/LTOM-Book-2-E-Copy.pdf)
is the collection-procedure reference located on 2026-09-15. Full retrieval returned
403, so search excerpts are not sufficient authority for implementing its unseen rules.
The [COA dishonoured-cheque guidance](https://www.coa.gov.ph/wp-content/uploads/ABC-Help/Cash_Examination_Manual/lrrce1.6.1.htm)
separately addresses redemption and custody. Do not infer a local settlement method,
deadline, statutory account code or current amendment from generic source correction.
Verify applicable primary guidance before completing those accounting effects.

## Capture validation recovered on 2026-09-15

The earlier native 43-test run completed: PASS, 67.937 seconds. Final capture SQLite:
PASS, 43 discovered / 37 passed / six native-only skips, 39.615 seconds. Those runs
precede the clearing extension. Initial identity reproduction was invalidated by a
model import mismatch while new code was being loaded; it is not regression evidence.
The unchanged identity reproduction is included in the initial clearing native run.

Clearing focused SQLite PASS: three workflow/web/source tests, 5.873s, exit 0,
`.tmp/cheque-clearing-focused-sqlite.log`. Initial native: five clearing workflow/race
tests passed, and the duplicate-instrument test reproduced the issue-date bypass
(six tests, 12.929s, exit 1; `.tmp/cheque-clearing-initial-native.log`). Identity
comparison now derives bank/account/number from retained fields, preserving old
dated digests and recorded issue dates without treating date changes as new instruments.

Combined validation PASS via `.tmp/run_cheque_clearing.py sqlite|native`:
50 labels in `.tmp/cheque-clearing-labels.json`, covering the earlier 43 and identity,
four clearing/security/web/output scenarios and two new races. Logs:
`.tmp/cheque-clearing-final-sqlite.log`, `.tmp/cheque-clearing-final-native.log`.
SQLite: 42 passed / eight native-only skips (38.924s, exit 0). MySQL: all 50 passed,
including eight races (71.557s, exit 0). Final public-identity immutability and web/print
native tests: two passed (4.777s), `.tmp/cheque-clearing-final-source-native.log`.
The final entry-form wording/field presentation was checked in the browser after that
run launched. Full SQLite passed as recorded above in `.tmp/cheque-clearing-full-sqlite.log`.
System/migration-drift/compile
checks pass; operator DB
SHA256 remains the retained `C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C`.

Browser validation: synthetic isolated two-store fixture, desktop 1440px and narrow
390px. Independent review and reasoned withdrawal preserve the earlier decision.
An early clearing date is rejected with inputs retained; correcting it creates version
2. Narrow document width equals 390px. Shortened the withdrawal option and corrected
the clearing-specific introduction; field controls use the existing Bootstrap style.
Retained images: `output/playwright/cheque-clearing-desktop.png`,
`output/playwright/cheque-clearing-narrow.png`,
`output/playwright/cheque-clearing-form-narrow.png`. Fixture default-image 404s were
resolved by copying the two existing static fixture assets into its isolated media
directory; no application asset changed. Browser and its server are stopped.

### Earlier capture run setup (historical)

Focused SQLite session 57126 uses three direct capture/deposit/web tests. Native
session 93563 runs `.venv/Scripts/python.exe .tmp/run_cheque_capture.py native`
with 43 selected tests: the preceding 39 collection/bank/refund tests, three cheque
scenarios and one new duplicate-capture race. Output logs are
`.tmp/cheque-capture-sqlite.log` and `.tmp/cheque-capture-native.log`.
These runs were active at the preceding handoff. Native source predates the final CSV assertions
and existing-cheque checksum guard; repeat affected final-source tests after results.
Final SQLite session 69273 runs the same 43 labels via
`.venv/Scripts/python.exe .tmp/run_cheque_capture.py sqlite`; output is
`.tmp/cheque-capture-final-sqlite.log`. All three handles were confirmed live on the
last poll. System and migration-drift checks pass; operator DB hash is unchanged.
No operator database changes or eGAPS access are authorized by these tests.

See [continuation](../CONTINUE.md) and [delivery priorities](FINANCE_MODERNIZATION_PRIORITIES.md).
