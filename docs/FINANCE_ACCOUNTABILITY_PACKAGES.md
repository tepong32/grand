# Finance accountability-package profiles and assembly

Status: **F9.7 implemented synthetic control; actual accepted package contents, signed source outputs, filing acknowledgements, and named-office replay remain external acceptance evidence.**

F9.7 connects the approved outputs already produced by Budget, Accounting, Treasury, statement-note, signed-reference, and tax-filing workflows. It is not another report builder and it does not copy financial authority into a new module. An accountability package records which approved evidence formed one reviewed submission for one exact period, why it was selected, and how it can be reproduced.

## Human-modifiable package profiles

An authorized Finance Configuration Manager can describe a reusable package checklist using ordinary fields:

- a familiar package name and stable short code;
- plain-language purpose and employee instructions;
- the office responsible for each source;
- the evidence type: approved GRAND report, approved financial-statement notes, reconciled signed-reference comparison, or verified tax-filing evidence;
- the exact report definition or tax form code when applicable; and
- whether the item is required or optional.

Profiles cannot contain SQL, macros, scripts, formulas, or credentials. A different Finance Configuration Approver must review the profile before it becomes active. Submission pins the complete requirement recipe and SHA-256. An accepted profile is immutable; changes use a reasoned successor, which copies the prior checklist for readable editing while the accepted predecessor remains traceable.

The profile is a local control instrument, not a declaration that a public COA, DBM, BIR, ordinance, or memorandum applies automatically. Activation requires both a reviewed authority reference and a named local-acceptance record.

## Period-package workflow

1. An Accounting preparer chooses one active profile and an exact start/end period.
2. GRAND clones the accepted checklist into immutable package slots and pins the profile UUID, version, content, and checksum.
3. Each slot offers only currently eligible source evidence:
   - an approved official GRAND report for the selected definition, source office, and exact period, with complete output/dataset/control/reproduction hashes and any required reconciled control;
   - locally confirmed approved financial-statement notes for the exact period;
   - an independently reconciled zero-difference signed/redacted reference comparison for the exact report and period; or
   - independently verified tax-filing evidence for the Accounting/Treasury relationship, exact tax period, and form code.
4. Selecting evidence pins its UUID, employee-facing label, source facts, approval basis, and SHA-256.
5. Submission rechecks every current source, required slot, exact period, approved profile, and checksum before freezing the whole package.
6. A different Accounting reviewer approves or returns the package. Approval is blocked if the preparer or submitter attempts to review it or if any source has drifted or lost eligibility.

Approved and historically superseded packages remain reproducible if a legitimate successor later supersedes a source report, note set, comparison, filing record, or profile. A new draft cannot select superseded evidence.

## Modification, correction, reversal, and traceback

The correction boundary follows the meaning of the underlying event:

- **Draft or returned package:** replace a mistaken selection only with a plain-language reason. The former selection becomes an immutable superseded version linked to its successor.
- **Submitted package:** it is read-only. A reviewer must return it before the preparer can correct a selection.
- **Approved package:** never overwrite it. Create a reasoned successor package, which retains the predecessor UUID/checksum and copies the selected evidence for review. The predecessor remains the approved package until the successor is independently approved; only then is the predecessor marked superseded.
- **Financial error:** the package workflow does not reverse a JEV, obligation, remittance, check, or payment. Use the source module's governed return, cancellation, reversal, replacement, adjustment, or reopen route first; approve the corrected source; then select that evidence in the package successor.

Append-only profile and package events record actors, times, actions, reasons, source UUIDs, selection versions, predecessor/successor identities, and checksums. Package requirements, selections, events, approved snapshots, and superseded history cannot be deleted through the governed model APIs.

## Roles and department boundaries

- **Finance Configuration Manager:** prepares package profiles and successor recipes.
- **Finance Configuration Approver:** independently activates profiles.
- **Accounting DV Preparer:** assembles packages, replaces draft evidence with a reason, creates approved-package successors, and exports authorized packages.
- **Accounting Reviewer:** independently approves or returns packages and may export them.

The package is owned and viewed through the employee's assigned Accounting department. A configured slot may point to a source report owned by Budget or another named Finance office, but it exposes only approved package evidence selected through the governed profile. Direct report/source access remains subject to the source module's own permissions.

## TraceSync export

Approved or historically superseded packages export a deterministic JSON manifest beneath:

`department/user/finance-accountability-packages/year/month`

The manifest contains the pinned profile and package versions, period, every slot, source UUID and snapshot, selection lineage, source checksums, package/profile SHA-256 values, preparer/submitter/reviewer identities, approval time, and review note. The adjacent archive manifest records the exported bytes and relative path.

Copy or synchronize the complete `GRAND_EXPORT_ROOT` so accountability manifests remain beside the separately exported governed source reports and transaction evidence. F9.7 intentionally does not bypass source permissions by silently copying confidential report bodies, TIN-bearing schedules, signature images, or uploaded signed references into a second package file.

## Acceptance still required

Before claiming the parent F9 exit gate, the LGU must provide and accept:

- the actual package profiles and required/optional contents for each reporting obligation;
- current applicable COA, DBM, BIR, ordinance, memorandum, and local-procedure bases;
- exact accepted forms, layouts, signatories, copies, recipients, deadlines, and retention/custody rules;
- redacted signed reference schedules, statements, notes, tax forms, and external filing/payment acknowledgements;
- accepted opening balances and pilot transactions whose totals reproduce those references;
- complete package export/reproduction under the named offices' permissions; and
- named Budget, Accounting, Treasury, management, records, IT, and audit acceptance through the F11 field/cutover controls.

The software now enforces the assembly, modification, approval, audit, and reproduction contract. It does not fabricate the evidence needed to declare a statutory or local package accepted.
