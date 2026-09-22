# Populated DV starter: particulars and detail separation

Development checkpoint, 2026-09-22, based on v0.7.133 / PR #94.
See [foundation gate](FINANCE_FOUNDATION_GATE.md) and
[source context contract](FINANCE_DV_SOURCE_CONTEXT.md).

## Reproduction

An isolated two-store fixture generated the actual application starter through
Budget certification, payable allocation, Accounting review and DV generation.
The case allocates 500 from each of two certified obligations to a 1,000 payable,
with 10 deductions and 990 net. Party/address data is synthetic. Configuration
activation is a test fixture, not claimed independent real-world approval.

The original starter mapped GRAND_PARTICULARS to A10, which was also the first
cell of GRAND_LINE_ITEMS. The saved workbook contained the line description
"Synthetic office supplies" but lost the distinct case particulars "Synthetic
office supply payment". Both source values are retained in the before facts.
Artifact Tool inspection and rendering confirmed the generated content.

The renderer displayed the long synthetic address, TIN, both obligation references
and claim reference. This is screen-render evidence, not proof of Excel's printed
pagination or physical output. Do not infer a clipping defect solely from default
row heights, or claim accepted print layout from the renderer.

## Repair and boundaries

New starters reserve a separate merged particulars area and move the detail table
below it. The configured detail row capacity is preserved. Print titles, freeze
boundary, downstream totals/signature/footer positions follow the new table.
Detail amounts retain numeric values and show two decimal places.

Validation must reject controlled fields that overlap, including scalar/table
collisions. Existing approved workbook bytes are never rewritten. A conflicting
old template needs a corrected new draft and the existing independent review
before another output can be generated; issued copies remain retained.

## Validation and remaining work

PASS: the initial starter repair passed 164 tests in 66.299s, no skips, exit 0:

```text
python .tmp/earlier_sqlite.py finance.tests vouchers.tests vouchers.test_signature_custody reporting.test_local_form_acceptance
```

PASS: final broader regression after general collision validation, 364/364 tests,
no skips, 195.499s, exit 0. Fresh separate default/Finance stores were destroyed.
Scope covers full Finance setup/cutover, ordinary vouchers, signatures/custody,
Budget and payable handoff, and Reporting local-form controls:

```text
python .tmp/earlier_sqlite.py finance vouchers.tests vouchers.test_signature_custody budget.tests budget.test_payable_handoff reporting.test_local_form_acceptance
```

Logs: `.tmp/starter-layout-tests.log` and `.tmp/starter-layout-final-tests.log`.
Changed Python compilation and `git diff --check` PASS. Operator DB SHA256 is
unchanged: `C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C`.
No live fixture server or test runner remains. CI results are separate evidence.

PASS: isolated before/after source assertions and read-only workbook verification.
Both case particulars and detail description are retained in the corrected output;
context and 1,000/10/990 totals match, ten detail rows remain available, numeric
amount types and the revised repeat-title boundary agree. The original conflicting
workbook now raises `GRAND_PARTICULARS overlaps controlled field GRAND_LINE_ITEMS`.
Original output hashes remain unchanged. Both PNGs were visually inspected;
renderer exit codes were not captured independently of the shell's subsequent
log-read command, so no renderer-process exit-status claim is made.

Evidence:

- [Before source facts](../output/playwright/starter-layout-before-facts.json)
- [Before workbook](../output/playwright/starter-layout-before.xlsx) and [render](../output/playwright/starter-layout-before.png)
- [After source facts](../output/playwright/starter-layout-after-facts.json)
- [After workbook](../output/playwright/starter-layout-after.xlsx) and [render](../output/playwright/starter-layout-after.png)
- [Verification facts](../output/playwright/starter-layout-verification.json)

Native MySQL: NOT RUN - OUT OF SCOPE for workbook geometry and validation only;
no persistence schema, query, transaction or concurrency changes. Prior v0.7.133
native source-context validation remains separate evidence. No financial
posting, amount, schema, permission or lock-order change. Physical printing,
local accepted-form fidelity, wet signatures and actual custody remain open.
The Finance goal is incomplete and production remains NO-GO.
