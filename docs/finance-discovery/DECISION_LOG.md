# Finance decision and unresolved-question log

Record policy choices, disagreements, missing evidence, and scope blocks here. A deadline does not convert an unresolved question into a requirement.

## Status and outcome

- `Open` — evidence or accountable decision is still required.
- `Blocked` — the named affected scope may not proceed safely.
- `Proposed` — an accountable owner has proposed an outcome; reviewers have not accepted it.
- `Accepted` — named decision authority accepted the outcome and its evidence.
- `Superseded` — a later decision replaces it; history remains visible.
- `Rejected` — the proposal was declined; record the replacement or remaining question.

## Project baseline decisions

| Decision ID | Question/decision | Status | Outcome/current position | Authority/evidence | Owner/reviewers | Affected scope | Due/review trigger | Replacement |
|---|---|---|---|---|---|---|---|---|
| DEC-001 | May GRAND depend on an installed eGAPS client, license, session, or database at runtime? | Accepted | No. GRAND Finance has an independent store and service boundary. | EV-003, EV-004, EV-005 | Project product and technical authority | All Finance phases | Reconfirm at architecture and cutover review | — |
| DEC-002 | Is the current Voucher Workbench authoritative for official Finance operation? | Accepted | No. It remains a shadow/UAT prototype until the applicable phase gates and cutover decision are accepted. | EV-004, EV-005 | Project product authority; LGU cutover authority still required | Current F5–F8 prototype | Every release and training artifact | — |
| DEC-003 | What is the earliest complete-cycle product gap? | Accepted | Annual appropriation, allotment release, and authoritative obligation control precede voucher use. Printing is the earliest confirmed divergence only inside the existing voucher subcycle. | EV-004, EV-005 | Project product authority | Delivery sequencing | Revisit only with contrary accepted evidence | — |
| DEC-004 | Which current national and local authorities govern the enabled LGU scope? | Open | National references are indexed, but current applicability, COA requirements, local ordinances, procedures, bank rules, and transaction-specific authorities require confirmation. | EV-001, EV-002 | Budget, Accounting, Treasury, legal/management, audit coordination | Blocks only unconfirmed rules/forms/routes | Before affected design acceptance | — |

## New-entry template

| Decision ID | Question/decision | Status | Options and control impact | Evidence required/IDs | Decision owner | Reviewers | Affected scope | Due/review trigger | Outcome/reason | Replacement |
|---|---|---|---|---|---|---|---|---|---|---|
| DEC-___ |  | Open |  |  |  |  |  |  |  |  |

For accepted decisions, record why rejected options did not meet authority, control, accessibility, continuity, or operational needs. Never store confidential deliberation or personal attribution in the repository copy.
