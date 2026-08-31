# Finance statement composition and explained measures

Status: **F9.3 implemented synthetic controls; signed local-statement comparison, notes, exact official forms, named-office acceptance, and the parent F9 exit gate remain open**.

F9.3 turns posted Accounting entries into two reproducible management statements without treating a balanced screen as an accepted financial statement:

- Management Statement of Financial Position uses posted balances through the selected end date.
- Management Statement of Financial Performance uses posted revenue and expense during the selected period.
- Each run pins its report definition, template, statement-mapping snapshot, checksum, covered period, rows, totals, freshness, and source JEV evidence.
- Each reporting-workspace measure names its definition, period, freshness, control result, and retained run.

## Governed, human-maintained mapping

Accounting receives broad controlled starters: Assets, Liabilities, Equity, Revenue, and Expenses. They are intentionally readable and select all active posting accounts of the relevant type. A starter is suitable for management comparison and training, not an automatic assertion that GRAND reproduces the municipality's accepted signed statement.

The maintenance route is `Reports → Statement mappings`:

1. Compare the current signed local statements and reviewed COA/GAM guidance with the starter.
2. Create an editable successor and define readable sections and lines.
3. Select all accounts of a type or a controlled list of account codes.
4. Resolve exact-coverage errors: every active posting account for that statement must be assigned once.
5. Record the reviewed authority and local acceptance evidence.
6. Submit to a different authorized reviewer.
7. Activate only after independent review. Activated and superseded versions, line rules, evidence, checksums, and events are immutable.

New runs use the active mapping; if no locally active version exists, they visibly use the controlled starter. Prior runs retain their pinned older snapshot, so adopting a successor never rewrites history.

## Equations and exception gates

Financial position reports all mapped asset, liability, and equity lines plus a separately visible **unclosed operating result** derived as posted revenue less posted expense. The control equation is:

`Assets = Liabilities + Equity + unclosed operating result`

This avoids hiding current-period activity before governed closing entries are posted. Financial performance reports mapped revenue and expense and derives the period surplus or deficit.

A statement run becomes a control exception when:

- the financial-position equation does not equal zero;
- a non-zero account is not mapped;
- an account is mapped more than once; or
- no governed starter or active mapping is available.

Control exceptions cannot advance through official report review. Users correct the underlying source through the applicable adjustment/reversal route or adopt a reviewed successor mapping, then generate a successor run. Generated rows and evidence are never edited.

## Internal guidance and exports

The Accounting Internal How-To is version 3 and covers statement mapping, equation review, exact coverage, source freshness, and drill-through. The mapping page also includes a `?` guide in a floating modal so users can read the procedure without leaving their current work.

Statement outputs, control-evidence exports, and reproduction receipts continue through the existing TraceSync-ready department/user/category archive. Copy or synchronize the complete export root, including sibling manifests, for safekeeping.

## Acceptance boundary

F9.3 does not claim that period close means statement acceptance. It also does not supply statement notes, current accepted BIR/tax outputs, signed-reference reproduction, exact paper layouts, or named Budget/Accounting/Treasury acceptance. Those remain explicit F9/F10 evidence and rollout work.
