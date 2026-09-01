# Finance fiscal-year and classification foundation

Status: **GRAND-implemented** F2.1 foundation. Local classifications, authority references, readiness evidence, fiscal calendars, and process-owner acceptance remain **Unresolved** until the named Budget, Accounting, Treasury, forms, and technical owners approve a synthetic year.

## Boundary and purpose

This slice establishes the governed dimensions that later appropriations, allotments, obligations, vouchers, JEVs, payments, and reports will reference. Canonical fiscal records live with Accounting in the separately routed `grand_finance` database. Core identities and approved Finance Setup releases remain in the default database.

The boundary deliberately uses stable numeric/UUID identities, display snapshots, release metadata, and SHA-256 checksums. It does not create a database foreign key from the Finance store to a department, employee, or setup release in the core store, and it has no eGAPS runtime dependency.

## Implemented records

- A typed fiscal year carries a stable UUID, calendar bounds, controlled business date, lifecycle, maker/checker identity snapshots, source-release evidence, and state version.
- Accounting periods link to the typed year while retaining the former integer year as a compatibility snapshot. Period 13 can be marked explicitly as an adjustment period.
- Funds, responsibility centers/offices, and ledger accounts now have stable UUIDs and effective-dated classification details. Existing used records remain protected from historical redefinition.
- Funding sources are fiscal-year and optional-fund scoped, with source kind and authority reference.
- MFO, program, PPA, project, and activity records form a same-year hierarchy and may pin their responsible office and funding source.
- Five independent readiness records cover technical setup, Budget approval, Accounting approval, Treasury readiness, and form readiness. Each decision records evidence, actor snapshots, time, state version, and an append-only Accounting audit event.

Activation requires all five decisions and the automated structural checks. The checks require a period, funding source, program classification, active fund, and posting account. Treasury and form readiness remain human evidence decisions because their locally accepted bank, payment, custody, and template rules cannot be inferred safely.

## Guided setup workflow

1. A **Finance Configuration Manager** creates a fiscal year or adopts an approved Finance Setup release.
2. The manager links calendar periods, funds, offices, accounts, funding sources, and program classifications, then submits the year.
3. A different **Finance Configuration Approver** approves the fiscal-year definition. The preparer/submitter cannot self-approve.
4. Authorized reviewers record the authority or acceptance evidence for each readiness layer. A failed structural check cannot be approved.
5. The approver activates the year only after every layer passes. Active classifications and readiness evidence cannot be silently rewritten.

### Guided modification allowance

A configuration manager may use **Edit** to correct a governed fiscal-year/calendar/classification record while no disbursement voucher number and no check/payment instrument has been issued for the affected fiscal year. The form requires a reason, shows the control boundary, retains before/after snapshots in an append-only audit event, returns the fiscal year to Draft, and reopens the readiness layers affected by the field group. The manager then resubmits and a different approver repeats the applicable decisions.

The current conservative gate treats any numbered DV in the fiscal-year/release scope as the end of in-place setup modification, even if the check has not yet been released. A check that was later cancelled still counts as issued. Once the gate closes, operators must use the applicable successor setup, case return, adjusting/reversing entry, voucher supersession, check cancellation/replacement, or later phase-specific correction workflow. Existing used journal masters retain their stricter no-redefinition rule.

F5 voucher-lineage integration now closes the former cross-store race with one permanent transaction-store issuance boundary per Finance office and fiscal year. Guided foundation edits and release adoption hold that row lock across the separately routed Finance-store amendment and final blocker recheck; an edit that moves a period or classification also locks and reopens both its original and proposed years. Budget certification, DV preparation, and physical-check registration take the same boundary **before** locking their voucher case; they then recheck that any adopted typed fiscal year is Active before new issuance. A concurrent DV/check issue therefore finishes first and blocks the edit, or the edit finishes first and the waiting issuance stops until independent readiness review and reactivation; it cannot slip between the final check and amendment commit. Later event-JEV numbering retains its ordinary sequence lock but does not take the setup boundary because the numbered DV has already closed in-place setup modification. The boundary is coordination evidence only—it does not authorize setup, issue a number, or replace the existing maker–checker and successor/reversal rules.

Run `python manage.py configure_finance_roles` after migration to create or refresh these curated roles and their explicit permissions. Superuser status alone does not grant Finance access.

## Existing setup and release adoption

Migration `accounting.0004` is additive. It assigns stable UUIDs to existing funds, offices, and accounts; creates one typed record for every legacy department/year found in Accounting periods; links those periods; and creates pending readiness layers. It does not delete, renumber, post, close, or reinterpret any journal.

The guided **Adopt / reconcile** action accepts only approved, scheduled, active, or superseded Finance Setup releases. It pins the release ID, code, version, and checksum, then copies supported governed categories into the isolated Finance database. Repeating the same adoption is idempotent. Account classifications without a valid `account_type` and `normal_balance`, or program classifications with an invalid `kind`, are skipped and identified in the result rather than guessed.

Supported release categories are `fund`, `responsibility_center`, `account_classification`, `funding_source`, `ppa_mfo`, and `project_activity`. Their `configuration` mappings may include:

| Category | Optional/required configuration keys |
| --- | --- |
| `fund` | `category` |
| `responsibility_center` | `office_id`, `office_code` |
| `account_classification` | `account_type` and `normal_balance` required; `government_account_code`, `subsidiary_reference_type` optional |
| `funding_source` | `kind`, `fund_code`, `authority_reference` |
| `ppa_mfo`, `project_activity` | `kind`, `parent_code`, `funding_source_code`, `responsibility_center_code`, `authority_reference` |

Rollback is a normal code/database rollback before use. Once later transactions reference a classification, correction must use a successor setup/version rather than destructive reversal of this migration.

## Synthetic acceptance script

Use synthetic codes only and retain the screenshots/decision notes in the evidence register.

1. Create FY 2027 with January 1–December 31 bounds and a business date inside that range.
2. Add one regular period and one adjustment period; confirm an out-of-range period is rejected.
3. Add a fund, office, posting account, funding source, MFO, and child activity. Confirm cross-department and cross-year selections are rejected.
4. Submit as the configuration manager. Confirm that the same person cannot approve the year.
5. Attempt Budget readiness without a funding source/PPA and confirm it is blocked. Complete the missing records and record synthetic evidence for all five layers.
6. Activate the year, edit one classification before any DV/check issuance, and confirm GRAND records before/after/reason evidence, returns the year to Draft, and reopens affected readiness. Reapprove it.
7. Issue a synthetic DV, then confirm the guided modification window closes and directs the operator to successor/return/reversal/cancellation/replacement workflows. Confirm the setup amendment and number issue use the same office/fiscal-year issuance-boundary record.
8. Adopt the same approved synthetic setup release twice and confirm no duplicate dimensions are created and the checksum is unchanged.
9. Run Accounting tests, the full test suite, `manage.py check`, and `makemigrations --check --dry-run`.

Passing this script proves the software controls only. It does not approve an official fiscal year, establish opening balances, or satisfy the F2 exit gate. F2.2 supplies staged opening-balance and control-total intake next.
