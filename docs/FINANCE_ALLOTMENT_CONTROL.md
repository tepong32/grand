# GRAND Finance allotment release control (F4.1)

## Purpose and authority boundary

F4.1 turns an immutable, operationally authorized appropriation schedule into a controlled allotment-movement ledger. It does not create appropriation, obligation, payable, cash, or accounting authority by itself. Only a posted allotment order changes balances; draft, returned, and submitted records do not.

The design follows the budget-execution and accountability concepts in DBM Local Budget Circular No. 152 and the [BOM for LGUs, 2023 Edition](https://www.dbm.gov.ph/wp-content/uploads/Issuances/2023/Local-Budget-Circular/BOM-for-LGUs-2023-Edition-%282024-Reprinted%29-For-Posting-in-DBM-Website.pdf). The [DBM Local Budget Circular register](https://www.dbm.gov.ph/index.php/local-budget-circulars) identifies LBC No. 152 as the prescribed 2023 LGU manual. Account/classification interoperability remains aligned to the COA Revised Chart of Accounts for LGUs and its [COA Circular No. 2016-004 conversion/reporting guidance](https://www.coa.gov.ph/wpfd_file/coa-circular-no-2016-004-september-30-2016/).

Those are official references, not proof that a GRAND screen or CSV is an accepted local form. Before official use, the LGU must confirm the current form title/number, blank template, signatories, copies, page geometry, submission route, and any regional/local instructions. GRAND exports therefore say `controlled schedule export` rather than `official DBM/COA form`.

## Implemented workflow

1. A preparer chooses one authorized annual, supplemental, or reenacted appropriation and creates a draft ARO/equivalent record.
2. The header records order number/type, release/effectivity dates, authority and evidence references, purpose, signed control total, and optional posted-order correction lineage.
3. Schedule rows may select only the exact immutable authorized appropriation lines. The order type constrains valid movements: release, release reduction, reserve/withholding, reserve release, deferral, deferral release, return, or cancellation.
4. Submission requires at least one line and a zero difference between signed and computed totals. GRAND locks affected appropriation lines and recomputes cumulative balances.
5. A different authorized officer posts after recording an independent evidence/control-total review basis. Posting creates append-only movements and a deterministic SHA-256 schedule checksum.
6. A posted order and its movements are immutable. Later correction uses a linked adjustment, return, or cancellation order; the original remains reconstructible.

## Balance rules

For each authorized appropriation line:

- `released = sum(release effects)`; release, later release, and authorized adjustment-in increase it; reduction, return, and cancellation decrease it;
- `reserved` and `deferred` are separate sub-balances; each placement increases only its own bucket and only its matching release/lift may decrease that bucket;
- `held/deferred = reserved + deferred`;
- `unreleased = authorized appropriation - released`;
- `executable allotment = released - held/deferred`.

Posting is rejected when released allotment would exceed the authorized appropriation or fall below zero, a reserve/deferral would exceed released allotment, or a release/lift would reduce held balances below zero. The posting transaction locks the affected authorized schedule rows so two reviewers cannot validly consume the same remaining balance in parallel.

F4.2 now subtracts certified obligation movements from executable allotment to produce unobligated balances. Allotment posting also refuses any later reserve, deferral, return, cancellation, or reduction that would push executable allotment below obligations already certified; see [Finance obligation control](FINANCE_OBLIGATION_CONTROL.md).

## Modification allowance

- Draft and returned headers and schedule rows may be edited by an authorized preparer; every saved action has audit evidence.
- Submission makes the order read-only while an independent reviewer decides it.
- Return reopens governed editing and requires a specific reason.
- Posting permanently closes direct editing. Correction requires a linked movement order and reviewed authority.
- This is stricter than the later DV/check convenience-edit window: no voucher or check state can authorize rewriting a posted allotment ledger movement.

## Roles and Internal How-Tos

- `Budget Review and Consolidation Officer` can view control balances and prepare allotment orders.
- `Budget Appropriation Authorizer` can view and independently post/return allotment orders.
- `Finance UAT Viewer` can inspect the workspace without transaction authority.
- The floating `?` window includes **Prepare and post allotment releases**. Its private checkmarks only help the current user remember guide steps; they are not transaction status, performance evidence, approval, or inherited job history.

Run `python manage.py configure_finance_roles` after migration to refresh curated role permissions. Run `python manage.py seed_internal_howtos` to add the new department-specific guide where it does not already exist.

## Export and safekeeping

A posted order exports CSV with authority and allotment checksums, classifications, signed movement effects, and current authorized/released/held/unreleased/executable balances. The exact downloaded bytes are also archived under:

`GRAND_EXPORT_ROOT/<department>/<user>/finance-allotment-releases/<year>/<month>/`

The adjacent manifest records SHA-256, size, exporting identity, department, and source lineage. TraceSync can synchronize or copy the one configured root without a second export step. Preserve the whole tree and manifests; this portable archive complements controlled records and tested backups.

## Synthetic acceptance checks

- unapproved and merely approved proposal versions cannot be selected;
- order classifications can come only from the linked immutable appropriation snapshot;
- signed and computed control totals agree exactly;
- self-posting, over-release, excess reserve/deferral, over-reduction, and cross-department access fail;
- posted order/movement mutation fails and linked corrections retain original history;
- repeated posting cannot create duplicate movements;
- CSV bytes and the TraceSync-ready archived artifact share the recorded checksum;
- certified obligations constrain later allotment changes, and accepted ALOBS/ORS/OBR and RAAO equivalents must still reconcile to signed references before official use.
