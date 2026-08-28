# Voucher and Disbursement Workbench

GRAND's Voucher Workbench is the implemented shadow vertical slice for part of F5–F8 in the [complete-cycle roadmap](FINANCE_ROADMAP.md). It is a shared, permission-aware disbursement case and does not copy a voucher between departmental databases. Budget, Accounting, and Treasury act on the same case and append evidence to one history.

The initial controlled route is:

`Budget OBR/allocation → Accounting DV → wet signatures → Accounting validation/JEV reference → Treasury checks → Accounting bank advice → Treasury release`

The workbench is intentionally locked to shadow comparison mode until the LGU's Budget, Accounting, Treasury, and COA Audit Team validate local rules and blank/redacted forms. It does not replace the current authoritative process merely because the software route completes.

Its current entry point is intentionally provisional. A complete-cycle GRAND case will originate from a valid requesting-office transaction and authoritative appropriation/allotment/obligation lineage, not from a free-standing Budget voucher case.

## Database and app boundaries

GRAND uses one configured database so departments share stable users, departments, and references. Each Django app owns separate tables and permissions:

- `finance_*` stores governed master data, signatories, numbering, and workbook versions;
- `vouchers_*` stores disbursement cases, OBRs, DVs, checks, advice, release, and append-only events;
- `tracepoint_*` stores physical custody and may link only a `PacketItem` reference to a voucher;
- `records_*` retains approved official outputs; shadow voucher outputs cannot be filed as official records;
- future `mpdo_*` tables may use shared platform identities without receiving finance access.

Development uses SQLite. Production uses the database configured by the production settings, currently MySQL. A separate database per department is neither required nor recommended for this workflow.

## Governed setup

Accounting prepares and separately approves an effective-dated Finance Setup release before Budget can open a case. Configure selectable values rather than asking transaction users to retype them:

1. Add transaction types, funds, responsibility centers, account/expenditure classifications, tax/deduction rules, document requirements, and bank/payment accounts as stable code-and-label items.
2. Add suppliers, individual or employee payees, agencies, and their validity-dated authorized check claimants. Do not store banking credentials or unnecessary identity-document numbers.
3. Add validity-dated signatory names, titles, role codes, and acting assignments. An emergency change is a new governed version; previously generated vouchers retain their snapshots.
4. Add fiscal-year sequences for at least `obr` and `disbursement-voucher`. Issued values are recorded and never silently reused.
5. Upload and preflight the controlled DV workbook, submit the release, obtain a different Accounting approver, and activate it after readiness passes.

Budget case and DV forms read choices only from the pinned active release. The case stores the selected party plus a display snapshot, so later spelling, title, claimant, or signatory changes do not rewrite historical evidence.

## Permissions

Financial authority is explicit. Department assignment or platform superuser status alone is insufficient.

| Responsibility | Permission |
|---|---|
| View workbench | `vouchers.view_voucher_workbench` |
| Open Budget cases | `vouchers.initiate_budget_case` |
| Certify OBR/allocation | `vouchers.certify_budget_obligation` |
| Prepare/correct DV | `vouchers.prepare_disbursement_voucher` |
| Track wet signatures | `vouchers.track_wet_signatures` |
| Link TracePoint item | `vouchers.link_tracepoint_custody` |
| Validate DV/JEV reference | `vouchers.validate_accounting_voucher` |
| Issue and submit checks | `vouchers.issue_payment_instruments` |
| Finalize bank advice | `vouchers.finalize_bank_advice` |
| Release advised checks | `vouchers.release_payment_instruments` |
| Cancel/replace checks | `vouchers.manage_payment_exceptions` |
| Return same case | `vouchers.return_voucher_case` |
| View full event history | `vouchers.view_voucher_audit` |
| Approve emergency override | `vouchers.approve_control_overrides` |

The DV preparer cannot validate the same voucher. A staffing emergency requires a reasoned override approved by a different explicitly authorized employee. The override is single-use and remains in the audit data.

### Department workspaces and role provisioning

The Voucher Workbench keeps one case and one URL while shaping the queue for the employee's assigned office:

- Budget sees cases awaiting OBR certification and can follow cases already forwarded;
- Accounting sees DV preparation, wet-signature, validation, JEV-posting, and bank-advice work;
- Treasury sees check preparation, replacement, and release work;
- read-only UAT viewers can preview each office queue without receiving action permissions.

Provision the curated permission groups after migrations:

```powershell
python manage.py configure_finance_roles
python manage.py configure_finance_roles --uat-viewer teppy
```

The second command requires the named employee to have an assigned department. It grants read-only access to Finance Setup, Voucher Workbench and its audit history, Accounting, and ledger reports. It does not grant any workflow action.

Department membership determines presentation, not authority. The named permission groups remain the action boundary, preserving maker-checker separation even when employees share an office.

### Admin and guided setup boundary

Budget, Accounting, and Treasury users do not configure the normalized workflow models shown in the database. Voucher cases, OBR lines, DVs, deductions, document checks, signature tasks, validations, posting requests, checks, advice items, number issues, outputs, and audit events are created by workflow services.

Django Admin exposes only read-only voucher support evidence, read-only finance release/audit evidence, and the tightly governed workflow-exemption editor. Routine configuration belongs in Finance Setup Center and Accounting Setup, where validation and approval rules cannot be bypassed through generic model CRUD.

## Operating workflow

1. Budget selects the requesting office, approved supplier/payee, transaction type, and particulars, then certifies a pilot OBR against referenced budget sources. Budget formulation, approved appropriations, AROs, RAAO/equivalent balances, and authoritative over-obligation prevention are outside this release.
2. Accounting prepares the DV from the same case. The gross amount must equal the certified OBR amount in the pilot rule; deductions produce the net payable.
3. GRAND snapshots ordered, currently effective signatories. Staff record return of the actual wet-signed paper; GRAND does not claim that the clerk's entry is a digital signature. The current route does not yet make official printing, packet assembly, or TracePoint activation mandatory states.
4. A different Accounting validator accepts the voucher and creates a checksum-backed posting request. Accounting then materializes balanced GRAND journal lines, submits the entry, and an independently authorized poster posts it before the case moves to Treasury.
5. Treasury registers one or more physical checks. Active checks must exactly reconcile to the DV net before advice.
6. Accounting finalizes an immutable advice batch for one bank account. Treasury may release only advised checks to an active authorized claimant.
7. Cancellation preserves the spoiled number and sends the same case back for replacement. Correction returns retain the DV number and earlier signature rounds.

Every consequential service uses a database transaction, row lock, expected state version, and idempotency key. Duplicate submissions return the recorded result; stale pages must reload.

## Complete-cycle integration target

F3–F6 will refactor the workbench boundary without discarding its shared-case, audit, numbering, correction, and maker-checker controls:

1. A requesting office initiates an approved transaction variant and supplies the references it owns.
2. Budget selects the exact fiscal year, fund, office, PPA/project/activity, object/account, appropriation, and released allotment; certification creates an immutable obligation movement in the authoritative registry.
3. Procurement, delivery/acceptance, payroll, claim, or other locally applicable evidence makes a payable eligible for Accounting intake.
4. Accounting prepares one or more valid DVs against the obligation/payable lineage. The data model must support partial, progress, consolidated, final, adjustment, and liquidation relationships only where LGU evidence approves them.
5. GRAND freezes an explicit official print version, assembles/links the TracePoint packet, records required wet-signature checkpoints, and invalidates obsolete signing copies after a material correction.
6. Accounting recognition/payment postings and Treasury actions continue on the same case lineage while retaining separate financial states and permissions.

The role-shaped UI remains: employees receive a My Work queue and the phase panel relevant to their office, while authorized users can follow the complete timeline. The product should not force users through legacy module menus or expose every phase's edit controls on one all-powerful screen.

## Outputs, Records, and custody

The pinned, preflighted DV workbook can generate a shadow XLSX containing a reproducible input snapshot and SHA-256 checksum. Each regeneration is a new immutable output version. F6 must add explicit Ready to print, Printed, Awaiting wet signatures, Signed packet returned, Superseded, and Reprinted evidence. Exact official ARO, ALOBS/ORS/OBR, DV, advice, register, receipt, and check layouts require blank/redacted approved samples before their mapping can be certified. Direct check printing is deferred until bank-form, form-stock, custody, and printer-alignment validation.

TracePoint may be linked by its item reference when the employee can already see the physical packet. Voucher amounts are never copied into TracePoint, and physical receipt never advances the financial workflow automatically.

Only an output explicitly promoted through a future formal official-use decision may be filed into Records. Shadow comparison outputs remain downloadable from Voucher Workbench but are rejected by the Records source boundary.

## Current deliberate limits

- no budget formulation, opening-balance import, or authoritative remaining-balance calculation;
- no approved appropriation versions, Allotment Release Orders, or RAAO/equivalent obligation movement ledger;
- one OBR per voucher, with the service/model supporting multiple allocation lines;
- standalone GRAND journal materialization and maker-checker posting are implemented, while opening balances, authoritative legacy-ledger import, and full production reconciliation remain outside this release;
- check registration, cancellation, replacement, advice, and release controls, but no direct check printing;
- no legacy production-data import and no signature images;
- no official-use switch before documented local validation and shadow reconciliation.
