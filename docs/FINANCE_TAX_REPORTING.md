# Governed tax withholding capture and reporting

Status: **F9.5 implemented synthetic control; local tax applicability, official forms, filing, remittance acceptance, and named-office sign-off remain open.**

This slice connects a locally governed tax rule to the disbursement voucher, immutable Accounting posting evidence, controlled source schedules, and portable exports. It is intended to remove repeated encoding and make each reported amount explainable. It does not determine which tax applies to a real transaction and it does not file, issue, or transmit a BIR form.

## Authority boundary

The starter wording is informed by public BIR primary sources, including the official [BIR Form 1601-EQ guidelines](https://efps.bir.gov.ph/efps-war/EFPSWeb_war/forms2018Version/1601EQ/1601eq_guidelines.html), [BIR Form 1601-EQ PDF](https://bir-cdn.bir.gov.ph/local/pdf/1601-EQ%20January%202019%20ENCS%20final.pdf), [BIR Form 1604-E PDF](https://bir-cdn.bir.gov.ph/local/pdf/1604E%20Jan%202018%20ENCS%20Final2.pdf), [BIR Form 1604-E eFPS guidance](https://efps.bir.gov.ph/efps-war/EFPSWeb_war/help/help1604e.html), and [BIR Form 1600-PT guidance](https://efps.bir.gov.ph/efps-war/EFPSWeb_war/help/f1600pt_guidelines.html).

Those sources are research evidence only. Before a rule becomes transaction-ready, the local Finance owner must confirm the taxpayer/LGU scope, transaction coverage, ATC, tax base, rate, rounding, form codes, reporting date, effectivity, filing channel, deadline, signatories, and retained acceptance evidence. GRAND stores that decision; it does not make it.

## Plain-language setup

An authorized Finance Setup preparer uses **Add tax rule** rather than editing configuration JSON. Each version records:

- a tax family and readable code/title;
- ATC, percentage, and ordinary-language description of the taxable base;
- return/remittance and optional certificate form codes;
- whether the report period follows Accounting posting, voucher date, or actual payment release;
- cent rounding and whether the payee tax identifier is mandatory;
- reviewed authority, effectivity, version, local applicability, and retained local decision evidence.

A researched starter remains **Candidate**. A reporting-enabled candidate blocks configuration-release submission so transaction users cannot mistake it for accepted policy. The ordinary successor/version and independent release review controls still apply.

## Guided voucher capture and modification allowance

The DV preparation page accepts multiple deduction rows without forcing the user into a technical screen. The preparer selects a locally confirmed rule, enters the reviewed tax base, and enters the withholding amount. GRAND then verifies the configured percentage and cent rounding, prevents duplicate use of the same governed rule, and requires the governed payee identity/TIN when configured.

Each governed row pins the rule version, rule snapshot/checksum, payee name and tax-identifier snapshot, tax base, and a contextual evidence checksum. Generic locally approved deductions can continue without being misrepresented as reporting-enabled tax lines.

While no check or other payment instrument has been issued and no JEV has posted, the case may use its guided return/correction route and the DV may be prepared again with a recorded reason. Once a JEV has posted or an instrument has been issued, tax and voucher evidence is not editable in place. Correction must use the governed adjustment/reversal and, when applicable, coordinated cancellation and replacement process so the original evidence survives.

## Accounting evidence and reports

The governed tax snapshot moves with the withholding subsidiary posting. A posted reversal retains the same source evidence and appears as a negative report line at the reversal date; the original is never rewritten.

Accounting receives two human-modifiable report starters:

- **Governed Tax Withholding Detail / Certificate Source** lists reporting date, event, JEV, case/DV, payee/TIN, tax family, form codes, ATC, base, rate, amount, rule version, reporting basis, and authority.
- **Governed Tax Return / Remittance Summary** groups that evidence by return/remittance form, tax family, ATC, and rate, with payee/line counts, tax base, and withholding total.

Before a run can advance to review, the dataset checks the pinned rule checksum, contextual evidence checksum, base-times-rate formula, configured rounding, posted ledger amount, and required TIN. It also exposes payment-release-basis items that are not yet reportable. Source drill-through leads to the posted JEV.

These reports are controlled working schedules. They are not filed returns, issued certificates, e-filing integrations, deadline calculators, or official form reproductions. F9.6 can now link a homogeneous governed-tax remittance to independently reviewed external filing/payment references and, preferably, the exact approved and reconciled GRAND return/remittance summary; a reasoned external checksummed schedule remains an advanced fallback. See [Finance governed tax remittance and filing evidence](FINANCE_TAX_REMITTANCE_EVIDENCE.md). That evidence record still does not perform filing or replace the external acknowledgement. An exact accepted layout must still pass the F10 template comparison/promotion controls and the parent F9/F11 field acceptance gates.

## Guidance, privacy, and export custody

The existing floating **?** window now explains tax-rule setup, multi-line DV deductions, pre-issue corrections, report selection, and the official-use boundary without leaving the current page. Guide checkmarks remain private learning aids; they are not work completion, competence, approval, or performance evidence and do not pass to a successor user.

Requesting-office transaction exports include tax amounts, base, codes, form references, and checksums but omit the full TIN. The Accounting tax-detail report may contain the TIN because its purpose requires authorized tax custody. Every downloaded report continues through the single GRAND export root using the department/user/category/year/month hierarchy and an adjacent checksum manifest. For safekeeping or TraceSync, copy or synchronize the complete root rather than moving isolated files.

## Remaining acceptance work

- confirm every current local tax rule and the actual responsible owner;
- compare the schedules with current accepted BIR/local returns, certificates, attachments, and remittance evidence;
- confirm TIN access, retention, redaction, export-custody, and backup rules;
- verify period/deadline treatment, amendments, zero returns, unusual payees, exceptions, and mixed-tax transactions;
- promote exact locally accepted templates and complete consecutive redacted field replay;
- retain named Accounting, Treasury, management, records/privacy, IT, and audit decisions through F11.
