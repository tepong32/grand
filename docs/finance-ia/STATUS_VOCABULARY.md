# Finance status vocabulary

The interface must name the object before its status: `Case phase: Obligation control`, `Task: Returned`, `JEV: Posted`, `Check: Cancelled`. A generic badge such as `Approved` or `Completed` is prohibited where the object is ambiguous.

## Case phase

Case phase answers “where is the shared case in the complete cycle?” It does not assert every artifact in the phase is approved.

| Code | User label | Meaning |
|---|---|---|
| `request_preparation` | Request preparation | Requesting office is preparing/submitting the funded request and references. |
| `budget_authority` | Budget authority | Approved-budget and classification linkage is being established. |
| `allotment_control` | Allotment control | Release/reserve/deferral authority is being established or checked. |
| `obligation_control` | Obligation control | Obligation request, certification, registry, or adjustment is active. |
| `claim_validation` | Claim validation | Procurement/delivery/claim evidence and payable readiness are under review. |
| `voucher_and_signatures` | Voucher and signatures | DV preparation, controlled print, custody, and wet signatures are active. |
| `accounting` | Accounting | Recognition/adjustment/payment JEV review, posting, or ledger work is active. |
| `payment` | Payment | Cash check, instrument, advice, authorized release, or remittance is active. |
| `reconciliation` | Reconciliation and close | Bank/register/ledger/report reconciliation or period close work remains. |
| `closed` | Closed | Enabled terminal conditions and reconciliations are accepted. |
| `cancelled` | Cancelled | Case ended through an authorized cancellation with retained history. |

An enabled transaction may skip an inapplicable phase only through a versioned, accepted route. Its timeline still records why.

## Work-task state

| Code | Label | Meaning |
|---|---|---|
| `ready` | Ready for action | All known gates pass and the user's role may act. |
| `claimed` | In progress | An authorized worker claimed the task; no approval is implied. |
| `waiting` | Waiting for evidence | A named gate, office, document, balance, signature, or external acknowledgement is pending. |
| `returned` | Returned for correction | A reason and destination are recorded; prior history remains. |
| `completed` | Task completed | This task ended successfully; the case may continue. |
| `cancelled` | Task cancelled | The task ended without action because the route/case changed. |
| `superseded` | Task superseded | A newer version/task replaces it. |

## Authority and artifact lifecycles

Use object-specific vocabularies:

- Configuration/template: `Draft → Submitted for review → Approved → Scheduled → Active → Superseded → Retired`.
- Budget version: `Working → Submitted → Reviewed → Authorized/Conditionally authorized/Disapproved → Superseded` (final labels require LGU confirmation).
- Authority movement: `Draft → Submitted → Approved → Effective → Adjusted/Reversed/Cancelled`.
- DV/controlled output: `Draft → Ready to print → Printed → Awaiting wet signatures → Signed packet returned → Superseded/Cancelled`.
- JEV: `Draft → For posting → Posted → Reversed`; a posted JEV is never edited or relabeled Void without accepted authority.
- Payment instrument: `Prepared → Issued → Signed/eligible as locally required → Advised → Released → Reconciled`, with `Spoiled/Cancelled → Replaced` lineage.
- Advice: `Draft → Finalized → Submitted → Acknowledged`, with `Returned/Superseded` where applicable.
- Reconciliation: `Not started → In progress → Difference unresolved → Reconciled → Reviewed/Closed`.

These are design vocabularies. F0 evidence may change local labels and applicable transitions without weakening immutable history or segregation.

## Exception vocabulary

Exception is an independent facet, not a replacement phase/status:

| Level | Use |
|---|---|
| Information | No action required; explain an accepted condition. |
| Attention | Human follow-up is needed but no current control failure is known. |
| Blocking | The named task/action cannot proceed until the gate is resolved. |
| Critical | Authority, financial integrity, segregation, official output, custody, or reconciliation is at risk; affected scope is stopped. |

Show reason, affected action/scope, responsible role, evidence/decision ID, raised time, and resolution event. Avoid accusatory language for duplicate warnings or unexplained differences.
