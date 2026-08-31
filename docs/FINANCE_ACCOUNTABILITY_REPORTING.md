# Finance accountability reporting

Status: **F9.1 implemented synthetic control; local form, signatory, routing, and reference-output acceptance remain required**.

This slice extends GRAND's governed reporting workspace with Finance-specific datasets, retained control evidence, source drill-through, reproduction receipts, conservative editable starters, and portable TraceSync archives. It does not declare a DBM/COA recommendation to be the LGU's accepted official form.

## Starter reports

- **Quarterly Budget Accountability Schedule** shows cumulative authorized appropriation, released allotment, reserve/deferral, executable allotment, certified obligation, unreleased appropriation, and unobligated allotment through the selected period end. It is an LBAc Form No. 2-equivalent working layout pending confirmation of the exact locally applicable form.
- **Posted Trial Balance** groups posted JEV lines by fund and account, shows debit, credit, and net balances, and requires exact debit/credit agreement. Its native layout remains a controlled working starter until Accounting accepts the applicable schedule.

Both starters use plain report/template fields that an authorized non-developer can revise through the existing reporting administration. A revised official layout must still follow template versioning, preflight, review, activation, and regression checks; this slice does not silently overwrite an approved template.

## Applicability boundary

Each report definition records one of three plain-language positions:

- **Departmental** — an internal management output, not represented as a statutory form;
- **Candidate reference** — informed by a COA, DBM, BIR, or other reference but awaiting local confirmation;
- **Locally confirmed** — authority and the local acceptance decision are both recorded.

Candidate reports may be generated and reviewed as controlled working outputs, but cannot be approved as official. Promotion to locally confirmed requires the authority reference and a local acceptance note. A run generated before that promotion remains a candidate run; regenerating under the confirmed definition prevents retroactive relabelling.

## Guided workflow and controls

1. Budget or Accounting chooses a report and covered period in the familiar Reporting workspace.
2. GRAND pins the definition, applicability, parameters, template version, and layout/signatory fields used for that run.
3. The Finance dataset is generated only from authorized/posting records for the selected department and period.
4. GRAND stores the rendered-data snapshot, control totals, freshness, source count, and separate SHA-256 values for the output, dataset, and control evidence.
5. The preparer reconciles the visible controls and follows source links to the authoritative appropriation, allotment, obligation, or posted JEV record.
6. A separate reviewer may review the run. A control exception blocks review; a candidate applicability position or pilot template blocks official approval.
7. Authorized users download the main output, the control/source CSV, and the deterministic JSON reproduction receipt.

The floating **?** help window contains separate Budget and Accounting instructions on the relevant pages. Progress belongs to the individual user only, is not assigned to a predecessor or copied to a successor, and does not alter the report's approval state.

## Modification allowance

Before approval, users do not edit retained report evidence in place. Correct the authorized source transaction through its governed pre-issuance/pre-posting route where allowed, or use its reasoned successor/correction route once locked; then generate a new report run. Definition and template changes create governed current configurations without rewriting already generated snapshots. This keeps the existing allowance to correct vouchers and related records before voucher/check issuance while preventing a report from becoming a back door around transaction controls.

## Export, reproduction, and safekeeping

Each output can be accompanied by:

- a CSV containing control totals and immutable source identities, references, dates, amounts, checksums, and permitted drill-through paths; and
- a JSON reproduction receipt containing the pinned definition/template snapshots, period/parameters, all three report checksums, control result, source snapshots, and reproduction key.

These files use the existing `GRAND_EXPORT_ROOT` department/user/category/year/month hierarchy. The generated manifest/checksum files allow the entire root folder to be copied or synchronized by TraceSync without users reorganizing individual exports.

## Acceptance still required

Before official use, named Budget, Accounting, Treasury, management, records, and audit-coordination owners must confirm the current applicable DBM/COA/BIR issuances; exact form names and layouts; fund and period treatment; column equations; cut-off and adjustment treatment; signatories; copies, recipients, and deadlines; source-record access; retention classification; and at least one signed reference package whose totals are reproduced exactly from accepted opening balances and pilot transactions.

F9.2 supplies the first [Finance operational report catalog](FINANCE_OPERATIONAL_REPORT_CATALOG.md): Budget-versus-posted-actual, posted general ledger, payable/withholding schedules, and a Treasury disbursement register. F9.3 adds [governed statement composition and explained measures](FINANCE_STATEMENT_CONTROLS.md). F9 remains open for statement notes, current accepted tax/BIR outputs, signed-reference reproduction, exact locally accepted forms, and named-office acceptance. F10 remains responsible for exact official-form mapping and non-developer template promotion.
