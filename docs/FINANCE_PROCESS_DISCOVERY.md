# Finance process discovery protocol

Use this protocol before treating GRAND's voucher workflow as an accurate copy of the LGU's operating process. The objective is not to validate GRAND against a policy manual alone. It is to reconstruct one real, completed voucher from documentary evidence and the employees who handled it, then replay the same case in GRAND.

## Scope of the first walkthrough

Choose one completed, ordinary supplier payment with no emergency procurement, cash advance, payroll, infrastructure billing, or unusual tax treatment. Later walkthroughs should cover those variants separately.

The source packet should be copied or photographed only after these values are redacted:

- signatures and signature specimens;
- bank account, check, TIN, personal address, telephone, and email values;
- personal identifiers and information about private citizens;
- credentials, QR bearer tokens, and internal network details.

Keep document titles, form geometry, office stamps, routing annotations, dates relative to one another, status labels, attachment types, and numbering relationships visible when policy permits. Assign each artifact an evidence ID such as `EV-01`; do not place production identifiers in this repository.

## Evidence inventory

Record whether the completed packet contains each item and which office produced it:

- initiating request and claim attachments;
- purchase request, purchase order, inspection or acceptance evidence, and invoice;
- obligation request or OBR;
- disbursement voucher and deduction worksheet;
- routing slip, receiving log, office stamps, and return notes;
- wet-signature pages and the configured signing order;
- journal entry voucher or equivalent accounting posting evidence;
- check preparation or printing evidence;
- bank advice;
- claimant authorization and release receipt;
- cancellation, replacement, or correction evidence, if applicable.

Absence is a finding. Do not invent an artifact because GRAND currently models it.

## Walkthrough order

Interview the requesting office, Budget, Accounting, and Treasury in the same order the packet actually travelled. If the route includes the Mayor, Vice Mayor, resident attorney, procurement, inspection, cashier, or another office, add that participant where the evidence places them.

For every handoff, ask:

1. What exact paper or system record arrived, and from whom?
2. What did the employee verify before accepting it?
3. What did the employee enter into eGAPS, Excel, a paper log, or another system?
4. What number, form, checklist, stamp, or printed paper was produced?
5. Whose wet signature or approval was required, and in what order?
6. Who physically held the packet after the action?
7. How was receipt acknowledged?
8. What condition authorized the next office to act?
9. What causes rejection or return, and to which exact step does it return?
10. Which identifiers survive correction, cancellation, reprinting, and replacement?

Prefer demonstration using the selected completed packet over answers based only on memory. Record disagreements as unresolved; do not choose one account without documentary or policy support.

## Actual-step record

Create one row for every business action and a separate row for every physical handoff.

| Field | What to record |
|---|---|
| Sequence | Observed order, including returns and repeated visits |
| Actor | Position and office, not a private employee identity |
| Input | Paper, system state, attachments, and prior authorization received |
| Action | Verification, entry, calculation, approval, printing, signing, or release |
| System | eGAPS module, spreadsheet, logbook, bank portal, or none |
| Output | Record, number, printout, stamp, signature, or packet produced |
| Custody | Holder before and after the action and how receipt was confirmed |
| Gate | Evidence that legally or operationally permits the next action |
| Return path | Destination, reason, preserved numbers, and work that must be repeated |
| Evidence | Redacted artifact ID, policy citation, and confirming office |

## GRAND replay

Replay the same facts with separate Budget, Accounting-preparer, Accounting-reviewer, and Treasury test accounts. Use the Finance UAT Viewer only to observe all office presentations; it must not submit actions.

For every actual-step row, identify the GRAND screen, permission, service action, event, output, and next stage. Classify the comparison:

- **Exact** — actor, order, authority, artifact, and correction behavior match.
- **Partial** — the purpose matches but a material paper, authority, custody, or routing detail differs.
- **Missing** — the LGU performs a required step that GRAND cannot represent.
- **Extra** — GRAND requires or records a step the LGU does not perform.
- **Unknown** — evidence is incomplete or participants disagree.

Assign severity separately:

- **Critical** — legal validity, financial authority, audit evidence, segregation of duties, or physical custody.
- **High** — wrong office, stage order, identifier, form, or correction route.
- **Medium** — reporting, search, workload, or avoidable duplicate entry.
- **Low** — terminology, help text, or presentation.

## Exit criteria

The ordinary-supplier flow is understood only when:

- every paper and system event has an accountable actor and evidence source;
- every physical handoff has a holder, receiver, and acknowledgement method;
- wet-signature order and the rule authorizing post-signature processing are confirmed;
- numbering, reprinting, correction, cancellation, and replacement behavior are confirmed;
- every actual step has an Exact, Partial, Missing, Extra, or Unknown comparison;
- Budget, Accounting, and Treasury agree that the actual-state map describes the selected completed packet;
- critical and high gaps have an accepted operational decision before implementation.

Do not generalize the result to payroll, cash advances, infrastructure, emergency procurement, or other transaction types until each variant receives its own walkthrough.
