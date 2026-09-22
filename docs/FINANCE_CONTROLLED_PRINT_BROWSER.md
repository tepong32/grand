# Controlled DV printing and replacement browser rehearsal

2026-09-22 development evidence, based on v0.7.130
`6319ddcf24f79600efc74b54b697fc9a6e52d9cb`. No application code changed.
This closes the controlled-printing omission in the earlier ordinary browser case
within a synthetic software rehearsal; actual physical operations remain unproved.

## Setup and actual browser actions

Fresh, separate default/Finance SQLite stores under
`.tmp/controlled-print-browser-20260922`, loopback server 8776. Existing fixture
services created authoritative Budget authority/allotment/OBR, submitted intake,
independent Accounting review and a DV for gross 1,000, deduction 10, net 990.
Controlled printing was enabled on the synthetic template before case creation.
Those setup steps were service calls, not new browser proof of the whole chain.
The initial helper used nonexistent `PayableIntake.ACCEPTED`; setup stopped before
review. Corrected to the service's `READY` constant and resumed the single case.
No operator or application data repair was needed.

Using Accounting preparer's browser session:

1. No returned-signature action was shown before printing/assembly. Prepared v1
   through the visible button and downloaded its actual checksum-backed workbook.
2. Recorded two explicitly SIMULATED printed copies and a SIMULATED packet with
   four documents/twelve pages. No real printer or papers were used.
3. Attempted replacement with a blank reason. The service rejected it and the
   page retained v1. Entered an explicit simulated replacement reason; v2 appeared
   with signature round 2 and required fresh print/assembly evidence.
4. Downloaded v2, recorded simulated replacement printing and verified the same
   packet association. The UI exposed only the next eligible signature step.
5. Recorded both named round-2 steps in order with explicit synthetic notes.
   Case advanced to Accounting validation; v2 displayed Signed packet returned.
6. Changed to the independent validator's session and confirmed the visible
   Validate and request GRAND JEV action. No JEV was requested or posted in this
   browser rehearsal. The earlier ordinary payment proof remains separate.

## Verification

PASS: read-only fixture assertions in `.tmp/controlled_print_proof.py` prove two
print jobs, v1/output superseded, v2 linked to v1 and signed-returned, old pending
signature tasks retired and both new tasks returned. Both versions use the same
TracePoint item. Case is at Accounting validation with no payment instruments.
Each browser download hashes identically to its stored file, print-job checksum
and archived file. Original and replacement files are retained separately.

Retained under `output/playwright/`:
- `controlled-signing-v1.xlsx` and `controlled-signing-v2.xlsx`: actual synthetic downloads.
- `controlled-print-v2-packet.png`: inspected packet/version and superseded output display.
- `controlled-print-signed-return.png`: final stage screenshot.
- `controlled-print-browser-facts.json`: asserted final facts and checksum evidence.

Existing unchanged-code baseline: 21 tests PASS, no skips, 11.731s, exit 0,
from v0.7.130. Exact command in CONTINUE.md's prior checkpoint; no redundant re-run
for documentation/artifacts. This includes controlled-print/reprint, office denial
and Finance custody task contracts. NOT RUN - OUT OF SCOPE: native MySQL/full
project regression for this evidence-only change; neither is claimed as passed.

Browser/server stopped. Operator database SHA-256 remains
`C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C`.
eGAPS untouched. No production migration, master merge or deployment.

## Remaining evidence

The template remains an editable starter, not a locally accepted official form.
The screenshot correctly says so. Workbook hashes do not establish exact field,
print-area, pagination, paper or signature-layout fidelity. Inspect the generated
workbook against its retained source values and print settings next, before any
code change. Actual paper printing, wet signatures, TracePoint physical handover,
independent field witnessing and named-office acceptance remain open.

FG-07 and the full Finance Completion Gate remain partial. Preserve the local
output inventory and earmark unknowns; no new domain behavior is inferred here.
