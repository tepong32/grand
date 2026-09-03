# Finance controlled DV printing and custody

This guide describes the implemented F6.1 synthetic control. It turns a prepared GRAND Disbursement Voucher into one checksum-pinned signing file, records what was actually printed, creates its physical TracePoint route, blocks signature recording until that packet exists, and preserves a reasoned successor when copies must be replaced.

It does **not** declare GRAND's starter workbook an official local form or complete the parent F6 acceptance gate. The enabled LGU still has to compare a redacted output with its accepted blank form and actual paper route, confirm current authority and local applicability, test its printer/form stock, and record acceptance in Finance Setup.

## Official-source basis and acceptance boundary

- [COA Circular No. 81-155](https://www.coa.gov.ph/wpfd_file/coa-circular-no-81-155-february-23-1981/) describes consolidation and adoption of one common voucher form for national and local agencies and covered bodies.
- [COA Circular No. 92-389](https://www.coa.gov.ph/wpfd_file/coa-circular-no-92-389-november-3-1992/) restates that circular with modifications and identifies Disbursement Voucher General Form No. 5(A).
- [COA Circular No. 2023-004](https://www.coa.gov.ph/wpfd_file/coa-circular-no-2023-004-june-14-2023/) prescribes updated documentary requirements for common government transactions.
- COA's published [fundamental and general disbursement requirements](https://coa.gov.ph/wp-content/uploads/ABC-Help/DRCGT/DRCGT.1.htm) include lawful appropriation/allotment, proper approval, legality, and sufficient supporting documents.

These public sources are review evidence, not a substitute for the LGU's current form, local procedure, records-retention decision, signatory authority, COA Audit Team/authorized-official clarification where required, or written acceptance. Finance Setup therefore labels each workbook `Editable starter`, `Pilot comparison`, or `Locally accepted`. A locally accepted version cannot pass model validation without a reviewed authority reference and comparison/acceptance reference.

## Editable starter workbook

An authorized Finance template manager can choose **Build editable DV starter** from a draft configuration release. The ordinary form asks for the LGU/office name, familiar form title/reference, A4/Letter/Legal paper, portrait/landscape orientation, particulars-row count, default copies, signature labels, and footer note.

The generated macro-free `.xlsx` uses a conservative government-form layout, a fixed print area, and the required GRAND named cells/range. Its `Read Me First` sheet tells a non-technical editor which text and layout may be changed and warns that preflight is only technical compatibility. The edited workbook must be uploaded as a new governed template version, preflighted, compared, approved, and activated through the existing Finance Setup release process.

## Operator sequence

1. **Prepare the DV.** GRAND pins the active setup, form version, obligation relationship, calculated amounts, documents, signatory snapshots, and current signature round.
2. **Prepare signing copy.** GRAND generates a checksum-backed XLSX, assigns print version 1, and retains the exact bytes plus sibling JSON manifest under `department/user/finance-dv-signing-copies/year/month` in `GRAND_EXPORT_ROOT`.
3. **Record printed copies.** The operator records actual copy count and the printer, tray, paper/form stock, duplex/margin setting, and useful quality note. Server time and operator are retained.
4. **Assemble the packet.** The operator records document/page counts, confidentiality, and an assembly note. GRAND creates a TracePoint packet/item when none is linked and adds the configured signatory-office checkpoints. TracePoint stores case/DV/version/checksum/custody references but not voucher monetary values.
5. **Record returned wet signatures.** Only the current print version and signature round may receive returned-signature records. GRAND does not treat the clerk's record as a digital signature. The last current task marks the packet returned and opens Accounting validation.

The persistent, non-modal `?` panel exposes the same steps only to employees in the current department who hold the applicable role permission. A person's checkmarks are private tutorial progress—not task completion, approval, performance evidence, or history transferred to a successor.

## Guided queue and portable custody register

The shared Finance Queue can isolate controlled-paper work without adding another workflow state: **Needs a current signing copy**, **Signing file ready to print**, **Printed; packet not assembled**, **Packet circulating for signatures**, or **Signed packet returned**. These choices combine safely with stage, transaction type, requesting office, role attention, and plain search. Unknown controlled-choice values fail closed.

**Export DV custody history** uses the exact visible role scope and filters, then emits every retained print version for each matching case. Rows include DV/template controls, gross/deductions/net, form status and checksum, print version/status, plain next action, output/archive checksum, actual copies/printer/note, TracePoint packet/item and counted contents, checkpoint count, signature-round results, returned-packet evidence, supersession lineage/reason, and case state version. Spreadsheet formula prefixes in text are neutralized while amounts remain numeric.

The exact bytes and sibling manifest are archived under `department/user/finance-dv-custody-register/year/month`, and an append-only Finance audit event records the filters, case count, history-row count, path, and SHA-256—even for an empty result. This register is custody oversight evidence; it is not a wet signature, approval, payment authority, or local-form acceptance.

## Modification and reprint rules

- Before check/payment-instrument issuance, an authorized user may correct permitted non-financial DV dates/signatories through the existing reasoned amendment route; related signing outputs and active print jobs are superseded and a new round is required.
- A damaged, smudged, misaligned, incomplete, or otherwise wrong signing copy may be replaced while the case is awaiting signatures. A specific reason is mandatory.
- The old output and print job remain stored as `Superseded — do not sign`; pending tasks in its signature round are declined, and printed physical copies must be marked **DO NOT SIGN** and controlled under the local disposal/records procedure.
- The successor receives a new output checksum, print version, and—when printing/circulation had begun—a new signature round. Printing and packet assembly must be recorded again.
- A current signature return is blocked until the current job is `Awaiting wet signatures` and linked to its TracePoint item.
- Accounting validation is blocked until the current controlled print job is `Signed packet returned`.
- Once a check/payment instrument exists, the convenience edit/reprint route closes; use the coordinated return, supersession, reversal, cancellation, or replacement process instead.

## Local F6 acceptance checklist

- Record the exact accepted blank DV/form and its checksum or controlled reference.
- Record current authority, scope/effectivity, approving office, and any written local or audit clarification.
- Compare a fully redacted ordinary-supplier case side by side: fields, labels, certifications, signatures, copies, paper, margins, print area, overflow, and form stock.
- Walk the actual packet through every configured receiving office and acting/absence route; reconcile TracePoint events to the paper log.
- Test a normal return, refused/missing signature, damaged-copy reprint, non-financial correction, and obsolete-copy control.
- Confirm the portable export folder and sibling manifests survive a whole-folder copy to another computer and that access/backup/retention controls are suitable for financial data.
- Obtain named Budget, Accounting, Treasury, requesting-office, Records/IT, and authorized local acceptance for the enabled scope.

Until those checks pass, use the feature only as an implemented synthetic control and pilot comparison—not as an official-use declaration.
