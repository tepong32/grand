# Finance payable and withholding subsidiary controls

This guide documents the F7.2 synthetic control slice. GRAND now explains mapped payable and deduction control-account balances through posted claimant/payee and withholding detail, records immutable reconciliation evidence, and exports portable schedules. It does not declare a CSV to be an official COA or locally accepted form.

## What is implemented

- A voucher-generated JEV line using a payable mapping carries the governed Finance Party code and payee name as its subsidiary identity.
- A voucher-generated JEV line using a deduction mapping carries the configured deduction code and description.
- Subsidiary amounts exactly mirror their associated journal line and remain immutable with it.
- A governed reversal creates the exact opposite subsidiary movement while retaining the original identity and reversal lineage.
- The Accounting workspace compares GL and subsidiary credit-minus-debit balances separately by cut-off date, fund, category, and mapped control account.
- Missing detail is visible. A manual, opening, or adjusting posting to a configured control account does not receive an invented payee or deduction row; it remains an unexplained reconciliation difference until reviewed.
- Authorized Accounting reviewers may record a dated result snapshot. Balanced and exceptional runs both retain the preparer, rows, absolute difference, SHA-256 checksum, and audit event.

## Familiar operating flow

1. Configure the payable and deduction source codes to the reviewed posting accounts in Finance/Accounting setup.
2. Review and post the governed voucher JEV through the normal maker-checker route.
3. Open **Accounting → Subsidiary controls**, select the same cut-off used for the GL review, and compare each fund/control pair.
4. Investigate a difference at its journal source. Correct a posted error through a separately reviewed reversal or adjustment; never add a balancing subsidiary row.
5. Record the result when the comparison evidence is ready. Recording an exception proves the check happened; it does not mark the exception resolved.
6. Export the payable schedule, withholding schedule, and recorded reconciliation when portable review evidence is needed.

The floating `?` guide presents these steps only to the current department and applicable Accounting role. Its private checkmarks are reading progress—not transaction status, approval, performance evidence, or inherited work history.

## Modification and correction boundary

The earlier payable/voucher modification allowance remains unchanged: permitted users can make reasoned corrections while the governed case is in its allowed pre-issuance state. Once a DV or payment instrument closes that convenience window, corrections follow the coordinated successor, return, cancellation/replacement, reversal, or adjustment route.

F7.2 adds no way to rewrite posted journal or subsidiary facts. If the payee, deduction, mapping, or amount was wrong:

- correct the source while it is still editable and recreate the unposted generated JEV; or
- after posting, prepare a linked reversing/adjusting entry under independent review.

## Portable exports

Browser downloads are archived byte-for-byte under the configured `GRAND_EXPORT_ROOT` using the established department/user/category/year/month tree. Each artifact has an adjacent JSON manifest with its SHA-256, size, exporter, department, time, and source metadata. Copy or synchronize the whole root with TraceSync so artifacts remain beside their manifests.

The export contract is deliberately plain CSV with stable labels and readable codes. It is a human-editable interchange starting point for local review, not executable logic and not an automatically accepted statutory schedule.

## COA/DBM and local acceptance boundary

The [initial official-source register](finance-discovery/OFFICIAL_SOURCE_REGISTER.md) remains the evidence index for COA/DBM issuances, LGU accounting materials, forms, documentary requirements, and applicability questions. F7.2 implements internal-control concepts and reconstructible subsidiary evidence; it does not infer that a public national template, account title, signatory route, or effectivity rule applies unchanged to this LGU.

Before official use, local Finance owners still need to confirm:

- the exact control-account mappings and payee/deduction classifications by enabled transaction type;
- treatment of opening balances, prior accruals, remittances, cancellations, replacements, and year-end items;
- locally accepted schedule columns, numbering, signatories, frequency, cut-off, paper/file format, and retention;
- redacted replay against completed local cases and independent GL-to-subsidiary totals; and
- whether the exported CSV is supporting data for an accepted form or itself an approved schedule.

## Verification checklist

- A supplier recognition creates expense/allocation, payable, and deduction JEV lines that balance.
- The payable and withholding control lines carry the expected stable subsidiary identity and amount.
- Repeating materialization does not duplicate the JEV or subsidiary rows.
- A posted reversal produces equal opposite subsidiary movements.
- A mapped GL control line without subsidiary detail creates a visible difference.
- A recorded reconciliation cannot be edited or deleted and its exported checksum matches its snapshot.
- Department/permission boundaries apply to the workspace, action, schedules, and archived exports.
