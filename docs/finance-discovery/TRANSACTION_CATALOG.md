# Finance transaction catalog

The catalog defines the routes that must be discovered, designed, tested, and accepted separately. Inclusion is not authorization to enable a transaction type.

## Catalog fields

| Field | Meaning |
|---|---|
| Transaction ID/name | Stable `TX-###` and locally understood name. |
| Enabled scope | Fiscal year, fund, office, claimant/payee class, amount band, and exclusions. |
| Initiating authority | Request, payroll, contract, bill, ordinance, court/order, or other authority. |
| Budget route | Appropriation, allotment, obligation, adjustment, and registry behavior. |
| Payable/claim rule | Documents and event that establish a valid claim. |
| Accounting route | Recognition, adjustment, liquidation, payment, remittance, and reversal JEV behavior. |
| Payment route | Check, ADA, transfer, cash, or other locally approved instrument and cash control. |
| Forms/outputs | Form, register, report, receipt, and template evidence IDs. |
| Roles/signatures | Matrix route ID and transaction-specific deviations. |
| Exceptions | Returns, partial/final payments, cancellation, replacement, and close handling. |
| Authority/evidence | Evidence IDs and labels supporting each material rule. |
| GRAND status | Missing, prototype, implemented, UAT accepted, or enabled by recorded cutover. |
| Acceptance | Named process owners and safe acceptance evidence. |

## Discovery backlog

Every row remains Unresolved until local evidence confirms applicability and route.

| Transaction ID | Candidate variant | Distinguishing questions | Initial GRAND position | Evidence/acceptance |
|---|---|---|---|---|
| TX-001 | Ordinary supplier payment | Procurement, delivery/acceptance, invoice, tax, obligation-to-claim adjustment, DV, JEV, instrument, advice, release, reconciliation | Voucher shadow prototype; upstream authority missing | Unresolved |
| TX-002 | Payroll and personnel compensation | Payroll authority, funding, deductions/remittances, bulk claims, confidentiality, bank/payment route | Not established as a complete-cycle route | Unresolved |
| TX-003 | Employee reimbursement | Prior authority, receipts, claimant validation, tax treatment, payable timing | Not established | Unresolved |
| TX-004 | Utility or recurring bill | Contract/account reference, consumption period, late/estimated bills, recurring controls | Not established | Unresolved |
| TX-005 | Financial assistance | Eligibility authority, privacy boundary, claimant/representative, acknowledgement, public-service linkage | Not established as a Finance route | Unresolved |
| TX-006 | Cash advance and liquidation | Grant, accountability, ageing, liquidation, refund/excess, subsequent-advance restrictions | Not established | Unresolved |
| TX-007 | Infrastructure/progress billing | Accomplishment certification, retention, progress/final billing, variation orders, warranties | Not established | Unresolved |
| TX-008 | Emergency procurement/payment | Emergency authority, abbreviated documents, post-review, exception expiry | Not established | Unresolved |
| TX-009 | Tax/deduction remittance | Source deductions, schedules, due dates, grouping, proof of remittance, reconciliation | Partial deduction fields only | Unresolved |
| TX-010 | Refund, return, or other receipt | Receipt authority, cash collection, deposit, recognition, refund netting prohibition | Accounting foundation only | Unresolved |

Add locally approved variants rather than forcing them into these candidates. Split a row when authority, classification, documents, signatures, posting, payment, or correction behavior materially differs.
