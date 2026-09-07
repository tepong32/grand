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
- **D-005:** Carry personal Waiting through released remittance posting, excluding current related source/journal actions.
- **D-006:** Fix the setup UAT mutation boundary before expanding setup projections.
- **D-007:** Make the advertised pre-approval setup correction path usable before adding more setup dashboard coverage.
- **D-008:** Extend setup handoff views from current source state and retained attribution, including existing governed exemptions.
- **D-009:** Attribute setup completion only to retained release transition events.
- **D-010:** Preserve named cross-office discovery access and the distinction between recorded evidence and accepted scope.

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


### D-005 — Follow the existing remittance posting handoff in Waiting

- Date/checkpoint: 2026-09-07; v0.7.15 verified.
- Decision: Keep a contributor's released remittance in Waiting while its source status is Accounting posting. Use the retained release time, not the document date. A releaser qualifies because release creates the Accounting posting request with that actor as `requested_by`. Resolve related posting-request and journal identities so any current action for the user removes the parent from Waiting before display truncation.
- Alternatives considered: stop Waiting at release; infer completion from cash release; ignore related child-record actions because their IDs differ from the batch.
- Goal fit: follows the same case through departmental handoffs and distinguishes cash payment from Accounting completion without inventing a parallel state or duplicating records.
- Tradeoff: the Waiting row uses the source's named Accounting posting queue, not undisclosed journal details or a newly inferred assignment/deadline. Source permission still controls visibility.
- Evidence/status: release service explicitly creates the linked Accounting request. Verification: both focused remittance Waiting tests passed in 5.368 seconds; all 555 project tests passed on the final source in 139.218 seconds. System, migration-drift, compilation and diff checks are clean.
- Revisit when: the source introduces a separately governed posting exception or assignment; use that retained authority rather than infer it in My Work.


### D-006 — Prioritize the setup UAT authority gap over dependent features

- Date/checkpoint: 2026-09-08; identified during v0.7.15 review and verified in v0.7.16.
- Decision: Reproduce and close FIN-GAP-009 before implementing setup Waiting. Continue the independent remittance checkpoint through its existing test gate.
- Alternatives considered: rely on hidden UAT buttons; add the new setup projection before addressing source authority.
- Goal fit: least privilege and a trustworthy governed source are prerequisites for a useful office dashboard. Preview access must not silently become operational authority through combined groups.
- Tradeoff: this inserts a corrective milestone ahead of further visible coverage. It does not change local approval policy or remove governed exemptions for normal authorized actors.
- Evidence/status: the shared setup action helpers lacked UAT exclusion; direct mutation reproduction confirmed the gap and v0.7.16 verification passed. No actual misuse is asserted.
- Revisit when: the finding is reproduced, fixed and regressed; then resume setup coverage.

D-006 update (2026-09-08): isolated reproduction confirmed all three setup mutations were accepted for the UAT actor (1 test, 3 failures). The same helper pattern is also used by shadow and discovery control mutations. The repair therefore centralizes the active, authenticated, non-UAT mutation boundary for that helper family and for named discovery actions, preserving separate preview reads and ordinary governed exemptions. FIN-GAP-009 is verified: all 20 focused Finance control tests passed in 3.225 seconds; all 557 project tests passed on the final source in 144.110 seconds. System, migration-drift, compilation and diff checks are clean.


### D-007 — Prefer a usable governed correction path over misleading review guidance

- Date/checkpoint: 2026-09-08; FIN-GAP-010 reproduced, implemented and verified in v0.7.17.
- Decision: After the UAT authority fix, address the missing pre-approval setup return/correction flow. It must retain a reviewer reason and correction evidence, allow resubmission, and preserve the lock on approved/active records.
- Alternatives considered: remove the words "or return" and leave no correction handoff; add a return button without a usable correction path; unlock approved data.
- Goal fit: the end-to-end office workflow must handle corrections safely and clearly, rather than strand staff on an approval screen or require silent administrative edits.
- Tradeoff: source correction work precedes additional setup Waiting coverage. The bounded implementation must be tested through return, correction, resubmission and independent approval; broader edit capabilities are not assumed.
- Evidence/status: original source rejected return with `Unsupported finance release action` (isolated test, 1 error). The return/correction implementation, 24 focused tests and 561 full project tests pass.
- Revisit when: additional locally evidenced correction cases require their own guided source changes; preserve version and audit lineage.

D-007 implementation choice (v0.7.17, verified): use a reasoned return from submitted to draft, retaining the previous submission attribution and immutable return event. Only an independent approver can return; the existing self-approval exemption does not imply self-return authority. Submitted child records return to draft together. Workbook correction retains the previous file under its original storage path and records before/after checksums; fresh preflight is mandatory. Release-first row locks coordinate correction/preflight with review. Approved/active records remain locked. This covers workbook replacement and missing preflight, not arbitrary edits to every setup master record. A failed database transaction can leave an unreferenced replacement file in storage; it cannot commit the correction without its audit event. Evidence retention/cleanup is deliberately separate from this source correction flow.

### D-008 — Keep setup handoffs aligned with current source authority

- Date/checkpoint: 2026-09-08; implemented and verified in v0.7.18.
- Decision: Start setup Waiting with submitted releases the user prepared/submitted. Project Returned only for current drafts with a retained return event; resubmission removes that label. Resolve stable source identities and filter actual actions before the display cap.
- Alternatives considered: all office submissions; a separate persisted task status; treating effective dates as submission deadlines; ignoring an already authorized self-approval exemption.
- Goal fit: the dashboard should explain the authoritative office workflow without duplicating its state or inventing timing/authority. Existing exemptions must remain explicit and governed, never automatically granted.
- Tradeoff: approved/scheduled release waiting and broader source completion remain subsequent coverage. The existing setup review selector excludes all preparers, even when an active exemption permits source approval; align this selector before relying on it for Waiting exclusion, and distinguish approval under exemption from independent return.
- Evidence/status: source review, selector alignment and projections implemented; four focused tests and all 564 project tests passed. No permission grants or exemption changes are authorized by this projection work.
- Revisit when: later lifecycle coverage or local operating evidence calls for additional handoff projections.

D-007 verification note: the first full run exposed two synthetic fixtures that preflighted templates under already-active releases. They now preflight during draft fixture construction before synthetic activation. The stricter current-parent-state check remains in place; the final full run passed all 561 tests in 143.087 seconds.

### D-009 — Attribute setup completion to recorded release actions

- Date/checkpoint: 2026-09-08; implemented and verified in v0.7.19.
- Decision: Extend Completed by me to retained setup submission, return, approval, scheduling, activation, rollback and retirement events attributed to the signed-in account. Recheck current source read scope and event/target/office consistency.
- Alternatives considered: infer completion from current release status; credit the creator for every later approval; count every draft edit as a completed handoff.
- Goal fit: one traceable history should distinguish who performed an action from what state the release is in today. Stable event identity preserves repeated submissions and corrections.
- Tradeoff: this first setup history adapter covers release transitions; detailed template/preflight and other setup child actions remain later coverage. It does not confer new authority or claim production readiness.
- Evidence/status: source audit events and transition actions inspected; the adapter is implemented; both focused tests and all 566 project tests passed.
- Revisit when: additional operational actions have reliable retained attribution and a clear current source read boundary.

### D-010 — Preserve named discovery custody and evidence meaning

- Date/checkpoint: 2026-09-08; planned after v0.7.19 verification.
- Decision: Extend personal discovery Waiting using retained preparer/submitter attribution and the source's named-owner/reviewer read scope, including existing cross-office access. Completion must come from retained submission/return/recording events, never from current status alone. A recorded unresolved decision remains unresolved and scope-blocking.
- Alternatives considered: limit every discovery record to the current department; treat every assigned owner as having submitted work; label recorded discovery as local acceptance; invent submission deadlines.
- Goal fit: the shared workflow should retain office accountability and exact evidence meaning. Named cross-office participation is existing authority, not an exception to hide. A stored review target should be identified as that target, not silently reassigned as the user's deadline.
- Tradeoff: this adapter will cover discovery handoffs and recorded decisions; field-cycle and nested-record Waiting/history require their own source review. It does not modify discovery evidence locks, grants or acceptance rules.
- Evidence/status: named source access, public identifiers and retained audit actions inspected; implementation and verification pending.
- Revisit when: local staffing or review policy changes the source contract, or further nested handoffs are added.
