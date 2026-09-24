# Required office outputs: source map and unresolved acceptance

Status: development checkpoint, 2026-09-21. This is a source-to-output map for the
Finance foundation gate, not an accepted inventory of mandatory LGU forms.

The user reports that the office scarcely uses eGAPS reports because they are not
user-friendly. Actual usage therefore cannot establish the required output set.
Keep eGAPS closed and untouched. Begin with the work being performed and retain
explicit local confirmation of names, periods, recipients, signatures and layouts.

## Working map

| Office / work | Existing GRAND source and output | Boundary still requiring confirmation |
| --- | --- | --- |
| Budget proposal and historical comparison | Annual version and planning-context exports in `budget/urls.py`; authoritative original/adjusted amounts and explicit estimates | Local proposal form, treatment of expenditure categories, required columns and signatures. Posted expenses are not certified total expenditures. |
| Budget release planning and authority | Quarterly plan, appropriation authorization, allotment register and individual ARO exports | Exact quarterly/ARO presentation and local certification. A quarterly plan is not spending authority. Earmark capacity basis remains unconfirmed. |
| Budget obligations and accountability | OBR registry/control register; Reporting Budget accountability and Budget versus Posted Actual datasets | Exact local accountability form and period; ambiguous PPA/account mappings require source resolution. The candidate schedule is not an accepted LBAc form. |
| Accounting posting and ledger work | Journal control register, ledger and trial-balance exports; governed posted general-ledger/trial-balance report starters | Required journal/JEV presentation, grouping, signatures and full signed output reproduction. Source CSV alone does not establish form parity. |
| Accounting liabilities and advances | Payable claim/subsidiary controls and officer advance exports; posted payable/withholding schedules | Local ageing, attribution, classifications and signatories. An advance dataset exists, but no advance starter is currently seeded in `reporting/presets.py`. |
| Accounting financial statements | Four governed statement starters and retained statement-note bundle | Approved local fields, comparatives, source completeness, notes, signatures and exact accepted package reproduction. Existing calculation controls do not establish local acceptance. |
| Accounting bank reconciliation | Reconciliation register and individual reconciliation export | Accepted statement layout, reconciling-item classification, cut-offs and witness/signature requirements. |
| Treasury payments | Payment instrument/disbursement report starter, case payment register, bank advice and cash-position exports | Local issue/release reporting, cancelled/replaced instruments, bank presentation and official output layout. Issuance is not proof of physical release. |
| Treasury receipts and deposits | Collection register/export and retained source copies through collection views | Accepted receipt and collection/deposit reporting package, groupings, accountable-form coverage and signatures. Collection data is not currently a Reporting dataset; source copies are not proof of accepted official forms. |
| Withholding/remittances across offices | Governed tax detail/summary starters; remittance and retained tax-filing evidence exports | Current applicable tax forms/certificates, actual filing requirements and agency acceptance. A liability schedule or retained evidence export is not a filing acknowledgement. |

Implementation evidence was inspected in `reporting/presets.py`,
`reporting/datasets.py`, and Budget, Accounting, vouchers and Reporting URL modules.
These are existing routes, not a claim that every output was regenerated in this
checkpoint. The [operational catalog](FINANCE_OPERATIONAL_REPORT_CATALOG.md)
describes dataset controls; [accountability reporting](FINANCE_ACCOUNTABILITY_REPORTING.md)
and [local form acceptance](FINANCE_LOCAL_FORM_ACCEPTANCE.md) own approval and
fidelity requirements. This map does not duplicate their specifications.

## Evidence and next bounded work

The [official source register](finance-discovery/OFFICIAL_SOURCE_REGISTER.md)
remains the source trail. The DBM [Local Budget Circular index](https://www.dbm.gov.ph/index.php/dbm-issuances/local-budget-circulars)
identifies LBC 152 and the 2023 Budget Operations Manual. This establishes a
publication reference, not current local acceptance of a particular output.
Attempts to open the indexed 2024 reprint and the COA 2002-003 page on 2026-09-21
returned 404 and 403 respectively; their full contents were not newly verified.
Barangay-only source results were excluded from municipal requirements.

Next, replay one ordinary source chain into the existing Budget, Accounting and
Treasury working outputs, comparing source identities, covered dates and totals.
Then resolve exact local fields/layouts against accepted evidence when available.
Keep the 31-form candidate catalog separate from confirmed required outputs.
No new report family is authorized merely by its presence in that catalog.
The subsequent [actuals source audit](FINANCE_BUDGET_ACTUALS_SOURCE_AUDIT.md) verifies
FY2027 DBM LBM 94 Annex D/E and informs the [proposal-actuals contract](FINANCE_BUDGET_ACTUALS_CONTRACT.md).
These references establish national form content and distinct certification roles;
they do not establish LGU usage, printer fidelity or acceptance of a GRAND output.

## Report-run retrieval repair

The reporting workspace previously counted all matching runs but displayed only
the first 100, with no route to older matches. It now pages 50 matching runs at a
time with deterministic creation-time/ID ordering, visible range and total, and
filter-preserving previous/next links. Existing own/department visibility and
full filtered register export remain the governing scope.

Validation results are recorded in CONTINUE.md. This read-only register change
adds no persistence schema, financial posting or report approval behavior.
FG-06 and the complete Finance foundation gate remain open.

The [ordinary cross-office output replay](FINANCE_CROSS_OFFICE_OUTPUT_REPLAY.md)
now exercises one linked Budget/Accounting/Treasury transaction through working
outputs and retained downloads. This is bounded synthetic evidence; it does not
close required-form fidelity or ordinary LGU workflow acceptance.

[Treasury stage-specific export evidence](FINANCE_TREASURY_OUTPUT_REHEARSAL.md)
now verifies bank acknowledgement, recorded release/pending posting and completed
posting against retained sources and archives. It preserves the distinction
between a reserved JEV number and actual posting, without claiming local form acceptance.
