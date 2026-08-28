# Finance workspace, case, timeline, search, and notification contract

## Global Finance navigation

| Destination | Purpose | Role shaping |
|---|---|---|
| Overview | Readiness, assigned workload, exceptions, period context, and recently viewed cases | Metrics are defined, scoped, time-stamped, and drillable; no decorative totals |
| My Work | Tasks the signed-in user may act on now or has saved/followed | Default view is `Ready for me`; tabs separate waiting, returned, due soon, and completed-by-me |
| Cases | Permission-filtered cross-cycle search and saved views | Filters and counts are evaluated after object authorization |
| Reports | Reconciled outputs, schedules, ledgers, accountability, and report status | Only authorized datasets/periods; totals state freshness and reconciliation status |
| Setup and controls | Fiscal readiness, master data, templates, numbering, roles, periods, health | Shown only for permitted read/manage/approve capabilities |

Notifications open the exact task, case event, report, or setup decision. They are not a parallel queue and cannot authorize an action.

## Overview contract

The page answers, in order:

1. Which LGU/office, fiscal year, business date, period, and operation mode am I viewing?
2. What can I act on now, what was returned, and what will breach a locally defined target soon?
3. Which control or reconciliation exceptions need attention?
4. What moved recently in cases I own, follow, or supervise?
5. Which Finance areas may my role open?

Every metric includes a definition, scope, generated-at time, and accessible link to its filtered result set. Currency totals identify fund and period; mixed-fund values are not silently added.

## My Work task contract

| Field | Requirement |
|---|---|
| Task ID/type | Stable task ID and controlled action type; never inferred only from a case status. |
| Case | Stable Finance case ID, display reference, transaction type, and safe subject/payee snapshot. |
| Action | Plain-language verb such as `Review allotment release`, `Post JEV`, or `Release advised instrument`. |
| Gate/authority | Evidence and state that make the task actionable; display missing gate when waiting. |
| Owner/queue | Assigned user when applicable plus accountable office/role queue. |
| Scope | Fiscal year, fund, requesting office, transaction type, and period where relevant. |
| Timing | Received, due/target, age, and local calendar used; avoid unsupported urgency claims. |
| State/version | Ready, claimed, waiting, returned, completed, cancelled; current state version for action submission. |
| Exception | Severity, reason, decision ID, and responsible resolution role without revealing restricted content. |

Claiming a task does not approve it. Reassignment is an auditable queue decision and does not rewrite the responsible office in past events.

## Shared Finance case contract

### Stable identity

- Internal immutable UUID and human display reference; display-number changes preserve aliases.
- Transaction type/version and enabled scope.
- Requesting office and safe counterparty/claimant snapshot at the time of submission.
- Fiscal year, fund, PPA/project/activity, responsibility center, and other accepted dimensions.
- Parent/child and consolidation/split relationships where the accepted transaction route permits them.
- Cross-database references are stable IDs and snapshots, not foreign keys to another database.

### Case header

Show the current phase, responsible office, next permitted action or waiting gate, authoritative amounts by concept, configuration/template versions, material exceptions, and non-authoritative/shadow marker. Never show one unlabeled `Available balance` or `Status` where multiple concepts exist.

### Case sections

| Section | Content |
|---|---|
| Summary | Current phase, next task/gate, transaction scope, safe parties, dates, and exceptions |
| Authority and budget | Budget version, appropriation, allotment movements, obligation, balances, adjustments, and evidence |
| Claim and voucher | Source-document references, completeness/waivers, payable decision, DV, deductions, prints, and signature rounds |
| Accounting | Recognition/payment/adjustment JEVs, posting states, ledger links, reversals, and reconciliations |
| Payment and release | Cash check, instruments, advice, signatures/custody, release, receipt, remittance, and bank reconciliation |
| Documents and custody | Versioned outputs, Records references, TracePoint packet/items/checkpoints, and disclosure classification |
| Timeline | Append-only business and technical events, corrections, supersessions, and recovery receipts |

## Timeline event contract

Each consequential event records:

| Field | Requirement |
|---|---|
| Event identity | Immutable event UUID, event type/version, occurred-at and recorded-at times |
| Case/state | Case UUID/reference, prior/new state version, phase and task effects |
| Actor | Stable user ID, display snapshot, department/role snapshot, authentication context; system events identify the service |
| Authority | Permission, evidence/decision IDs, approved exemption, and configuration/rule/template versions |
| Action/result | Plain-language summary plus structured payload with no secrets |
| Financial effect | Separate appropriation, allotment, obligation, payable, debit/credit, deduction, and cash movements with currency/fund |
| Artifact/custody | Document/output IDs and versions, checksum, TracePoint/Records references, custody before/after where applicable |
| Correlation | Request/idempotency key receipt, causation event, batch/outbox correlation, source system (`GRAND`, not eGAPS runtime) |
| Correction lineage | Returns, supersedes/superseded-by, reversal/replacement/cancellation IDs and reasons |

The UI groups technical recovery noise by default but never hides a financial or authority-changing event.

## Search contract

### Authorized object types

Finance cases, tasks, controlled numbers, appropriation/allotment/obligation records, DVs, JEVs, payment instruments, advice batches, approved parties/claimants, reports, setup releases, and safe evidence IDs.

### Matching and filters

- Exact normalized lookup for controlled numbers, UUID/display reference, evidence ID, and checksum where permitted.
- Prefix/token search for safe names and descriptions; no broad wildcard export.
- Filters: fiscal year, fund, office, transaction type, phase, responsible office, task state, exception, amount band, event date, period, output/reconciliation state.
- Dates, amounts, fund, and number type are always labeled in results.
- Result snippets come only from fields the user may view; unauthorized objects affect neither suggestions nor counts.
- Empty results explain active scope/filters and offer safe reset actions, not hidden-object hints.

Search selections survive Back navigation and can be saved as private or governed shared views. Exports require a separate permission, a bounded result set, purpose, audit receipt, and safe format.

## Notification contract

Notify on assignment/return, approaching accepted target, approval/posting/release outcome, exception, stale/conflict rejection, superseded output, reconciliation difference, period/numbering/setup gate, and recovery requiring human action. Dedupe by event + recipient + channel; record delivery status without storing message secrets. A notification title contains only safe identifiers and requires authentication to see details.

## Accessibility and responsive contract

- One `h1`, logical landmarks, visible keyboard focus, skip link, text labels for icon controls, and live-region feedback for view changes.
- Tables have captions/headers and transform into labeled cards or horizontal scroll without hiding actions on narrow screens.
- Color never carries status alone; phase/status chips include text.
- Currency and dates use locale-aware display with unambiguous accessible values.
- A 320 CSS-pixel viewport retains search, role context, next action, and primary navigation without two-dimensional page scrolling.
