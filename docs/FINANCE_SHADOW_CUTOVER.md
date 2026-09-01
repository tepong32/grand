# Finance shadow operation, UAT acceptance, and controlled cutover

Status: F11.1 governed transition control, F11.2 versioned redacted source staging, F11.3 scheduled reconciliation/defect control, F11.4 governed curricula/support and readiness exercises, F11.5 consecutive field-cycle/signed-reference control, and F11.6 exact accepted-form lineage implemented. This workflow stores transition evidence; it does not claim that the parent F11 exit gate or any local production cutover has occurred.

## Purpose and authority boundary

The Shadow operation & cutover workspace turns the last Finance roadmap gate into an explicit, attributable process. It keeps five decisions separate:

1. Finance defines and runs a limited shadow or parallel cycle.
2. A different authorized reviewer reconciles the exact comparison evidence.
3. Finance records an approved local field-qualification rule and a different reviewer accepts the actual retained evidence for each consecutive cycle.
4. Each named requesting-office, Budget, Accounting, Treasury, IT, management, and audit reviewer accepts or rejects the same enabled scope using their own training, UAT, and retained decision-record evidence.
5. A separate cutover authority records go/no-go for the exact scope and effective date.

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

F11.1 supplies governed comparison rows and the cycle dashboard. F11.3 adds the scheduled evidence and defect lifecycle described below. Automatic production-source ingestion remains separate and optional after local source formats and operating procedures are confirmed.

## Local cadence, scheduled runs, and defect triage

Before a cycle can start, Finance prepares a human-readable local reconciliation plan containing:

- calendar-day or Monday–Friday cadence, the first due time, and a visible grace period;
- the minimum independently reviewed run count required before final cycle submission;
- the exact transaction types covered by each run;
- retained local authority and acceptance references; and
- editable Critical, High, Medium, and Low correction hours plus a named person, role, or office escalation route for each level.

The displayed starter numbers are planning defaults only. They are not represented as COA, DBM, audit, or local requirements. A different reconciliation reviewer must approve the checksum-backed plan, and the preparer/submitter cannot self-approve it. Returned controls can be corrected before cycle start; an approved plan is immutable for that cycle.

During a running cycle, Finance opens the next scheduled run. Calendar-day plans advance daily; working-day plans skip Saturday and Sunday. GRAND prevents a second run from opening while the current one is open, returned, or awaiting review. Each submitted run snapshots the current comparison rows and complete defect register into JSON-safe evidence, calculates exact matched/explained/open counts, and locks the snapshot with SHA-256.

The independent reviewer may:

- mark a zero-open-defect snapshot Independently reconciled;
- mark a snapshot Reviewed with open exceptions, keeping every defect visible; or
- return the run for a specific correction and resubmission.

An accepted exception run is evidence that the reviewer saw the defect—not evidence that the defect is resolved. The cycle cannot reach final reconciliation review until the approved plan's minimum run count is met, every opened run has an independent decision, every current comparison has no open-defect outcome, and every registered defect is independently resolved.

Each open comparison receives a separate triage record with stable code, severity, impact, owner, calculated correction due time, and the approved escalation route pinned as a snapshot. The owner or Finance manager submits a correction note and retained evidence reference. A different reconciliation reviewer accepts the resolution or reopens it. Acceptance preserves the original exception run and defect history while changing the current comparison to Explained. Escalation records who was contacted, when, and the requested action; due/overdue state is visible and no intake or escalation history can be deleted.

## Training and stakeholder acceptance

Before formal stakeholder acceptance, Finance prepares a human-readable readiness plan that references the locally accepted role curriculum register, controlled quick guides, supervisor observation/rerun runbook, named support owner, actual support channels/hours, backup contact, escalation procedure, and retained local acceptance decision. A different reconciliation reviewer must approve its checksum-backed snapshot. The preparer cannot self-approve it, and an approved plan is immutable for that cycle.

The plan's learning-privacy notice keeps the floating `?` Internal How-To separate from formal readiness evidence. Guide checkmarks remain private resume aids. GRAND does not expose their completion count or percentage in the cutover evidence package, and they cannot satisfy a role exercise, attendance, competence, performance, or acceptance gate.

Finance then schedules locally written exercises with an exact cycle scope, human-followable procedure, observable expected result, owner, different assigned witness, schedule/due time, and the approved support route pinned as a snapshot. The categories are:

- one role curriculum and synthetic job exercise for every named stakeholder acceptance row;
- security and access control;
- privacy and redaction;
- accessibility and assisted use;
- performance at the locally selected safe operating volume;
- printing, paper/form stock, and physical custody;
- backup and restore;
- business continuity; and
- incident response and support escalation.

The values, devices, volumes, forms, timings, channels, and pass conditions are deliberately editable local inputs; GRAND does not invent COA, DBM, BIR, printer, infrastructure, or response-time requirements. Only the assigned owner submits the actual result and retained redacted evidence reference. Only the different assigned witness can pass it or return it with a specific correction/rerun instruction. A returned result can be resubmitted while the earlier event remains in audit history; an independently passed exercise is immutable.

Finance assigns a separate row for each required stakeholder kind and, for a requesting office, the exact department. Only the named reviewer can decide that row. The reviewer records:

- the exact enabled scope;
- a role-specific training, exercise, attendance, or supervisor-runbook reference;
- the exact synthetic/redacted UAT scripts and results reviewed;
- Accepted, Accepted with conditions, or Not accepted; and
- every condition or rejection reason.

Accepted is blocked until that named reviewer owns an independently witnessed Passed role exercise under the approved readiness plan. Conditional or Not accepted remains available so a reviewer can record missing readiness or a failed scenario honestly. Conditional, rejected, or pending decisions block cutover. The stakeholder scope must exactly equal the reconciled cycle scope. Requesting-office reviewers must currently belong to the named office.

The stakeholder also references the retained wet-signed or otherwise locally accepted attributable decision record and enters that copy's SHA-256. GRAND stores the reference and file lock, not a signature image, and does not claim to create or validate a legal digital signature.

The floating `?` Internal How-To supports learning on the current page. Its checkmarks are private resume aids only. They are never exposed as supervisor attendance, employee performance, training readiness, or UAT acceptance. Formal training/UAT evidence is entered explicitly in the stakeholder record.

## Consecutive field-cycle qualification

For the candidate cutover cycle, Finance prepares a locally editable qualification plan containing:

- the minimum consecutive reconciled cycles, with two shown only as an editable planning starter;
- whether at least one controlled parallel run is mandatory;
- the retained local authority for that threshold;
- the accepted local rules, forms, reports, print layouts, and instructions used; and
- the retained-record basis that distinguishes actual field execution from synthetic UAT.

A narrative rules/forms reference is retained for authorities, procedures, and material outside the form register, but it cannot satisfy the form gate by itself. While the plan is Draft or Returned, Finance must select at least one exact, currently Accepted F10.2 local-form version and explain in familiar terms where staff use it. Forms may come from the Finance offices involved in the interconnected process. Submission validates the protected acceptance packet and pins the exact accepted form snapshot, department, version, source mapping, reference checksum, source checksum, and submission checksum into the plan. A different reconciliation reviewer approves or returns that complete checksum-backed plan. GRAND does not present its starter count or parallel-run setting as COA, DBM, BIR, audit, or local policy.

After approval, Finance adds each reconciled field cycle from oldest to newest. Each row references its retained field-execution packet and the accepted rules/forms actually used. At submission, the row receives its own snapshot and checksum of the plan's exact accepted-form set. A different reviewer can accept it only while every selected form is still the current Accepted F10.2 version and the form set still matches the submitted field evidence. The cutover gate requires at least the approved minimum, sequence numbers starting at 1 without gaps, an explicit predecessor link between each adjacent cycle, the candidate as the last cycle, exact Finance office/fiscal year/scope equality, no open evidence row, a controlled parallel cycle when the plan requires one, and exact current form lineage across every accepted cycle. Accepted field evidence is immutable; changed scope, execution evidence, or accepted form version belongs to a successor cycle and fresh qualification plan.

These controls cannot create the field evidence. Synthetic tests may demonstrate the software gate, but only retained actual local execution records can satisfy the operational entry fields honestly.

## Cutover record and rollback

After independent reconciliation, Finance prepares a human-readable decision record containing:

- the signed/retained authority matrix reference;
- the exact enabled scope, copied without widening from the reconciled cycle;
- cutover date and time;
- opening and in-flight transaction reconciliation reference;
- objective rollback criteria;
- historical eGAPS/current-process read-only retention plan; and
- backup, restore, recovery, and continuity exercise evidence; and
- the retained signed authority record reference, its SHA-256, and its named records/TracePoint custodian.

Submission is blocked until the field-cycle plan and consecutive-cycle chain pass, the readiness plan is approved, all eight nonfunctional categories and every named role exercise are Passed, no scheduled exercise remains planned/submitted/returned, all seven stakeholder kinds exist, every row is Accepted, and every accepted stakeholder has a retained decision reference and SHA-256. A different user with cutover authority records authorization or decline and its basis. The normal seeded roles separate preparation (`Finance Configuration Manager`) from reconciliation/authority (`Finance Configuration Approver`), and service checks still reject self-review or self-authorization if permissions were combined exceptionally.

When a recorded rollback criterion is triggered, the authority records the incident and immediate operating direction. The status becomes Rolled back; the original authorization, actor, time, reason, comparisons, and stakeholder decisions remain reconstructible.

## Modification allowance

The editable window is deliberately narrow:

- a draft cycle plan can be corrected before it starts;
- comparison rows can be added or corrected only while the cycle is Draft/Running;
- pending stakeholder assignments can be corrected before a decision;
- a draft/returned readiness plan can be corrected before approval;
- a planned or witness-returned exercise can receive a corrected/rerun actual result and evidence reference;
- a draft/returned field-qualification plan and its selected accepted-form rows can be corrected before submission/approval, and draft/returned field evidence can be corrected before independent acceptance;
- a draft cutover record can be corrected before submission.

Submitted cycle evidence, approved readiness/qualification plans, accepted field-cycle evidence, passed exercise evidence, recorded stakeholder decisions, and submitted authority fields are immutable. A returned comparison requires a successor cycle. A changed stakeholder scope or concluded decision requires a successor cycle and fresh evidence. An authorized cutover is never edited into a different scope or date; use decline before authorization or recorded rollback afterward.

This transition allowance does not reopen issued vouchers/checks or bypass their existing guided correction, cancellation/replacement, adjustment, reversal, close/reopen, or returned-payment rules.

## Access and exports

Department-bounded Finance permissions control cycle preparation, independent reconciliation, and cutover authority. A named cross-office stakeholder can read only the assigned cycle and record only their pending decision; assignment does not grant Finance preparation or authority actions. Finance UAT viewers remain read-only within their office boundary.

Every visible cycle can produce a schema-v6 JSON evidence package containing each source version's checksum, headings, row count, drift/review metadata; the approved local cadence and escalation matrix; every scheduled run snapshot/checksum; defect intake, resolution, and escalation evidence; the approved curriculum/support plan; every role and nonfunctional exercise with result/checksum/witness evidence; the qualification plan, exact accepted-form versions/checksums, and each field cycle's pinned form-set snapshot/checksum; stakeholder decision references/checksums; readiness checks; and the current cutover decision and signed-authority reference/checksum/custody. Protected form-reference bytes, source row values, retained CSV bytes, signature images, and private Internal How-To progress are deliberately excluded from the portable JSON. The downloaded bytes are also archived atomically under:

`department/user/finance-shadow-cutover/year/month`

inside the single `GRAND_EXPORT_ROOT`, beside a SHA-256 manifest for TraceSync whole-folder safekeeping. The export is portable evidence, not a Records filing, database backup, or authority by itself.

## Remaining F11 acceptance work

Before claiming the parent exit gate, the LGU still must confirm and execute:

- current locally accepted redacted source layouts and, if useful, a separately reviewed read-only adapter beyond the implemented file-staging boundary;
- actual locally accepted cadence/severity/escalation values, named support ownership, and enabled transaction-type field sign-off using the implemented controls;
- locally completed curriculum/quick-guide/supervisor/support content and actual witnessed role-exercise evidence entered through the implemented F11.4 controls;
- actual named security, privacy, accessibility, performance, print/form-stock, backup/restore, continuity, and incident exercise execution using locally accepted pass conditions;
- actual consecutive limited shadow and controlled parallel execution entered through the implemented F11.5 plan/evidence controls, with every applicable current F10.2 accepted form selected through the implemented F11.6 lineage controls; and
- actual signatures/decisions from Budget, Accounting, Treasury, every enabled requesting office, IT, management, and audit stakeholders entered through the implemented retained-reference/checksum fields.

Until those field-evidence steps and the recorded authorization exist, the roadmap's shadow/UAT label remains in force.
