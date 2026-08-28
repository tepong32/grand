# GRAND standalone accounting operations

GRAND Accounting is an independent finance subsystem. It does not connect to eGAPS and does not need eGAPS to be online, installed, licensed, or retained.

## Database deployment

Development uses `grand_finance.sqlite3` by default. Override it with `GRAND_FINANCE_SQLITE_PATH` when isolation or disposable test data is preferred.

Production requires a dedicated database and least-privilege GRAND service account:

- `FINANCE_DB_NAME`
- `FINANCE_DB_UN`
- `FINANCE_DB_PW`
- `FINANCE_DB_HOST`
- `FINANCE_DB_PORT`

No eGAPS address, service port, username, password, or database path belongs in GRAND configuration.

Run migrations for both stores during a controlled deployment:

```powershell
python manage.py migrate --database=default
python manage.py migrate --database=finance
```

The router places only `accounting` tables in `finance`. GRAND identities, departments, groups, and permissions remain in `default`. Accounting rows preserve numeric identity references and display-name snapshots rather than cross-database foreign keys.

## Role assignment

All access is explicit; platform-superuser status alone does not grant finance access.

- `view_accounting_workspace` — view the journal register and entry details.
- `manage_accounting_setup` — manage periods, funds, responsibility centers, and accounts; close periods.
- `prepare_journal_entries` — create and correct drafts, manage lines, submit, and discard drafts.
- `post_journal_entries` — independently review, return, and post submitted entries.
- `view_general_ledger` — view posted-ledger and trial-balance screens.

Assign permissions through an approved role/group procedure. The preparer and poster should be different people.

### Governed workflow exemptions

Strict maker-checker separation remains the default. When an approved staffing model genuinely requires combined duties, an authorized administrator may add a **Finance workflow exemption** in Django Admin for one named employee or one permission group/role. Each policy is limited to one department and one control, has effective dates and an active flag, requires a documented operational rationale, and cannot be deleted through Admin; deactivate or end-date it instead.

Available controls cover Finance Setup self-approval, Budget-certifier/DV preparation, DV-preparer validation, and JEV self-posting. An exemption never grants the underlying action permission and never crosses department boundaries. Every actual exempt action snapshots the policy ID, scope, rationale, validity, and authorizing administrator into the corresponding immutable Finance, Voucher, or Accounting audit event. One-case voucher overrides remain available for exceptional incidents where a reusable policy would be too broad.

## Operator workflow

1. In **Accounting → Setup**, add an open period, fund, optional responsibility centers, posting accounts, and controlled voucher posting mappings.
2. Create a journal from **Accounting → New journal entry**.
3. Add debit and credit lines. GRAND explains missing or invalid values next to the affected field.
4. Confirm the live balance card shows equal non-zero debits and credits.
5. Submit the draft. The entry becomes read-only for the preparer.
6. A different authorized poster reviews it, then either returns it with a correction reason or posts it.
7. Posted lines appear in the general ledger and trial balance and cannot be edited. An authorized preparer can prepare an exact reversing JEV with a mandatory reason and original-entry link; that reversal must pass the same independent submit-and-post workflow.
8. Close a period only after its drafts and submitted entries are cleared. Closed periods reject new postings.

For Voucher Workbench cases, Accounting validation creates an immutable, checksum-backed posting request in GRAND's core database. The Accounting workspace materializes that request into the separate GRAND finance database. The operation is idempotent: retrying opens the same JEV rather than creating a duplicate. After independent posting, a recoverable reconciliation step advances the same voucher case to Treasury. A posted source JEV blocks silent voucher rewrites.

### Date and signatory corrections before check issuance

The separate `amend_nonfinancial_voucher` permission allows an authorized Accounting user to correct the DV document date and choose one currently approved, date-valid person for every required signatory role. This remains available after JEV posting as long as no check— including a later-cancelled check—has ever been issued for the case.

The amendment keeps the same case and DV number, snapshots the unchanged gross/deductions/net/certified amounts, preserves the posted JEV, supersedes earlier generated DV workbooks, and creates a replacement wet-signature round. Earlier signature evidence remains in history. After the replacement round is completed, the case resumes the stage it occupied before the amendment. The replacement workbook uses the revised DV date and selected approval signatory.

This route does not change the JEV date, accounting period, fund, accounts, allocations, deductions, or amounts. Those are financial corrections and continue to require the accounting return/reversal workflow.

Master records used by journals are archived instead of deleted. Codes and names already used in history cannot be silently redefined.

## Excel templates

GRAND's existing Finance Setup Center already accepts macro-free `.xlsx` versions, validates controlled mappings and print areas, rejects external links/risky formulas, fingerprints the workbook and mapping, and produces synthetic previews. The planned Template Studio will add point-and-click cell/range selection, repeating-row mapping, change-impact comparison, approval, activation, and rollback so non-technical template managers can update forms without code changes.

## Current implementation boundary

The current native slice covers setup, manual and voucher-generated journals, controlled posting mappings, cross-database handoff/retry, submit/return/post controls, pre-check non-financial DV amendments, correction reversals, audit evidence, general ledger, and trial balance. Subsidiary ledgers, automated payment-side postings, closing entries, financial statements, and the visual Template Studio remain subsequent phases. Historical eGAPS migration is optional and will be designed only if separately authorized.
