# Department report-template intake

Use this checklist before treating a GRAND-generated report as an official departmental form. A technical template approval permits controlled preview generation; official activation requires the retained promotion, golden comparison, independent approval, and impact record described in [Finance visual template promotion and rollback](FINANCE_TEMPLATE_PROMOTION.md). Local acceptance is separately recorded through the [Finance local-form inventory and acceptance](FINANCE_LOCAL_FORM_ACCEPTANCE.md) workflow.

## Template pack

Collect these items from the department for each report:

- a blank current template;
- a redacted or synthetic completed example;
- the governing memorandum, circular, or reporting instructions when applicable;
- the required submission format and receiving office or agency;
- frequency, covered-period rules, and filing deadline;
- prepared-by, reviewed-by, and approved-by roles;
- paper size, orientation, margins, borders, logos, print headers, footers, page numbering, and annex rules;
- any manual calculations, external figures, corrections, or narrative sections not yet stored in GRAND.

Never place production citizen data in the repository or synthetic showcase pack.

## Compatibility decision

| Mode | Use when | Current state |
| --- | --- | --- |
| Native GRAND layout | The office accepts a controlled data table with configurable print identity and geometry | Supported for PDF and XLSX |
| Mapped Excel workbook | The existing workbook's cells, merged headers, formulas, print areas, and sheets must be retained | Supported for macro-free XLSX through reserved named ranges and preflight |
| Mapped Word document | The report combines narrative sections, expanding tables, and official signatory blocks | Intake/reference only; use native PDF or XLSX unless a later governed renderer is approved |
| Exact PDF form or overlay | A receiving agency mandates fixed boxes and coordinates | Supported through reviewed coordinate mappings and preflight |

Uploaded documents and images remain non-executable references. Mapped XLSX and PDF files are data-free layout sources: the mapper writes only allowlisted application fields after checksum-backed preflight. GRAND does not run macros, embedded queries, scripts, or arbitrary template expressions.

## Pilot comparison

1. Configure a versioned native layout, mapped XLSX, or exact PDF overlay and complete controlled preflight.
2. Generate the same covered period through the existing process and GRAND.
3. Compare totals, labels, row ordering, rounding, page breaks, logos, borders, repeating headings, footers, signatories, annexes, and print output.
4. Record every mismatch and resolve it in a new template version when print geometry or mappings change.
5. Prepare the promotion record with the accepted prior run, human comparison, printer/form-stock checks, and schedule-impact choice.
6. Have a different authorized reviewer approve the locked evidence, then let an authorized manager activate it separately.
7. Open **Local form acceptance** in the reporting workspace and inventory the familiar form, exact blank/redacted reference, authority, local decision, sections, signatures, copies, custody, deadlines, accessibility, overflow, and print settings.
8. Perform all seven practical tests, have a different witness decide each attempt, and submit the exact form version to a different acceptance reviewer. Do not copy test results into a successor.

Preview outputs may be printed or downloaded by authorized employees for comparison, but GRAND blocks local-form acceptance until promotion/activation and independently witnessed form evidence are complete.

## Print and download behavior

- Print appears only for an archived PDF and opens an inline browser preview.
- Download appears for archived PDF, XLSX, and CSV outputs.
- Both actions require `reporting.download_reports` or equivalent department-head/OIC authority.
- Employees cannot expose another department's files through a direct URL.
- XLSX and CSV do not display a misleading Print action; users download them and print through an appropriate spreadsheet tool when necessary.
- Archived files retain the template version and checksum used at generation time.

## Versioning rule

An approved template's header, footer, logos, page geometry, border, reference file, mapping notes, and document-control behavior are immutable. A change creates a new version. Existing archived output files do not change when the institution later updates its portal identity or report layouts.

An accepted local-form record follows the same history-preserving rule. Start a reasoned successor, edit its familiar fields and sections, repeat the practical tests, and obtain independent acceptance. The prior accepted record remains effective until the successor is accepted, then remains exportable as superseded evidence.
