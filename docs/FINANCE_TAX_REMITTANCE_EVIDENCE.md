# Governed tax remittance and filing evidence

Status: **F9.6 implemented synthetic control; actual filing, current deadlines/forms, and named-office acceptance remain external and open.**

This slice joins F9.5 tax-withholding evidence to F8.1 remittance execution. GRAND preserves which locally governed tax rule, return/remittance form, and ATC produced a remitted liability, then records independently reviewed references showing what users actually filed and paid outside GRAND. It does not log in to an agency portal, submit a return, calculate a deadline, or certify that a local filing was accepted.

## Evidence chain

1. A reporting-enabled tax rule must already be locally confirmed in Finance Setup and pinned to a posted voucher deduction.
2. Treasury selects the posted withholding balance. The allocation now retains the governed tax scope and rule checksum in addition to the subsidiary-balance checksum.
3. Submission, Accounting review, actual release, JEV creation, and posting continue through the existing F8.1 maker-checker route. The liability-reducing subsidiary movement retains the tax-remittance scope without being misreported as new withholding.
4. After actual release, Treasury records the form code, tax period, filing date, actual channel, filing/submission reference, payment-confirmation reference, and restricted evidence-custody reference.
5. The recommended source path offers only approved, control-reconciled GRAND tax return/remittance summaries using a locally confirmed definition and department-validated official template. The selected run must cover the exact tax period, contain only the filing's form, and reconcile to the batch total. GRAND copies its run identity, report/template snapshot, control checksums, reproduction key, and output SHA-256 automatically.
6. An advanced external-schedule fallback remains available for a locally accepted schedule outside GRAND. Treasury must record the reviewed schedule reference, its 64-character SHA-256, and a plain-language reason the approved GRAND summary was not used.
7. GRAND accepts one evidence package only when every active remittance allocation carries governed tax evidence and all allocations agree on one return/remittance form. Mixed or generic deductions remain in the generic remittance register.
8. A different Accounting reviewer verifies or returns the exact checksum-backed package. Verification means the recorded references were independently compared; it does not make GRAND the filing authority.

## Modification and amendment rules

- A Draft or Returned filing-evidence package can be corrected in place while audit events retain each save/submission/review action.
- Submission closes ordinary editing. Accounting can return it with specific correction instructions.
- Verified evidence is immutable. A later correction creates an explicitly Amended successor; the verified prior version becomes Superseded and remains reconstructible.
- Pre-upgrade F9.6 evidence retains checksum schema 1 and its original proof meaning. Saving a correctable legacy draft or creating an amended successor upgrades that record to schema 2, which covers the source-mode and report-lineage fields.
- The underlying remittance schedule still follows its stricter boundary: approval closes allocation editing, actual release cannot be repeated, and posted entries require reversal or adjustment rather than rewriting.

## Guidance, export, and privacy

The existing floating department-specific `?` guides explain the guided GRAND-report path, the exceptional external-schedule path, and the filing-evidence handoff without navigating away from the remittance. Private tutorial checkmarks remain learning aids only and are not filing, competence, performance, or approval evidence.

The remittance register includes tax family, form, ATC, rule checksum, and source checksum. Each filing-evidence version can also export a small CSV under `department/user/finance-tax-filings/year/month` in the single TraceSync-ready GRAND export root with its adjacent manifest. The export identifies whether the source was a GRAND report and, when applicable, its run, definition, and template version. Evidence references should point to the controlled local record or restricted packet; users should not paste passwords, portal credentials, or unnecessary taxpayer data into GRAND.

## Acceptance still required

Before official use, the local BIR/tax owner, Accounting, Treasury, and records/privacy owners must confirm current applicability, ATCs, form versions, period rules, deadlines, zero and amended returns, filing channels, authorized-agent-bank handling, proof-of-payment and acknowledgement evidence, TIN custody, retention, exact accepted layouts, and named-office redacted replay. These values remain human-governed because public guidance does not by itself prove the LGU's current accepted practice.
