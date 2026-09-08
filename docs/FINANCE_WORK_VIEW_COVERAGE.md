# Finance personal handoff coverage

This table describes the implemented My Work views, not production or LGU acceptance. Current source authorization applies to every row. Ready/action coverage is detailed in [FINANCE_MY_WORK.md](FINANCE_MY_WORK.md); turning-point choices are in [IMPLEMENTATION_DECISIONS.md](IMPLEMENTATION_DECISIONS.md).

Last reviewed: 2026-09-08, v0.7.30 instrument-action history.

| Source domain | Personal Waiting | Completed by me |
| --- | --- | --- |
| Finance setup releases | Own submitted releases; current authorized review actions excluded (v0.7.18) | Retained release transition events (v0.7.19) |
| Discovery decisions | Retained preparer/submitter handoffs with named source read scope (v0.7.20) | Retained submission, return and recording events (v0.7.20) |
| Budget proposals, allotments and obligations | Implemented for supported source review/certification handoffs | Retained Budget events implemented, including call/consolidation/appropriation actions |
| Accounting JEVs | Own submitted JEVs, excluding current posting actions | Retained submission/posting/return events |
| Opening balances | Submitted source handoffs | Retained submission, decision, posting and reconciliation events |
| Period close/reopen | Submitted close checklist handoffs; broader reopen Waiting remains to audit | Retained close and reopen events |
| Bank advice | Supported review, bank-submission and bank-response handoffs | Retained review, submission and recorded bank-response events |
| Treasury remittances | Review, release and Accounting-posting handoffs; related current actions excluded | Retained review, release and posted-source synchronization events |
| Payable intake and shared voucher processing | Review/DV preparation (v0.7.21), plus signatures and independent validation (v0.7.23) Accounting posting (v0.7.25), Treasury preparation/advice (v0.7.26) and release/event posting (v0.7.27). Returned reviews use their own adapter (v0.7.28) | Retained payable submission/return/acceptance events (v0.7.21) |
| DV print, packet and wet-signature custody | Personal case Waiting through signatures/validation, with authorized child-action exclusion (v0.7.23) | DV preparation/correction, ordinary signature-return recording and validation events (v0.7.24); print/packet/amendment history remains |
| Payment instruments | Shared case through Treasury/advice/release/event posting (v0.7.27); returned reviews use their own adapter (v0.7.28) | Retained issuance/replacement/advice-submission/cancellation/release events (v0.7.30) |
| Bank reconciliation | Remaining coverage | Remaining coverage |
| Returned-payment reviews | Current attributed review/clarification/posting/replacement handoffs (v0.7.28) | Retained submission/clarification/return/decision events (v0.7.29); later posting remains; issuance uses instrument history (v0.7.30) |
| Cash policy and cash position | Remaining coverage | Remaining coverage |
| Reporting runs and accountability packages | Remaining coverage | Remaining coverage |
| Field cycles and named nested controls | Remaining coverage | Remaining coverage |
| Local forms | Remaining coverage | Remaining coverage |

## Common rules and remaining work

- Waiting means work the user prepared/submitted that is now with another queue, under current source read access. It is not all visible office work. Current actionable records are removed before the display cap.
- Completed by me credits retained actions attributed to the account. It does not infer actions from terminal status or credit later reviewers' actions to a creator. Current source state remains separate.
- Returned uses current actionable correction state; a historical return does not label a resubmitted record as returned. Setup draft returns additionally require a matching retained return event.
- Upcoming/Past dates currently filter supported actionable tasks with stored targets. They do not provide an all-record calendar. The meaning of each target remains visible; no working-day or legal deadline is invented.
- The administrator-assigned portable export permission applies to the selected supported view. Coverage and truncation are retained with the export.
- Assignment/following rules, governed shared views and notifications remain future work. They must build on the same source contract rather than create another authoritative queue.

Next: audit remaining completion history and bank-reconciliation/cash/reporting handoffs. Review each remaining domain's real authority, return/recovery path and attribution before adding its personal projections. Preserve the separate post-functional scrutiny and LGU acceptance gates.
