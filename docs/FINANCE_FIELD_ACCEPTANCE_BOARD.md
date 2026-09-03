# Finance Field Acceptance Board

Status: **F11.8 coordination layer implemented; actual LGU field evidence and the parent F11 exit gate remain open**.

## Purpose

The Field Acceptance Board gives Finance and assigned office reviewers one readable view of the remaining local transition work. It does not create another approval checklist. Every status is calculated from the governed F10/F11 records already maintained in the selected shadow or parallel cycle. Linked F0.2 discovery decisions and exact-scope blockers are shown above the board without inflating the ten-checkpoint percentage.

The board groups those records into ten practical checkpoints:

1. redacted source and layout;
2. local cadence, procedures, and support;
3. department role exercises;
4. practical security, privacy, accessibility, performance, printing, continuity, incident, and recovery exercises;
5. the structured two-store backup and restore rehearsal;
6. exact accepted local-form lineage;
7. consecutive field-cycle qualification;
8. final cycle reconciliation;
9. named-office decisions; and
10. cutover authority and rollback.

Each checkpoint reads **Not started**, **Action needed**, or **Evidence accepted**, explains the current source record, and gives the next plain-language action. Staff then continue in the existing cycle workspace, where maker–checker permissions, immutable evidence, correction successors, and final authority rules remain enforced.

## Truthful status boundary

The percentage is a coordination aid, not a phase score, employee rating, or authority decision. It counts only the ten grouped checkpoints whose underlying governed checks currently pass. It cannot promote a form, pass an exercise, accept a field cycle, decide for a stakeholder, or authorize cutover.

Personal Internal How-To checkmarks remain private resume aids. They do not feed the board and never become attendance, competence, UAT, acceptance, or employee-evaluation evidence.

GRAND is authoritative only when the selected cycle has a separately prepared, independently authorized cutover decision for its exact scope and date. A ready board without that decision remains **Shadow/UAT only**.

The cutover-readiness calculation also requires LGU-confirmed F0 rows with retained acceptance examples for all eight detailed areas, a current independently recorded whole-scope decision whose affected scope exactly matches the cycle's enabled scope, and no current linked blocker. The board names missing areas above the ten checkpoints. No linked entry or unresolved generated starter is treated as discovery acceptance evidence.

## Access and portable export

A Finance shadow-operation user sees cycles owned by their department. A requesting-office or other stakeholder sees only cycles explicitly assigned to their account. Supplying another cycle ID does not broaden access.

The CSV export contains the selected cycle, exact enabled scope, linked discovery-decision/blocker counts, missing discovery coverage, each checkpoint state, current evidence summary, next action, and current authority flag. The browser download bytes are archived atomically under:

`department/user/finance-field-acceptance/year/month`

inside the single `GRAND_EXPORT_ROOT`, beside the SHA-256 manifest used for TraceSync whole-folder safekeeping. The export action is also retained in the append-only Finance audit history. The CSV is a status/evidence index, not an official COA/DBM form, records filing, database backup, or authority by itself.

## Modification and correction behavior

The board itself is read-only and always recalculates from current governed records. Corrections therefore follow the source workflow:

- draft plans, source versions, and exercises use their existing editable or returned states;
- submitted or accepted evidence follows independent return/rerun or successor rules;
- accepted form versions are superseded rather than overwritten;
- reconciled field cycles are corrected through a successor cycle; and
- an authorized cutover is reversed only through the retained rollback action.

This preserves the existing pre-issuance modification allowance while preventing the board from becoming a shortcut around voucher/check issuance boundaries, maker–checker review, or immutable posted history.

## Synthetic acceptance checks

- A Finance manager can select a visible cycle and see all ten groups without a false authority claim.
- A named cross-office reviewer can see and export their assigned cycle without receiving Finance preparation permissions.
- Replacing the query-string cycle ID with an unassigned cycle returns not found.
- CSV bytes are UTF-8 with familiar headings, retained in the TraceSync layout, and recorded in Finance audit history.
- No database migration or duplicated acceptance-state model is introduced.
