# Ordinary OBR, journal and ledger output comparison

Checkpoint: 2026-10-16, Asia/Singapore. Application source is accepted primary
v0.7.172 / `32ab04669da05b868f6c8b8ff37e0f71b3805555`. This is local synthetic
engineering evidence, not new financial functionality, another release or LGU
acceptance. No application, permission, posting, schema or CI source changed.

## What this adds

The existing [ordinary cross-office replay](FINANCE_CROSS_OFFICE_OUTPUT_REPLAY.md)
already checks the eight report workbooks and Treasury's three-stage payment and
bank-advice exports. The [partial-settlement replay](FINANCE_PARTIAL_PAYMENT_OUTPUT_REPLAY.md)
already checks returns and replacement. Those are reused, not reimplemented.

This checkpoint compares the same service-created ordinary transaction with four
additional clerk-facing CSV outputs and the Accounting ledger screen. It verifies
original source identities, dates, amounts, retained bytes and office access. The
source chain remains approved appropriation → released allotment → certified OBR →
reviewed payable → signed synthetic DV → independent recognition posting → issued/
acknowledged/released synthetic cheque → independent payment posting → reconciled
bank statement. All people, evidence, signing and physical acts are synthetic.

## Evidence table

| Working output | Source and period evidence | Actual reconciled result |
| --- | --- | --- |
| Budget certified OBR registry CSV | One movement; exact certified OBR number, date and checksum agree with the case's authoritative obligation | 1,000 obligation effect; zero unobligated balance |
| Accounting posted journal register CSV | Three unique original journal UUIDs: opening 2026-08-01, recognition 2026-08-25, payment 2026-10-16 | 3,900 debit and 3,900 credit movements |
| Accounting general-ledger CSV and screen | Seven posted lines, same three journal UUIDs; every displayed source UUID/date/account/debit/credit/running balance equals its exported row | 3,900 debit/credit movements; final bank normal balance 1,100 |
| Accounting trial-balance CSV | Five account rows plus a distinct total row; the total is not counted again as an account | 3,900 debit and credit totals |
| Existing governed Budget reports | FY2026 coverage; separate output ending 2026-08-19 excludes the August 20 OBR | 1,000 annual obligation and expense; earlier cut-off obligation zero |
| Existing governed ledger/trial-balance workbooks | FY2026, same three source journals and seven financial lines | Same 3,900 movements and bank balance 1,100 |
| Existing payable/withholding and Treasury outputs | Retain the before-payment payable workbook and original instrument/advice/release evidence | Gross 1,000 = net release 900 + withholding 100; payable 900 before payment, zero after |

The direct ledger/trial exports cover the acting office's complete posted ledger;
they have no selected report-period input. The comparison above is valid because
all three fixture journals fall within FY2026. Do not generalize agreement in this
fixture to arbitrary lifetime-versus-period comparisons, or interpret debit/credit
movement totals as expenditure. Payment does not duplicate the 1,000 expense.

Each new CSV's SHA256 equals its HTTP header, retained archive bytes and manifest;
manifest byte length and exporting actor agree. Budget's registry archive pointer
comes from its actual audit event; it does not expose Accounting's relative-path
header. Nine retained report runs are copied with their original checksums: the
existing eight downloaded workbooks plus the earlier Budget cut-off output.

Budget, Requesting and Treasury fixture users each receive HTTP 403 for Accounting
ledger export. No additional grants were supplied to make those checks pass.
The original ordinary replay also checks permitted report downloads and denies
Budget access to the Accounting trial-balance report. These are specific tested
actors/routes, not proof of every role/office combination.

## Validation and reproducibility

The isolated probe subclasses the existing `VoucherWorkflowTests`, calls its
`test_authoritative_budget_to_reconciled_treasury_report_replay`, then verifies the
additional HTTP/CSV/screen outputs. It does not mock report amounts or create a
second financial route. Probe: `.tmp/ordinary_register_probe.py`.

```powershell
$env:GRAND_REGISTER_PROBE_ID='ordinary-register-sqlite-final-20261016'
& 'C:/Users/Administrator/Desktop/GH/grand/.venv/Scripts/python.exe' -B -X utf8 .tmp/intake_primary_sqlite.py ordinary_register_probe.OrdinaryRegisterProbe.test_sources_and_registers --verbosity 2
$env:GRAND_REGISTER_PROBE_ID='ordinary-register-native-final-20261016'
& 'C:/Users/Administrator/Desktop/GH/grand/.venv/Scripts/python.exe' -B -X utf8 .tmp/intake_primary_native.py ordinary_register_probe.OrdinaryRegisterProbe.test_sources_and_registers --verbosity 2
```

Fresh identifiers are required for a new run: retained evidence directories are
never overwritten.
Use the documented Python 3.11 environment and existing isolated wrappers/native
fixture. Probe and raw artifacts are ignored local evidence; preserve them for a
new conversation in this workspace. They are not a new committed CI test identity.

- **FAIL — CAUSED BY CURRENT WORK (verifier assumption):** first SQLite probe,
  one case / 9.809s, exit 1. It required a relative-path header absent from the
  Budget endpoint. Source inspection confirmed the retained audit pointer; the
  probe now follows that contract. No application repair was justified.
  Raw failed log: `.tmp/ordinary-register-probe-sqlite.log`; both stores destroyed.
- **PASS:** corrected SQLite probe, one case / 9.456s, zero skips, exit 0;
  both stores destroyed. Raw log `.tmp/ordinary-register-final-sqlite.log`;
  CSVs, nine XLSX files and source/control facts retained in
  `.tmp/ordinary-register-sqlite-final-20261016/`.
- **PASS:** native MySQL probe, one case / 14.867s, zero skips, exit 0;
  both stores destroyed. Raw log `.tmp/ordinary-register-final-native.log`;
  CSVs, nine XLSX files and source/control facts retained in
  `.tmp/ordinary-register-native-final-20261016/`. Expected HTTP 403 checks log
  `PermissionDenied`; these are asserted denials, not failed test cases.
- **PASS:** `.tmp/verify_ordinary_register.py` verifies all eight retained CSVs,
  eighteen workbooks, source/control facts, cross-backend financial controls,
  terminal summaries and both-store cleanup. It records source/log/artifact hashes
  in `.tmp/ordinary-register-acceptance-20261016.json`. Both operator database
  hashes equal their retained baselines. Owned MySQL fixture shutdown requested
  only after the native process returned exit 0.
- **NOT RUN — OUT OF SCOPE:** another complete project suite or remote CI for this
  evidence-only check; application/test/CI sources are unchanged. Accepted primary
  [38618885804](https://github.com/tepong32/grand/actions/runs/38618885804) is separate:
  all nineteen jobs PASS, native 2,547 / zero skips; SQLite 2,348 / 199 native skips.
- **NOT RUN — OUT OF SCOPE:** browser/physical/printer/statutory/LGU acceptance.
  HTTP render/export agreement is not normal-browser file-save or accepted layout.

## Assessment and next work

No production defect was reproduced by these comparisons. Missing-header behavior
was a verifier error, not a financial integrity finding. Required official-output
fidelity and ordinary LGU acceptance remain **HIGH open completion gaps**; the
fixture cannot close them. Historical CI timeout evidence remains retained; current
accepted candidate and primary runs passed after the bounded whole-class partition
repair. Runtime variability remains a risk, not a current failed required gate.

GO for this bounded two-backend source/register comparison and further isolated
work. **Production NO-GO.** Update the [required-output map](FINANCE_REQUIRED_OUTPUT_MAP.md)
and [finite remaining-task list](FINANCE_REMAINING_WORK_2026-10-14.md) rather than
repeating this ordinary or partial-settlement replay again. Next required work must
name an outstanding output field/source/layout requirement or ordinary workflow
gap and its evidence. Earmark capacity, Form 1 numerical/statutory authority and
manual local acceptance stay unknown/deferred where not established.
