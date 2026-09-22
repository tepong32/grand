# DV source context in governed templates

Development checkpoint, 2026-09-22; branch `codex/finance-dv-source-context`,
based on v0.7.132 / `05503560242bfe3f24ab57fcc6fadd44227a6c33`.
See [foundation gate](FINANCE_FOUNDATION_GATE.md) and [required output map](FINANCE_REQUIRED_OUTPUT_MAP.md).

## Demonstrated omission and change

The editable DV starter displayed Fund, Address, TIN, OBR/ORS/ALOBS reference
and Claim reference labels, but generation had no mappings for those cells.
New starter workbooks expose five optional controlled names. Fresh preflight
records the names that exist; verification, preview and generation bind only
those already recorded in the template's mapping. Merely upgrading the code
never opts an existing approved workbook into newly recognized names.

Fund codes come from the case's retained Budget allocation lines. Authoritative
obligation references come from active payable allocations and their certified
obligations, including every reference for a multi-obligation claim. The
compatibility projection's MULTI/... identifier is not presented as an OBR.
Legacy cases retain their existing OBR reference. Missing authoritative links
fail closed. Claim reference comes from the linked intake; address/TIN from the
case's exact party version, not the latest party sharing its code. Missing
optional source data stays blank.

New outputs retain context values, party version and obligation allocation
identities/versions/checksums/amounts in their input evidence. Replays retain the
original output bytes. Context is literal spreadsheet text, including a leading
= character. Preflight checks single-cell destinations, print coverage, merged
anchors and collisions with other controlled fields or the detail table.
Existing unbound custom cells and issued output files remain unchanged.

No model migration, journal posting, financial amount, lock order, permission or
approval workflow changes. The multi-source test uses 1,500 of independently
certified Budget authority/allotment for two obligations of 1,000 and 500, then
allocates 500 from each to a 1,000 payable. Reducing a payable allocation does
not release the original Budget obligation.

## Validation

Initial focused SQLite run: 33 pass / one fixture error (34 total, 7.324s).
The second obligation exceeded the fixture's original 1,000 allotment; financial
validation correctly rejected it. Corrected funding setup uses the existing
Budget services; no capacity control was relaxed. Second focused run: 33 pass /
one fixture error (34 total, 7.074s), because certification correctly required
an explicit controlled obligation number. Added that number to the fixture.

PASS: native MySQL 8.4.11, 35/35 tests, no skips, 9.482s, exit 0.
Fresh default/Finance test stores were destroyed and the owned server stopped.
Command (the local helper supplies private fixture credentials without logging them):

```text
python .tmp/retrieval_native.py finance.tests vouchers.tests.VoucherWorkflowTests.test_dv_context_uses_pinned_sources_and_retains_output_evidence vouchers.tests.VoucherWorkflowTests.test_dv_context_does_not_fill_unapproved_legacy_names vouchers.tests.VoucherWorkflowTests.test_dv_context_lists_actual_multiple_obligations_and_claim_reference
```

PASS: changed Python compilation and `git diff --check`. Read-only inspection
of the actual starter and both prior issued samples passes; prior sample source
values and SHA256 hashes are unchanged. Retained facts:
[starter/output evidence](../output/playwright/dv-source-context-facts.json).
The operator database SHA256 remains
`C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C`.

PASS: broader SQLite regression, 362/362 tests, no skips, 199.059s, exit 0.
Fresh default/Finance test stores destroyed. Scope includes Finance setup and
cutover, ordinary voucher workflows, signatures/custody, Budget workflows and
payable handoff, and Reporting local-form acceptance controls:

```text
python .tmp/earlier_sqlite.py finance vouchers.tests vouchers.test_signature_custody budget.tests budget.test_payable_handoff reporting.test_local_form_acceptance
```

Logs: `.tmp/dv-context-broad.log` and `.tmp/dv-context-native.log`.
Full repository/native suites: NOT RUN - OUT OF SCOPE for this bounded mapping
change; broader production acceptance remains required. CI is reported separately
and local passes are not substituted for remote results.

## Limits and next work

This checkpoint binds source context, not accepted official-form fidelity.
The actual application starter is preflighted in the Finance test; output tests
use a synthetic controlled workbook and actual Budget/intake services. These do
not establish physical print quality, wrapping of long references, local form
approval, wet signatures, custody or LGU acceptance. No production configuration,
operator data, master merge or deployment is authorized by this checkpoint.
FG-06 remains partial; eGAPS remains closed and local earmark semantics unknown.
Next compare a populated actual starter, including long/multiple references,
with its source evidence and rendered layout before further template changes.
