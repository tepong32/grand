# Finance shadow operation, UAT acceptance, and controlled cutover

Status: F11.1 governed transition control and F11.2 versioned redacted source staging implemented. This workflow stores transition evidence; it does not claim that the parent F11 exit gate or any local production cutover has occurred.

## Purpose and authority boundary

The Shadow operation & cutover workspace turns the last Finance roadmap gate into an explicit, attributable process. It keeps four decisions separate:

1. Finance defines and runs a limited shadow or parallel cycle.
2. A different authorized reviewer reconciles the exact comparison evidence.
3. Each named requesting-office, Budget, Accounting, Treasury, IT, management, and audit reviewer accepts or rejects the same enabled scope using their own training and UAT evidence.
4. A separate cutover authority records go/no-go for the exact scope and effective date.

A draft, running, submitted, or reconciled cycle does not make GRAND authoritative. Configuration activation, successful screens, balanced reports, a completed tutorial, or an exported package also do not imply cutover. `FinanceCutoverDecision.status = authorized` is the implemented authority marker, limited to its recorded scope and time. A recorded rollback removes current authority without erasing the earlier decision.

Public COA/DBM/BIR sources remain requirements or recommendations only within their actual scope and effectivity. The cycle and stakeholder references must identify the reviewed local applicability, current process evidence, accepted forms, and named-office decisions; GRAND does not infer them from a public memo.

## Cycle preparation and source drift

The Finance Configuration Manager records the limited cycle and source custody reference, then chooses one of two source-lock paths:

- a readable cycle code/title, fiscal year, limited shadow or controlled parallel mode, dates, and exact enabled scope;
- the current locally authoritative process/source label;
- a retained redacted/read-only extract, register, or records-packet reference—never production credentials or an unredacted database upload;
- an optional predecessor when a returned or failed cycle must be corrected.

The normal, less-technical path accepts a UTF-8 redacted CSV up to 5 MB. GRAND calculates the exact file SHA-256, normalizes and retains only the headings as inspection evidence, counts non-empty data rows, and calculates the ordered column-layout SHA-256. It retains the redacted file as evidence but never executes it or imports its rows into operational Finance tables. Headings commonly associated with names, contact details, TINs, or account identifiers produce a visible reminder; the preparer must always confirm and describe redaction because a heading check cannot prove a file is safe.

An advanced external-lock path remains available when approved custody requires the source file to stay outside GRAND. The preparer enters externally calculated file and layout SHA-256 values plus the redaction/custody note. This path is explicit and is not presented as an automatic adapter.

Every pre-start replacement becomes a new retained version and requires a plain-language reason. The predecessor cycle's layout lock is the primary drift baseline; when no predecessor exists, a replacement is compared with the prior draft version. Matching or first-baseline layouts need no separate drift decision. A changed layout blocks cycle start until a different user with reconciliation-review authority accepts it with a mapping basis. Rejection also blocks start and requires a corrected source version. Once a cycle starts, source versions are locked and a changed extract belongs in a successor cycle.

F11.2 does not connect to, parse, or synchronize an eGAPS production database. Historical eGAPS/current-process retention remains read-only and independent from GRAND runtime operation.

## Comparisons and defect handling

During a running cycle, Finance can add case, batch, period, register, ledger, and report controls. Each row carries the two source references, comparable amount and/or count, calculated differences, outcome, retained evidence, and an owner for unresolved defects.

- `Matched exactly` requires every entered amount and count difference to be zero.
- `Difference explained` requires a plain-language explanation and remains visible to the independent reviewer.
- `Open defect` requires both an explanation and owner and blocks submission.

Submission recomputes each row, rejects open defects, serializes the complete evidence payload, and stores its SHA-256 checksum. The independent reviewer cannot be the submitter and cannot accept changed evidence. A returned submitted cycle stays retained; corrections are made in a successor rather than rewriting the reviewed snapshot.

F11.1 supplies governed comparison rows and a cycle dashboard. Automatic source adapters, scheduled daily ingestion/reconciliation, richer defect queues and service-level escalation remain parent-F11 work after local source formats and operating procedures are confirmed.

## Training and stakeholder acceptance

Finance assigns a separate row for each required stakeholder kind and, for a requesting office, the exact department. Only the named reviewer can decide that row. The reviewer records:

- the exact enabled scope;
- a role-specific training, exercise, attendance, or supervisor-runbook reference;
- the exact synthetic/redacted UAT scripts and results reviewed;
- Accepted, Accepted with conditions, or Not accepted; and
- every condition or rejection reason.

Conditional, rejected, or pending decisions block cutover. The stakeholder scope must exactly equal the reconciled cycle scope. Requesting-office reviewers must currently belong to the named office.

The floating `?` Internal How-To supports learning on the current page. Its checkmarks are private resume aids only. They are never exposed as supervisor attendance, employee performance, training readiness, or UAT acceptance. Formal training/UAT evidence is entered explicitly in the stakeholder record.

## Cutover record and rollback

After independent reconciliation, Finance prepares a human-readable decision record containing:

- the signed/retained authority matrix reference;
- the exact enabled scope, copied without widening from the reconciled cycle;
- cutover date and time;
- opening and in-flight transaction reconciliation reference;
- objective rollback criteria;
- historical eGAPS/current-process read-only retention plan; and
- backup, restore, recovery, and continuity exercise evidence.

Submission is blocked until all seven stakeholder kinds exist and every row is Accepted. A different user with cutover authority records authorization or decline and its basis. The normal seeded roles separate preparation (`Finance Configuration Manager`) from reconciliation/authority (`Finance Configuration Approver`), and service checks still reject self-review or self-authorization if permissions were combined exceptionally.

When a recorded rollback criterion is triggered, the authority records the incident and immediate operating direction. The status becomes Rolled back; the original authorization, actor, time, reason, comparisons, and stakeholder decisions remain reconstructible.

## Modification allowance

The editable window is deliberately narrow:

- a draft cycle plan can be corrected before it starts;
- comparison rows can be added or corrected only while the cycle is Draft/Running;
- pending stakeholder assignments can be corrected before a decision;
- a draft cutover record can be corrected before submission.

Submitted cycle evidence, recorded stakeholder decisions, and submitted authority fields are immutable. A returned comparison requires a successor cycle. A changed stakeholder scope or concluded decision requires a successor cycle and fresh evidence. An authorized cutover is never edited into a different scope or date; use decline before authorization or recorded rollback afterward.

This transition allowance does not reopen issued vouchers/checks or bypass their existing guided correction, cancellation/replacement, adjustment, reversal, close/reopen, or returned-payment rules.

## Access and exports

Department-bounded Finance permissions control cycle preparation, independent reconciliation, and cutover authority. A named cross-office stakeholder can read only the assigned cycle and record only their pending decision; assignment does not grant Finance preparation or authority actions. Finance UAT viewers remain read-only within their office boundary.

Every visible cycle can produce a JSON evidence package containing each source version's checksum, headings, row count, drift/review metadata, comparisons, stored/computed evidence checksums, stakeholder decisions, readiness checks, and current cutover decision. Source row values and the retained CSV bytes are deliberately excluded from the portable JSON. The downloaded bytes are also archived atomically under:

`department/user/finance-shadow-cutover/year/month`

inside the single `GRAND_EXPORT_ROOT`, beside a SHA-256 manifest for TraceSync whole-folder safekeeping. The export is portable evidence, not a Records filing, database backup, or authority by itself.

## Remaining F11 acceptance work

Before claiming the parent exit gate, the LGU still must confirm and execute:

- current locally accepted redacted source layouts and, if useful, a separately reviewed read-only adapter beyond the implemented file-staging boundary;
- daily reconciliation cadence, defect severity/escalation rules, and enabled transaction-type sign-off;
- complete role curricula, quick guides, supervisor/support runbooks, and actual attendance/exercise evidence;
- named security, privacy, accessibility, performance, print/form-stock, backup/restore, continuity, and incident exercises;
- consecutive limited shadow and controlled parallel cycles using accepted local rules/forms; and
- actual signatures/decisions from Budget, Accounting, Treasury, every enabled requesting office, IT, management, and audit stakeholders.

Until those field-evidence steps and the recorded authorization exist, the roadmap's shadow/UAT label remains in force.
