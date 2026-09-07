# GRAND implementation decision log

This is the side record for turning-point implementation decisions made during autonomous work. It supports the user's next review; it is not LGU policy approval or production acceptance. Routine edits and test output stay in the changelog and continuation notes.

## Project goal used for decisions

The [Finance roadmap](FINANCE_ROADMAP.md#product-outcome) calls for one web application with a shared transaction history and workspaces shaped around the office that owns each step. Facts should be entered once and remain traceable from request through Budget, Accounting, Treasury, reporting and close. The [project roadmap](ROADMAP.md) keeps specialized processing in its own workspace, with employee dashboards summarizing and linking to that work.

Accordingly, turning-point decisions should improve operational clarity without copying authoritative records, inventing financial authority, weakening maker-checker or office scope, or claiming that automated tests constitute LGU acceptance. Practical accessibility and recovery matter alongside functional coverage.

## Review queue

- **D-001:** Continue My Work as a projection of governed source records, including attributed history. No new parallel task status.
- **D-002:** Preserve established cross-office Treasury bank-submission access when extending history.
- **D-003:** Keep portable export permission explicitly administrator-assigned, as the user chose; the 100-row cap is a bounded initial implementation.
- **D-004:** Keep engineering progress separate from the production/operational acceptance gate.

### D-001 — Retained events determine personal completion

- Date/checkpoint: 2026-09-07; v0.7.10–v0.7.12 implemented; payment-handoff extension verified in v0.7.14.
- Decision: A completed row represents a successful retained action attributed to the signed-in account. It links to the existing source and shows that source's current status separately. Repeated submissions remain separate events. Creating or preparing a record does not credit another person's later approval or release.
- Alternatives considered: infer completion from terminal source status; store a second task-completion status.
- Goal fit: preserves one shared transaction history and makes accountability legible without duplicate encoding or competing states.
- Tradeoff: sources without adequate actor/event evidence remain outside completion coverage until an explicit adapter is supported. A current permission loss can hide historical rows.
- Evidence/status: Accounting and Budget history passed the v0.7.12 full suite (549 tests). Verification: both focused payment-handoff tests passed in 3.328 seconds; all 553 project tests passed on the final source in 147.078 seconds. System, migration-drift, compilation and diff checks are clean.
- Revisit when: an actual office workflow needs an additional attributable action or a separately authorized audit-history view. No policy approval is assumed.

### D-002 — Preserve the Accounting-to-Treasury bank handoff

- Date/checkpoint: 2026-09-07; v0.7.14 verified.
- Decision: Advice history follows the existing source read scope. Treasury's explicitly authorized bank submission may cross the Accounting ownership boundary. Other advice decisions retain the Accounting-office boundary; remittance review and release retain their respective Accounting/Treasury offices.
- Alternatives considered: restrict every history row to the actor's current office; allow every office-visible event in personal completion.
- Goal fit: respects which office owns each operational step while retaining the single shared source record. Personal history still requires the event actor to be the signed-in user.
- Tradeoff: access follows current source permissions, so a role or office change may remove rows. This is an implementation of existing source authority, not a new delegation rule.
- Evidence/status: the existing bank-advice and remittance source scopes were inspected. Verification: both focused payment-handoff tests passed in 3.328 seconds; all 553 project tests passed on the final source in 147.078 seconds. System, migration-drift, compilation and diff checks are clean.
- Revisit when: LGU-confirmed bank-channel or office responsibilities change; update the authoritative workflow and projection together.

### D-003 — Explicit export grants and a bounded snapshot

- Date/checkpoint: 2026-09-07; v0.7.13 pushed as `abfe160`.
- Decision: Per the user's explicit choice, administrators grant `finance.export_finance_work` to selected users or groups. Operational role seeding does not grant it automatically. Export regenerates the chosen view under current access, includes up to 100 rows, and records eligible count/truncation with source IDs, checksum manifest and audit receipt.
- Alternatives considered: give every operational Finance role export access; export every visible record without a cap.
- Goal fit: enables portable, traceable office work while retaining least privilege and a clear relationship to the displayed source projection.
- Tradeoff: a snapshot over 100 eligible rows is incomplete and explicitly marked. This is not a bulk operational register or approved official form.
- Evidence/status: 551 project tests passed, including grant/revocation, UAT, scope/filter parity, truncation, formula escaping and persistence failures. Desktop and 320px layout checks passed.
- Revisit when: a demonstrated business use needs larger/filterable exports; define that bounded use and verify performance before expanding. Migration 0020 and an explicit grant are required at deployment.

### D-004 — Continue functional work without declaring production readiness

- Date/checkpoint: 2026-09-07; continuing constraint from the user's scrutiny instructions and canonical roadmap.
- Decision: Continue tested, versioned functional milestones. Reproduce and verify critical dependent defects before advancing affected work. The full post-Finance operational scrutiny remains after functional completion, followed by required named-office/local acceptance.
- Alternative considered: treat a green software suite or UI preview as acceptance of the operational process.
- Goal fit: GRAND's destination is accountable end-to-end LGU operation, not merely matching screens or menu names.
- Tradeoff: software progress does not remove external evidence, form, bank, restore, training or sign-off requirements.
- Evidence/status: see [operational scrutiny](FINANCE_OPERATIONAL_SCRUTINY.md), [gap register](FINANCE_GAP_REGISTER.md), and [completion audit](FINANCE_ROADMAP_COMPLETION_AUDIT.md). Production remains NO-GO.
- Revisit when: required real-world evidence and authorized decisions are available; never infer them from code tests.
