# Finance decisions and evidence register

Status: **F0.2 governed register, F0.3 editable coverage control, F0.4 portable department register, and F0.5 guided triage implemented; actual LGU discovery evidence and parent F0 acceptance remain open**.

## Purpose

The Finance **Decisions & evidence** workspace turns the F0 interview decision log into a governed in-app register. It is for questions that affect a named transaction type, office, fiscal year, form, output, cycle, or action. It does not replace the detailed field worksheets, copy protected source material into GRAND, or treat a public reference as automatic local authority.

Each entry uses one evidence label:

- **Observed in eGAPS** — an authorized read-only observation, limited to what was actually seen;
- **Official reference** — a reviewed COA, DBM, BIR, ordinance, bank, records, or other source that still needs an applicability decision for the exact LGU scope;
- **LGU-confirmed** — a retained accountable local decision for the named scope;
- **GRAND-implemented** — evidence of current software behavior, not proof of local acceptance; or
- **Unresolved** — authority, evidence, applicability, or agreement is still missing.

The preparer must state the question, current outcome, exact affected scope, evidence needed or why it is sufficient, owner, different reviewer, and optional due date. Protected evidence stays with its records custodian; GRAND stores a non-secret reference and custody location.

## Editable coverage starters

For a candidate shadow or parallel cycle, **Add coverage starters** creates nine ordinary drafts:

1. whole enabled-scope acceptance;
2. process steps;
3. required fields and data;
4. balances and control totals;
5. certifications and approvals;
6. signatures and accountable actors;
7. official numbers and identifiers;
8. forms, registers, reports, and other outputs; and
9. exceptions and correction paths.

These are minimum coverage areas, not a fixed LGU process. Staff edit the wording and add as many focused rows as the actual local route needs. Every starter begins **Unresolved**, blocks the cycle scope, and contains no assumed COA/DBM/local answer. Re-running the starter action creates only a missing current area.

Before an area can be submitted as **LGU-confirmed**, it needs a retained acceptance-example reference: a blank/redacted example, replay result, control total, or an accountable accepted explanation that no local case applies. Protected bytes remain outside GRAND.

## Review and correction flow

1. An authorized Finance configuration user creates the draft and may assign an owner or reviewer from another office.
2. The owner or authorized Finance preparer may edit a **Draft** or **Returned** entry.
3. Submission locks a JSON evidence snapshot and SHA-256 checksum.
4. Only the named reviewer, who cannot also be the owner, creator, or submitter, may **Record** or **Return** it with a reason.
5. A recorded Unresolved entry is valid evidence that the question remains open, but its exact affected scope remains blocked.
6. A recorded entry cannot be rewritten or deleted. When evidence or authority changes, create a reasoned successor. The predecessor remains current until the successor is independently recorded, then becomes Superseded without changing its original checksum.

This is the discovery equivalent of GRAND's modification allowance: ordinary corrections remain easy before independent recording, while accepted history uses a traceable successor instead of silent editing. Voucher/check issuance, posting, payment, and other downstream locks remain governed by their own stricter workflows.

When a cycle's cutover record leaves Draft, its linked discovery evidence is locked. A newly found issue belongs in the incident/rollback record and a successor cycle's discovery register; it cannot rewrite the evidence on which the earlier authority decision was made.

## Cutover relationship

Link relevant decisions to the exact shadow or parallel cycle they affect. A cycle cannot satisfy its cutover-readiness gate unless:

- one current, independently recorded **LGU-confirmed** F0 whole-scope decision is linked to the cycle;
- that row has an acceptance example and its affected scope exactly equals the cycle's enabled scope;
- current independently recorded LGU-confirmed rows with acceptance examples cover process step, field/data, balance/control total, certification/approval, signature/actor, number/identifier, output, and exception/correction; and
- no current linked decision has **Blocks affected scope** selected.

Therefore, an empty register is not proof that discovery is complete. A recorded Unresolved entry can accurately document a gap without blocking unrelated work, but the named affected scope cannot pass cutover until a reviewed successor clears it.

The Decisions workspace shows a 0–8 detailed-area summary per candidate cycle. The Field Acceptance Board displays missing area names, whole-scope state, and linked blocker counts outside its ten F10/F11 progress checkpoints. This keeps the coordination percentage honest while making the earlier F0 dependency visible.

## Access, guidance, and export

Finance discovery managers see their department's register. A named owner or reviewer from another office sees only entries assigned to them. Supplying another entry ID does not broaden access.

The existing register can be narrowed by candidate cycle, phase, workflow state, or one plain **Needs attention** choice: current scope blockers, awaiting named reviewer, overdue open work, or returned for correction. Cycle choices come only from records already visible to the user. Overdue dates are marked in the row. These are work-list filters, not new decisions, approvals, performance measures, or evidence states.

The Accounting-specific floating **?** guide explains the workflow in place and can be read without leaving the current page. Its personal checkmarks are private resume aids, never acceptance or employee-performance evidence.

Every visible entry can be exported as a UTF-8 CSV. A Finance discovery manager can also apply the cycle, phase, workflow-state, and attention filters and choose **Export department register**. That bulk CSV contains only the manager's assigned department and carries the same filters in its filename, manifest, and audit event; cross-office assignees keep their intentionally narrower per-record export access. Spreadsheet-formula prefixes in human-entered text are neutralized without hiding the underlying value.

The exact downloaded bytes and sibling SHA-256 manifest are archived under either:

`department/user/finance-discovery-decisions/year/month`

or, for the filtered department register:

`department/user/finance-discovery-register/year/month`

inside the single `GRAND_EXPORT_ROOT` for TraceSync whole-folder safekeeping. Each export is written to the append-only Finance audit history. These CSVs are evidence indexes, not the protected source files, Records filing, database backups, or authority. The F11 portable cutover package uses schema v9 and includes linked decision coverage areas, acceptance-example references, locked snapshots, checksums, actors, review basis, and successor lineage, while excluding protected evidence bytes and credentials.

## Acceptance boundary

Synthetic tests prove lifecycle, separation, scope blocking, access, successor, export, and cutover-gate behavior. They do not provide the implementing LGU's current sources, interviews, confirmations, custody records, or authority. F0 remains open until every enabled step, field, balance, certification, signature, number, output, and exception has adequate evidence and named-office acceptance.
