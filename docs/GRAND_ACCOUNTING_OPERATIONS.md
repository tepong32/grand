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

## Operator workflow

1. In **Accounting → Setup**, add an open period, fund, optional responsibility centers, and at least two posting accounts.
2. Create a journal from **Accounting → New journal entry**.
3. Add debit and credit lines. GRAND explains missing or invalid values next to the affected field.
4. Confirm the live balance card shows equal non-zero debits and credits.
5. Submit the draft. The entry becomes read-only for the preparer.
6. A different authorized poster reviews it, then either returns it with a correction reason or posts it.
7. Posted lines appear in the general ledger and trial balance and cannot be edited. Corrections will use a future adjusting/reversal entry workflow.
8. Close a period only after its drafts and submitted entries are cleared. Closed periods reject new postings.

Master records used by journals are archived instead of deleted. Codes and names already used in history cannot be silently redefined.

## Excel templates

GRAND's existing Finance Setup Center already accepts macro-free `.xlsx` versions, validates controlled mappings and print areas, rejects external links/risky formulas, fingerprints the workbook and mapping, and produces synthetic previews. The planned Template Studio will add point-and-click cell/range selection, repeating-row mapping, change-impact comparison, approval, activation, and rollback so non-technical template managers can update forms without code changes.

## Current implementation boundary

This first native slice covers setup, manual journal CRUD, submit/return/post controls, audit evidence, general ledger, and trial balance. Voucher-to-ledger posting, reversals, subsidiary ledgers, closing entries, financial statements, and the visual Template Studio remain subsequent phases. Historical eGAPS migration is optional and will be designed only if separately authorized.
