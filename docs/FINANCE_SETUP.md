# Finance Setup Center operations

The Finance Setup Center is GRAND's governed configuration boundary for future voucher work. It does not create, number, approve, post, or pay vouchers. Its operating rule is: **editable configuration for the future; immutable history for the past**.

## Responsibilities and permissions

Finance access always requires an active employee assigned to the same department as the configuration. Permissions never open another department's objects.

| Responsibility | Permission | Boundary |
| --- | --- | --- |
| View setup/readiness | `finance.view_finance_setup` | Assigned department only |
| Prepare releases and master data | `finance.manage_finance_configuration` | Draft preparation and submission; no approval by implication |
| Review, approve, schedule, activate, retire | `finance.approve_finance_configuration` | Assigned department, explicit permission, separate approver, recorded Accounting basis |
| Upload and preflight workbooks | `finance.manage_finance_templates` | Draft template versions only |
| Technical/provider setup | `finance.manage_finance_providers` | Does not authorize financial-policy approval |

Django superuser status is not treated as a finance-policy role. A platform administrator needs an assigned department and an explicitly assigned finance permission. Even then, the person who created or submitted a release cannot approve that same release. Every mutation creates an attributed append-only event.

## Governed release lifecycle

1. A Finance Configuration Manager creates a draft release for one fiscal year and effective period.
2. The manager adds versioned items, signatory assignments, a fiscal-year/document-type numbering policy, and one or more workbook versions.
3. Each workbook passes controlled preflight and may be downloaded as a synthetic-only preview.
4. The manager submits the release. Its draft components move to review with it.
5. A different Finance Configuration Approver records the local Accounting approval basis and approves the release.
6. Readiness must pass before immediate activation. An approved future-dated release may be scheduled.
7. Activation supersedes the preceding active release without deleting it. Historical configuration, workbook files, checksums, and events remain available.

Approved, scheduled, active, superseded, and retired configuration cannot be edited in place. Prepare a new stable code/version and use `supersedes` to make the lineage explicit. The setup app never consumes a numbering counter; that belongs to a future transactional voucher service.

## Supported configuration categories

The versioned item register supports voucher/transaction types, payee classifications, funds, offices/responsibility centers, bank/payment accounts, payment methods, account/expenditure classifications, obligation-reference behavior, tax/deduction/base/rounding rules, supporting-document requirements, approval routes and thresholds, and confidentiality/retention settings.

Values are stored as controlled JSON objects so locally approved details can evolve without fabricating a national or LGU default. Do not enter credentials, bank authentication secrets, production personal data, or signature images. Demonstration records must be conspicuously synthetic. Local Accounting approval is required for activation.

## Readiness contract

The readiness service returns stable reason codes, plain-language messages, and help anchors. Official activation is blocked if any check fails:

- `approved_voucher_template` — an approved, preflighted workbook is missing;
- `transaction_type_checklist` — transaction-type and document-requirement configuration is incomplete;
- `active_signatory` — no approved signatory covers the applicable date;
- `fund_and_payment_account` — an approved fund and payment account/method are missing;
- `approved_tax_rule` — no approved tax/deduction rule applies;
- `numbering_sequence` — no sequence exists for the fiscal year;
- `activation_date_conflict` — the release overlaps another scheduled or active release.

These structures are intentionally reusable by a future permission-aware GRAND Guide. Sandbox workbook previews remain available while official readiness is incomplete. The future Voucher Workbench must call the readiness service and pin the active release before enabling official creation.

## Macro-free Excel workflow

Finance templates are purpose-built voucher forms, not generic reports. The workflow is:

1. Download the current `.xlsx` version.
2. Edit layout, logos, headers, footers, borders, and print settings in Excel.
3. Upload it as a new version; `.xls` and `.xlsm` are rejected.
4. Define these workbook-level named ranges: `GRAND_DV_NUMBER`, `GRAND_DV_DATE`, `GRAND_PAYEE`, `GRAND_PARTICULARS`, `GRAND_GROSS_AMOUNT`, `GRAND_TOTAL_DEDUCTIONS`, `GRAND_NET_AMOUNT`, `GRAND_LINE_ITEMS`, `GRAND_PREPARED_BY`, `GRAND_CERTIFIED_BY`, and `GRAND_APPROVED_BY`.
5. Run preflight. It rejects invalid packages, macro payloads, external-link parts/formulas, network/dynamic-data formulas, missing or ambiguous named ranges, absent print areas, and zero line capacity.
6. Download a synthetic-only preview. GRAND verifies the workbook checksum again and inserts only conspicuously synthetic values.
7. Submit the containing release for a separate Accounting review and activate only when readiness passes.

Preflight records the exact workbook SHA-256, deterministic mapping SHA-256, controlled range map, worksheet count, print-area worksheets, line-row capacity, validator, and timestamp. Any future official output must additionally pin the configuration release, input snapshot, generator, generation timestamp, and output checksum/status. That output ledger belongs to the future Voucher Workbench/Records phases.

Wet-signature output is the starting assumption. Signature images are not collected by this phase. Digital signatures require a separate formal LGU decision, threat assessment, and implementation.

## Domain boundaries

- **Voucher Workbench** will own the financial transaction and voucher lifecycle.
- **Finance Setup Center** owns approved master data, rules, signatories, numbering, and form versions.
- **Reporting** owns derived registers, summaries, transmittals, and recurring reports.
- **Records** owns retained official outputs, attachments, review, retention, and supersession.
- **TracePoint** owns physical paper custody and may link a voucher to a packet item; it does not store financial voucher fields.

Before production activation, Accounting and the COA Audit Team should validate local rules and blank/redacted form fidelity in shadow/comparison mode. Never use legacy production data, PII, or proprietary compiled artifacts as fixtures or screenshots.
