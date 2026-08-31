# Finance role, signature, and custody matrix

This matrix separates four things that must not be conflated: responsibility for work, authority to approve, a wet signature on a controlled artifact, and physical custody of a packet. System permission is recorded separately from each.

## Route header

| Field | Record |
|---|---|
| Route ID and transaction |  |
| Fiscal year/fund/office scope |  |
| Effective dates |  |
| Evidence IDs |  |
| Acceptance owners |  |
| Supersedes route |  |

## Matrix template

Use `R` responsible, `A` accountable decision authority, `C` consulted, `I` informed, `W` wet signatory, and `P` physical custodian. Multiple codes require an explanation; `A` or `W` never implies system permission.

| Sequence/action | Requesting office | Budget maker | Budget approver | Accounting maker | Accounting reviewer/poster | Treasury maker | Treasury releaser | Setup manager/approver | Custody/Records | System permission | Evidence/notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Example: initiate obligation request | R | C | I | I | I | I | I | I | P | `finance.obligation.create: own_office` | Synthetic example only |
|  |  |  |  |  |  |  |  |  |  |  |  |

## Signature-route detail

| Round/order | Artifact and version | Signatory position | Authority/delegation evidence | Wet/digital/recorded confirmation | Acting/absence rule | Custodian before/after | Refusal/return route | GRAND representation | Evidence ID |
|---|---|---|---|---|---|---|---|---|---|
|  |  |  |  |  |  |  |  |  |  |

## Segregation checks

- Can the same user prepare and independently approve or post the same case?
- Can a setup author approve or activate their own finance policy change?
- Can a payment-instrument preparer release it without the locally required independent action?
- Can a custodian change a financial decision merely by acknowledging receipt?
- Can an acting signatory be selected without effective authority evidence?
- Can a permission grant cross the employee's department or enabled transaction scope?
- Does an exemption name its authority, scope, approver, expiry, and audit event?

Any `Yes` that is not supported by accepted authority becomes a Critical unresolved decision.
