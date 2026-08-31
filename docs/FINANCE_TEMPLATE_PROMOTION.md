# Finance visual template promotion and rollback

Status: **F10.1 implemented synthetic control; exact local form, printer, form-stock, overflow, and named-office acceptance remain required**.

This slice turns the existing native, mapped-XLSX, and exact-PDF renderers into a controlled non-developer promotion workflow. It does not declare a public COA, DBM, BIR, or another LGU's form to be locally accepted.

## Familiar editable starters

An authorized report-template preparer can create a new version using plain fields for headings, certification text, footer, document-control prefix, page size, orientation, margins, borders, repeating headers, logos, signatories, and output mode. A prescribed macro-free XLSX can retain its familiar formatting through named data/total/metadata areas. A prescribed PDF can retain its original pages through reviewed field coordinates.

Approved versions are never overwritten. Each revision is a separate numbered version, and every generated output remains pinned to the exact template snapshot and checksum it used.

## Controlled promotion

1. A preparer saves and, for XLSX/PDF, safely preflights a new inactive version.
2. A different authorized user approves it for controlled preview generation. This is not official activation.
3. The preparer chooses one accepted prior output covering the same period and file format. For a first layout, the candidate must retain the reviewed blank/redacted reference form.
4. GRAND generates a retained candidate preview and records the candidate template, reference, logos, mappings, page controls, and SHA-256 checksum.
5. Where an accepted prior run exists, GRAND automatically compares dataset checksum, control checksum, row count, source count, and control status. Any difference blocks submission.
6. The preparer records the human comparison: headings, labels, totals, optional blocks, signatories, page count, pagination, overflow, form stock, and printer alignment.
7. GRAND records changed template fields, current schedule impact, incompatible output formats, and whether compatible schedules should move during activation.
8. Submission locks the preview, comparison, impact, template snapshot, and submission checksum.
9. A different authorized reviewer approves or returns the request with a reason.
10. An authorized configuration manager activates the approved version without a software deployment. Historical runs remain pinned; compatible schedules move only when the request explicitly elected that behavior.

The old free-text “validate fidelity” shortcut no longer grants official status. It redirects users into this retained workflow.

## Rollback

An activated successor can be rolled back only to its retained prior official version, with an actor and reason. GRAND deactivates the candidate, restores the prior version, and returns compatible schedules that had moved to the candidate. It does not delete the promoted version, preview, approval, events, or outputs.

A first official version has no earlier layout to restore. Correct it by creating and promoting a successor.

## Roles and guidance

- Budget review/consolidation and Finance configuration managers prepare comparisons and activate approved versions.
- Budget authorization and Finance configuration approvers independently approve or return them.
- The preparer/submitter cannot approve the same request.
- Department scoping prevents another office from reading or acting on the promotion record.
- Accounting and Budget **Internal How-To** guides explain the workflow inside the floating **?** window without taking users away from their current page.

## Export and safekeeping

The promotion receipt exports as deterministic JSON under the shared `GRAND_EXPORT_ROOT` department/user/category/year/month structure, in the `finance-report-template-promotions` category. Its adjacent manifest retains the promotion identity, status, template checksum, submission checksum, and export checksum for TraceSync copying and offline safekeeping.

## Acceptance still required

F10.1 supplies the application control, not field acceptance. Before an official production form is enabled, the named office must still provide and accept the exact current blank form and redacted signed sample; current authority and local-use decision; required and optional blocks; signatories; copies and recipients; page geometry and print area; row overflow behavior; form stock; printer alignment; and at least one accepted golden output. The parent F10 exit gate remains open until an authorized non-developer completes that exercise on the actual local form and the responsible offices sign off.
