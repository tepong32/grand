# GRAND finance process fidelity baseline

This is the comparison starting point before LGU field evidence is collected. `Implemented` describes GRAND, not the actual LGU. `Confirmed divergence` is limited to facts already supplied by the project owner, such as the requirement for physical wet signatures. All other process-fidelity conclusions remain unverified.

## Current GRAND route

| Seq. | GRAND stage or event | Intended actor | GRAND evidence | Current finding | Actual LGU evidence required |
|---:|---|---|---|---|---|
| 1 | Case creation | Budget-authorized employee | Immutable case reference, requesting office, payee, type, particulars | Implemented; actual initiating office and intake route unknown | First receiving office, source documents, intake log, documentary gate |
| 2 | Budget certification / OBR | Budget officer | OBR number, date, source reference, allocation lines, certifier | Implemented pilot rule; authoritative appropriation and remaining-balance behavior excluded | Actual obligation checks, budget system of record, rejection and correction behavior |
| 3 | Accounting DV preparation | Accounting preparer | DV number/date, gross, deductions, net, checklist, template and preparer | Implemented; exact fields, documentary checks and number timing unverified | Redacted DV, attachment checklist, number-assignment rule, preparer responsibilities |
| 4 | Controlled DV generation | Accounting preparer | Immutable shadow XLSX version, input snapshot and checksum | **Confirmed divergence:** downloadable XLSX exists, but printing is not an explicit audited workflow stage | Who prints, when numbering becomes official, copy count, reprint and supersession controls |
| 5 | Physical packet registration | TracePoint preparer | Optional link from voucher case to an existing TracePoint packet item | **Confirmed divergence:** optional/manual and absent from the complete-cycle UAT case | Packet composition, label placement, custody log, activation point and responsible employee |
| 6 | Wet-signature circulation | Authorized signature tracker plus physical signatories | Ordered signatory snapshots and manually recorded signed-return events | Partial by design: GRAND records return of wet-signed paper; it does not digitally sign or authenticate handwriting | Exact signatories/order, intermediate office visits, refusal, absence, acting authority and return evidence |
| 7 | Accounting validation | A different Accounting reviewer unless a governed exemption exists | Decision, note, JEV request and maker-checker audit evidence | Implemented; exact validation checklist and legal gate unverified | Reviewer checklist, required signatures/stamps, return reasons, separation-of-duty policy |
| 8 | GRAND JEV materialization and posting | Accounting preparer and independent poster | Balanced journal lines, immutable source checksum, submission and posting history | Implemented in standalone GRAND Accounting; correspondence to eGAPS posting remains unverified | Redacted JEV, chart mappings, period controls, posting authority, reversal/correction process |
| 9 | Check registration | Treasury officer | Bank account code, check number, amount, cancellation/replacement lineage | Implemented; direct physical check printing deliberately excluded | Who prints/writes checks, printer/form controls, signatories, spoiled-check register and custody |
| 10 | Bank advice | Accounting-authorized employee | Advice number/date, bank account, immutable advised check set | Implemented; office ownership and exact advice process unverified | Advice form, bank submission method, required signatories, rejection/correction path |
| 11 | Check release | Treasury release officer | Active claimant, receipt reference, releaser, timestamp and completion event | Implemented; claimant proof and release controls unverified | Identity/authorization documents, release log, receipt, unclaimed and returned-check handling |
| 12 | Corrections and exceptions | Stage-specific authorized employees | Same-case returns, preserved DV number, signature rounds, check cancellation/replacement, governed exemptions | Implemented controls; actual return destinations and identifier rules unverified | Examples of returned DVs, reprints, changed signatories, cancelled checks and approved exceptions |

## Earliest known divergence

The first confirmed mismatch occurs after DV preparation. GRAND can generate a controlled workbook and immediately represents the case as awaiting signatures. The real LGU requires a physical signing copy, but GRAND does not yet make printing, packet assembly, TracePoint registration, or custody activation mandatory gates.

```text
GRAND today
DV prepared -> controlled XLSX available -> awaiting wet signatures

Actual route to confirm
DV prepared -> official signing copy printed -> attachments assembled
-> physical packet registered/received -> wet-signature visits
-> signed packet returned -> Accounting validation
```

TracePoint receipt should remain evidence of physical custody rather than an automatic financial approval. A future design may require the appropriate custody evidence before a finance employee records the next financial action, but the responsible employee must still confirm the legal/business decision.

## First evidence request

Obtain one redacted, completed ordinary supplier-payment packet and identify one knowledgeable participant from the requesting office, Budget, Accounting, and Treasury. Use [the discovery protocol](FINANCE_PROCESS_DISCOVERY.md) to replace each `unknown` finding with cited actual-process evidence.
