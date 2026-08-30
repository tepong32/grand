# GRAND Finance process-fidelity baseline

This is the comparison starting point before full LGU field evidence is collected. `Implemented` describes GRAND code, not actual LGU acceptance. Findings use the evidence labels defined in the [complete-cycle roadmap](FINANCE_ROADMAP.md); the read-only eGAPS inspection did not prove hidden rules or exact operator sequences.

## Complete-cycle baseline

| Seq. | Required capability/stage | Intended owner | GRAND position | Current finding and evidence required |
|---:|---|---|---|---|
| 1 | Budget call, departmental proposals, PPAs, targets, and revenue/resource estimates | LCE, departments, Planning/LFC, Budget, Treasury | F3.1 synthetic controls implemented | **Implemented, acceptance pending.** Obtain approved process, versions, classifications, calendars, ceilings, forms, and sign-off. |
| 2 | Executive budget, Sanggunian authorization, appropriation ordinance, and review | LCE, Sanggunian, Budget, reviewing authority | F3.2 authority lineage and immutable schedules implemented | **Implemented, acceptance pending.** Reconcile annual/supplemental/reenacted forms, review results, conditions, and signed control totals. |
| 3 | Fiscal-year opening, approved appropriations, continuing items, and opening balances | Budget and Accounting | F2.1–F2.2 fiscal/opening controls and F3.2 appropriations implemented | **Implemented, acceptance pending.** Reconcile approved schedules and opening balances to source books/system. |
| 4 | Allotment Release Orders, reserves, deferrals, and adjustments | Budget Officer and LCE/authorized approver | F4.1 immutable movement and balance control implemented | **Implemented, acceptance pending.** Confirm applicable ARO/equivalent forms, release authority, numbering, classifications, signatures, and signed balances. |
| 5 | ALOBS/ORS/OBR and RAAO/equivalent obligation registry | Requesting office and Budget | F4.2 authoritative request, certification, immutable movement, and balance control implemented | **Implemented, acceptance pending.** Confirm preparer/certifier, exact form/number/signatures, registry columns, return/rejection, period, cancellation, adjustment, and signed control totals. |
| 6 | Request, procurement/delivery, acceptance, and payable readiness | Requesting office, procurement/inspection, Accounting | F5.1 authoritative obligation/payable handoff implemented for one-to-one ordinary-supplier synthetic intake | **Partial.** Confirm documentary rules, relationships, variants, forms, exceptions, and replay one ordinary supplier plus each enabled variant from source evidence. |
| 7 | Accounting DV preparation | Accounting preparer | Implemented shadow route | Exact fields, document checks, tax/deduction rules, number timing, obligation adjustment, and maker responsibilities remain LGU-unverified. |
| 8 | Controlled official print and packet assembly | Accounting/authorized print custodian | Immutable shadow XLSX exists; print is not an explicit state/action | **Confirmed voucher-subcycle divergence.** Confirm printer/form control, official-number point, copy count, packet manifest, reprint, and supersession. |
| 9 | Physical packet registration and wet-signature circulation | TracePoint preparer/custodians and physical signatories | Optional TracePoint link and manual signed-return rounds | **Partial by design.** Confirm mandatory custody point, checkpoints, signatory matrix by transaction type, acting/refusal/return behavior, and terminal evidence. |
| 10 | Accounting validation, recognition, JEV review, and posting | Accounting reviewer/preparer/poster | Standalone balanced JEV materialization and maker-checker posting implemented | Recognition-versus-payment entries, mappings, batches, subsidiary schedules, period control, and actual eGAPS/local correspondence remain unverified. |
| 11 | Cash availability and payment-instrument preparation/printing | Treasury | Check registration and exception lineage implemented; cash program and direct print excluded | **Partial.** Confirm cash certification, instrument types, printer/form/custody, signatures, spoiled register, and payment postings. |
| 12 | Advice, release, receipt, remittance, and unclaimed handling | Accounting and Treasury | F8.1 remittance, F8.3 instrument exceptions, and F8.4 multi-case advice submission/acknowledgement plus returned-item Accounting/reissue orchestration implemented | **Implemented synthetic control; acceptance pending.** Confirm exact office ownership, bank/advice form and channel, agency forms/deadlines, receipts, local thresholds, stop-payment/cancellation, accounting entries/no-entry decisions, and correction rules. |
| 13 | Bank reconciliation, registers, ledgers, accountability reports, statements, and close | Budget, Accounting, Treasury | GL/trial balance/subsidiary controls plus F8.2 adjusted-balance reconciliation and F8.5 prior-item carry/clearance lineage implemented | **Partial, acceptance pending.** Confirm bank formats, local ageing/escalation, bank-memo/JEV route, official BRS, signatories/deadlines/copies, consecutive-month replay, other reports/statements, and period/year close. |
| 14 | Cross-cycle corrections and exceptions | Stage-specific authorized employees | Reasoned successors and linked reversals/replacements implemented across current synthetic slices, including F8.4 advice and returned-payment routes | Confirm end-to-end local authority and redacted replay for budget adjustment, obligation release, DV return/reprint, JEV reversal, spoiled/returned/replacement check, advice supersession, and reopening. |

## Earliest complete-cycle divergence

The earliest product gap occurs before voucher creation:

```text
Required complete cycle
Approved annual budget -> appropriation -> allotment release
-> obligation request/certification -> payable -> DV

GRAND today
Fiscal/opening control -> annual budget -> authorized appropriation
-> posted allotment movement -> authoritative obligation certification and registry movement
-> DV
```

GRAND now supports synthetic training from annual budget through one-to-one ordinary-supplier payable intake, including authoritative obligation UUID/checksum linkage. The earliest incomplete complete-cycle link remains the rest of F5: locally accepted document rules, payable decisions, relationship patterns, transaction variants, forms, exceptions, and redacted replay acceptance.

Within the narrower implemented voucher subcycle, the earliest confirmed mismatch remains printing and physical custody:

```text
GRAND voucher prototype
DV prepared -> controlled XLSX available -> awaiting wet signatures

Actual route to confirm
DV prepared -> official signing copy printed -> attachments assembled
-> physical packet registered/received -> wet-signature visits
-> signed packet returned -> Accounting validation
```

TracePoint receipt is evidence of custody, not a financial approval. A finance gate may require appropriate custody evidence, but the authorized employee must still confirm the legal/business decision.

## Immediate evidence program

Use the [discovery protocol](FINANCE_PROCESS_DISCOVERY.md) in this order:

1. reconcile one approved fiscal year from ordinance/review through system appropriations and opening balances;
2. trace one appropriation through ARO, obligation registry, selected ALOBS/ORS/OBR, payable, DV, JEV, payment, bank evidence, and reports;
3. map every paper print, wet signature, and TracePoint/physical handoff;
4. replay the same redacted facts in GRAND and classify each step;
5. obtain named-office acceptance before implementing or enabling the affected roadmap scope.

The implementation sequence and acceptance gates are governed by the [GRAND Finance complete-cycle roadmap](FINANCE_ROADMAP.md).
