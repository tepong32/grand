# GRAND implementation decision log

This is the side record for turning-point implementation decisions made during autonomous work. It supports the user's next review; it is not LGU policy approval or production acceptance. Routine edits and test output stay in the changelog and continuation notes.

## Project goal used for decisions

The [Finance roadmap](FINANCE_ROADMAP.md#product-outcome) calls for one web application with a shared transaction history and workspaces shaped around the office that owns each step. Facts should be entered once and remain traceable from request through Budget, Accounting, Treasury, reporting and close. The [project roadmap](ROADMAP.md) keeps specialized processing in its own workspace, with employee dashboards summarizing and linking to that work.

Accordingly, turning-point decisions should improve operational clarity without copying authoritative records, inventing financial authority, weakening maker-checker or office scope, or claiming that automated tests constitute LGU acceptance. Practical accessibility and recovery matter alongside functional coverage.

## Review queue

- **D-041:** Bind non-financial DV amendment to the pinned Finance owner while retaining Accounting authority after a Treasury handoff.

- **D-040:** Keep scheduled-run exceptions and qualifying-cycle evidence distinct, with personal history resolved through the controlling cycle.

- **D-039:** Restore a reasoned reference-correction route for draft/returned qualification evidence without changing qualifying-cycle lineage.

- **D-038:** Give each governed field plan its own source-aligned work identity and expose retained review integrity on the cycle screen.

- **D-037:** Preserve checksum-blocked acceptance while allowing an independently authorized, reasoned return with explicit integrity evidence.

- **D-036:** Complete local-form action parity and personal handoffs, distinguishing preparation from current witness waits and final acceptance.

- **D-035:** Project prepared stakeholder/submitted cutover handoffs and label each retained decision outcome without implying broader acceptance.

- **D-034:** Make returned field-cycle correction a linked-successor action, retaining prior evidence and using fresh source locks.

- **D-033:** Preserve separate cycle/exercise/defect handoffs and resolve retained field events through matching current source custody.

- **D-032:** Keep named cross-office field assignments, but require active non-UAT identity at every assigned-actor mutation boundary.

- **D-031:** Add accountability source-action parity before personal Waiting, preserving independent profile/package decisions and cross-office evidence recipes.

- **D-030:** Project report Waiting from creator/reviewer handoffs and completion from explicit personal events, excluding automated generation credit.

- **D-029:** Generate from persisted report/template/schedule evidence and retain failed-run recovery under the existing trusted scheduler policy.

- **D-028:** Enforce stored source authority for reporting configuration while preserving non-Finance roles and separately authorized read/export.

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
- **D-011:** Continue with payable handoffs on the existing shared voucher identity.
- **D-012:** Verify and close the signature task identity/state boundary before expanding signature projections.
- **D-013:** Match signature packet gates and map child actions back to the shared case before extending DV Waiting.
- **D-014:** Credit retained DV preparation, custody-recording and validation actions without inferring signing or payment authority.

- **D-015:** Continue personal Waiting through Accounting posting by resolving authorized source and journal actions to the same voucher case.

- **D-016:** Keep Treasury/advice Waiting tied to current instrument and batch lineage, with issuer attribution through advice.

- **D-017:** Follow physical release into required Accounting event posting without claiming premature case completion.

- **D-018:** Project returned-payment Waiting from current review versions and the established role-shaped register.

- **D-019:** Attribute returned-payment history to matching retained review-version events, including superseded versions.

- **D-020:** Describe instrument event history as physical actions, preserving required Accounting completion as a separate outcome.

- **D-021:** Project bank-reconciliation handoffs and lifecycle history under the specific bank-register read permission.

- **D-022:** Reproduce and fix the cash UAT mutation boundary before extending cash projections.
- **D-023:** Verify cash preparation and manual-resolution custody against locked stored records.
- **D-024:** Preserve Treasury ownership and cross-office review in personal cash handoffs.
- **D-025:** Apply the Finance report mutation boundary by source domain while retaining non-Finance authority.
- **D-026:** Enforce statement governance at service boundaries without changing read/export roles.
- **D-027:** Enforce package/form mutation ownership while preserving cross-office evidence and preview discovery.

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

- Date/checkpoint: 2026-09-08; implemented and verified in v0.7.20.
- Decision: Extend personal discovery Waiting using retained preparer/submitter attribution and the source's named-owner/reviewer read scope, including existing cross-office access. Completion must come from retained submission/return/recording events, never from current status alone. A recorded unresolved decision remains unresolved and scope-blocking.
- Alternatives considered: limit every discovery record to the current department; treat every assigned owner as having submitted work; label recorded discovery as local acceptance; invent submission deadlines.
- Goal fit: the shared workflow should retain office accountability and exact evidence meaning. Named cross-office participation is existing authority, not an exception to hide. A stored review target should be identified as that target, not silently reassigned as the user's deadline.
- Tradeoff: this adapter will cover discovery handoffs and recorded decisions; field-cycle and nested-record Waiting/history require their own source review. It does not modify discovery evidence locks, grants or acceptance rules.
- Evidence/status: named source access, public identifiers and retained audit actions inspected; adapters implemented; three focused tests and all 569 project tests passed.
- Revisit when: local staffing or review policy changes the source contract, or further nested handoffs are added.

### D-011 — Follow payable handoffs on the shared voucher case

- Date/checkpoint: 2026-09-08; implemented and verified in v0.7.21.
- Decision: Prioritize payable review and accepted-payable DV preparation next in personal Waiting, then credit retained payable submission/return/acceptance events. Use the existing voucher-case identity so current related actions remove Waiting before truncation.
- Alternatives considered: create a separate payable task lifecycle; call Accounting acceptance a payment approval; use the case's later current office as the historical review actor's office; jump directly to every downstream signature/bank/exception stage without auditing related-action exclusions.
- Goal fit: this fills a handoff in the core Budget-to-Accounting transaction chain while preserving one traceable case. Payable readiness and authority to release payment remain separate decisions.
- Tradeoff: the bounded first adapter ends at DV preparation; later voucher stages need explicit wet-signature, journal, advice and exception action mapping before claiming full-case Waiting. History retains the event's actor and office even after custody moves.
- Evidence/status: source submission/review transitions, canonical task identities and current workbench visibility inspected; three focused tests and all 572 project tests passed.
- Revisit when: the downstream case-action identity audit supports extending Waiting through later stages.

### D-012 — Protect recorded signature custody before projecting its next handoff

- Date/checkpoint: 2026-09-08; FIN-GAP-012 identified during v0.7.21 verification.
- Decision: Finish the independent payable milestone, then reproduce and close the signature service's caller-supplied task-state gap before extending signature Waiting/history.
- Alternatives considered: rely on the view having loaded the task; rely only on a case version; add the projection before verifying the source boundary.
- Goal fit: a single traceable transaction history depends on trustworthy recorded custody. Source locking must protect the stored task identity and prior return attribution, not just the parent case.
- Tradeoff: another targeted source fix precedes downstream dashboard coverage. It must preserve normal ordered recording, controlled-print gates and idempotency while rejecting stale/cross-case input.
- Evidence/status: service inspection and reproduction complete; five focused tests and all 577 project tests passed. No actual user-data misuse is claimed.
- Revisit when: regression proves the stored case/task boundary and normal signature flow remain correct.

D-012 scope update (v0.7.22): reproduction confirmed the three task-identity/state paths plus combined UAT/signature permission (5 tests, 4 failures). Inspection found the latter comes from the shared voucher-service mutation guard; its callers mutate case workflow, evidence or outputs. Fix that shared guard, preserving separate raw read predicates, instead of guarding only the signature function. FIN-GAP-013 records this related authority finding. Stored task identity, status, round and sequence are reloaded under the authorized case lock. Verification passed: five focused tests and all 577 project tests. No user data was used.

### D-013 — Extend DV Waiting only with exact signature-action exclusion

- Date/checkpoint: 2026-09-08; v0.7.23.
- Decision: First align the controlled-signature selector with the source-required TracePoint link (FIN-GAP-014). Then extend attributed DV handoffs through signatures and independent validation, resolving authorized child signature tasks back to their voucher case before truncation.
- Alternatives considered: exclude only actions with the same case-id prefix; regard an awaiting-signatures print job alone as a ready packet; introduce a separate authoritative DV waiting status.
- Goal fit: a user should see actionable custody work or Waiting consistently with the actual source gate. One case identity should tie its child tasks to the same traceable transaction.
- Tradeoff: this bounded slice stops before journal/advice/exception handoffs, which have their own identities. Existing non-controlled/legacy signature rules remain the source policy; no new physical-signature authority is inferred from a recording action.
- Evidence/status: the original queue/source mismatch reproduced (1 test, 1 failure, 2.110 seconds); selector repair and child identity mapping implemented. Verification: all nine focused DV tests passed in 3.594 seconds; all 579 project tests passed in 260.708 seconds. System, migration-drift, compilation and diff checks are clean. FIN-GAP-014 is verified.
- Revisit when: later handoff identities and their current source gates have been audited.

D-013 attribution/timing detail: retain intake preparer/submitter eligibility and add the current DV preparer for these DV stages. Use retained stage-transition time, excluding same-stage partial signatures; do not infer a deadline from the voucher date. Missing transition evidence remains visible. Work pauses after this checkpoint under the latest user instruction.


### D-014 — Credit retained DV actions without inferring signing or payment authority

- Date/checkpoint: 2026-09-08; v0.7.24.
- Decision: Project DV preparation/correction, ordinary partial/final signature-return recording and Accounting validation from retained VoucherEvent actor attribution and valid source transition pairs. Recheck current workbench read access; retain historical acting office after custody moves. Give repeated corrections distinct event identities.
- Alternatives considered: infer completion from the current DV preparer or terminal case state; credit signature recording as signing; require the historical acting office to equal today's case office.
- Goal fit: one traceable transaction history should show what each account actually did without erasing prior office work when custody moves. Review completion does not authorize payment release.
- Tradeoff: nonfinancial amendments, generic returns, print/packet actions and later payment stages remain separate adapters requiring their own event audit. This bounded slice does not claim complete DV history coverage.
- Evidence/status: inspected source event emission and mutation controls; implementation verified: two focused tests and all 581 project tests passed. Tests include real ordered signature service events and the existing full Budget-to-payment replay.
- Revisit when: expanding amendment, print/packet or later payment history; require explicit event meaning and current source access for each addition.


### D-015 — Follow the voucher posting handoff across both stores

- Date/checkpoint: 2026-09-08; v0.7.25.
- Decision: Keep the shared case identity while resolving already-authorized source and journal tasks across the existing default/Finance stores. Retain intake/DV authorship; an open recognition request additionally credits its requester. Stop this adapter at the next Treasury phase.
- Alternatives considered: check only case-prefixed actions; show all Accounting office cases; infer a deadline from the JEV date; create a separate task status or cross-database foreign key.
- Goal fit: one traceable transaction should remain visible to the people who handed it off, while people who can act see their real source task. Keep office boundaries, maker-checker policy and the two databases intact.
- Tradeoff: cancelled/closed request authorship alone does not confer Waiting attribution. Later payment and exception handoffs require their own stage and attribution audit.
- Evidence/status: shared source-handoff and journal authorization inspected; focused before-limit test and full service-generated Budget-to-report replay expanded. Both pass in 8.410 seconds. The initial replay failed because its one-row cap could select the legitimate journal Waiting row instead of the case; the replay now finds the case within the default view, while the dedicated cap test remains strict. All 582 project tests passed in 187.761 seconds; system, migration-drift, compilation and diff checks passed.
- Revisit when: expanding Treasury/advice/event-posting Waiting; audit all corresponding child identities first.


### D-016 — Preserve current instrument/advice lineage in personal Waiting

- Date/checkpoint: 2026-09-08; v0.7.26.
- Decision: Extend existing intake/DV contributor Waiting through Treasury preparation and bank advice. Map initial assembly and already-authorized current-batch actions to the shared case. Add the issuer of an issued/advised check during the advice phase.
- Alternatives considered: match all historical advice item memberships; let advice actions and Waiting overlap; infer issuer participation from a cancelled instrument; extend release/exception coverage without auditing its child actions.
- Goal fit: one traceable case remains visible across office handoffs without suggesting it is waiting when the account can act. Historical advice versions remain evidence, while current lineage governs the queue.
- Tradeoff: issuer-only Waiting ends on cancellation or leaving the advice phase. Release and post-release exceptions require separate coverage. Bank-advice batch Waiting may coexist with a case row because each links to a different governed source.
- Evidence/status: advice approval marks instruments advised before bank acknowledgement, so both issued/advised states retain issuer attribution. All three focused tests passed in 9.558 seconds and all 584 project tests passed in 187.754 seconds.
- Revisit when: extending release, replacement or post-release event posting; resolve their exact authorized child actions before adding Waiting.


### D-017 — Keep release and Accounting event completion distinct

- Date/checkpoint: 2026-09-08; v0.7.27.
- Decision: Extend shared-case Waiting through Treasury release and Accounting event posting. Retain active issued/advised instrument issuers during release, and current open supported event-request authors during posting. Resolve authorized returned-payment, source and journal child actions before the display cap.
- Alternatives considered: mark the case complete at physical release; infer continuing attribution from cancelled/closed requests; omit returned-payment children because their IDs differ from the case.
- Goal fit: financial facts and custody remain traceable through the ledger handoff. Staff should see the actual remaining responsibility without duplicate authoritative state or invented deadlines.
- Tradeoff: completed cases leave Waiting; event-completion history is a separate adapter. Returned-item-specific Waiting still needs its own ownership/state audit. Existing request kinds and source gates are preserved.
- Evidence/status: inspected source routing into ACCOUNTING_EVENT_POSTING and retained resume stages. Focused tests cover active requester attribution, cap ordering, issuer release visibility and returned-payment action exclusion, plus the real Budget-to-report replay. Verification: all four focused attribution/action/replay tests passed in 11.728 seconds; all 586 project tests passed in 190.924 seconds. System, migration-drift, compilation and diff checks passed. Full regression covers cross-module source/journal/returned-payment mapping; operational LGU acceptance is not claimed.
- Revisit when: adding correction/returned-item history and remaining completion adapters; require exact retained attribution and current source access.


### D-018 — Use current returned-payment review versions as handoffs

- Date/checkpoint: 2026-09-08; v0.7.28.
- Decision: Use the existing returned-payment register's current role/office read scope, retained preparer/open posting requester and consistent case/review stages. Link directly to the review anchor. Resolve current case/source/journal actions as well as review actions before truncation.
- Alternatives considered: follow all office reviews; continue showing superseded versions as Waiting; link to a broad unfiltered case list; credit any historical reviewer indefinitely.
- Goal fit: keep correction lineage and office ownership legible without inventing task state or expanding read access. A clarified successor replaces its predecessor in current Waiting while retained history remains intact.
- Tradeoff: completion history remains separate. Prepared timestamps or reviewed/posted handoff times measure age; the bank observation date is not a deadline.
- Evidence/status: source register and returned-item service transitions inspected. All three focused tests and 166 dependent My Work/voucher tests passed; full-project regression is not repeated for this isolated read-only projection under the updated repository guidance.
- Revisit when: adding completion events or changing register read policy; such changes require separate event/authority verification.


### D-019 — Preserve review-version completion evidence

- Date/checkpoint: 2026-09-08; v0.7.29.
- Decision: Credit retained submission, clarification, return and Accounting-decision events only when their review identity, case, stored preparer/reviewer, stage transition and relevant successor/outcome evidence agree. Require both current register and case read access. Retain superseded versions as historical actions.
- Alternatives considered: infer actions from closed status; use unvalidated review IDs from event metadata; hide superseded evidence; treat an Accounting decision as completed replacement or release.
- Goal fit: one traceable history should preserve who did what on each correction version without inventing authority or overwriting earlier work.
- Tradeoff: malformed or inconsistent historical evidence is excluded; no audit-history repair is inferred. Posting synchronization and instrument issuance history remain separate work. Current read loss can hide prior personal history.
- Evidence/status: inspected retained event emission and immutable review-source fields. Focused tests check malformed/cross-case metadata, actor/outcome mismatch and real superseded/successor history; all three focused tests and 168 dependent My Work/voucher tests passed.
- Revisit when: adding later posting/issuance history or exposing evidence inconsistencies through an audit repair workflow.


### D-020 — Name physical instrument actions precisely

- Date/checkpoint: 2026-09-08; v0.7.30.
- Decision: Credit retained issue/replacement/advice-handoff/cancellation/release events under current case read access. Validate instrument-bound actor, identifier, check number and replacement linkage. Label the final physical release accurately even when its legacy event name is disbursement_completed and the case enters event posting.
- Alternatives considered: infer completion from current instrument status; display the event name as a claim of final disbursement completion; credit altered instrument linkage or a different recorder.
- Goal fit: one traceable transaction should distinguish physical custody and ledger work, retaining who performed each action without implying extra authority.
- Tradeoff: later status changes remain visible separately. Inconsistent historical linkage is excluded; no repair is inferred. Posting synchronization and print/packet/amendment history remain separate adapters.
- Evidence/status: source issue/replacement reloads stored linkage under lock; source release can route into event posting. All three focused tests/replays and 169 My Work/voucher dependency tests passed.
- Revisit when: expanding posting completion or correcting legacy evidence; keep action labels and authority precise.


### D-021 — Reuse bank-reconciliation scope and immutable lifecycle events

- Date/checkpoint: 2026-09-08; v0.7.31.
- Decision: Follow own submitted reconciliation batches in Waiting; credit retained submission/return/reconciliation events in Completed. Require the specific current bank-reconciliation read permission and matching current office for both batch and event. Reuse the Accounting completion projection with bank-specific reference/period scope.
- Alternatives considered: expose bank history to every Accounting reader; infer completion from batch status; treat statement period dates as action targets; include every individual matching operation in this slice.
- Goal fit: preserve independent reconciliation review and one source history without expanding sensitive bank-register access or inventing deadlines.
- Tradeoff: detailed row matching/classification history remains in the source audit. Read loss hides personal history; returned or resubmitted current status remains distinct from earlier actions.
- Evidence/status: bank source selectors, handoff fields and event emission inspected. Tests cover office/personal visibility, specific read loss, event-office mismatch and real submission/reconciliation.
- Revisit when: a real workflow requires detailed row-action completion or different authorized historical access.


### D-022 — Verify cash mutation authority before dependent projections

- Date/checkpoint: 2026-09-08; v0.7.32.
- Decision: Reproduce FIN-GAP-015 and fix cash service entry points if the combined UAT/operational role can mutate controls. Audit all callers of the shared guard while preserving existing read/export behavior and legitimate cross-office approval.
- Alternatives considered: rely on dashboard action hiding; add more cash projections before testing the source boundary; change cross-office approval scope without evidence of a policy defect.
- Goal fit: a read-only preview role must not gain financial mutation authority through extra permissions. Source integrity takes precedence over dashboard coverage.
- Evidence/status: two isolated denial tests failed before the fix (1.762 seconds). Mutation guard and page controls now exclude UAT; all 597 project tests passed in 424.974 seconds. Existing export is a read operation with separate retained permissions and must be assessed independently.
- Revisit when: isolated regressions confirm UAT denial and normal operational paths still pass.

### D-023 — Enforce cash custody from persisted records

- Date/checkpoint: 2026-09-08; v0.7.33.
- Decision: reproduce FIN-GAP-016 before extending cash personal projections. Check preparation/manual-resolution custody after locking and reloading authoritative records if confirmed.
- Alternatives considered: trust objects supplied by current HTTP views; conflate preparation ownership with authorized cross-office review.
- Goal fit: office-owned work must retain its boundary across every service caller, including stale or altered in-memory objects.
- Tradeoff: preserve current independent review scope; no new role or workflow is introduced.
- Evidence/status: four mutation entry points inspect caller ownership before reload; policy-specific export also trusts supplied ownership. Foreign policy submission was accepted using altered in-memory ownership (1 failed denial test, 1.818 seconds). Stored-custody repair implemented; all 599 project tests passed in 370.798 seconds.
- Revisit when: regressions prove foreign ownership cannot be substituted and normal financial lifecycle remains valid.

### D-024 — Preserve cash source scope in personal handoffs

- Date/checkpoint: 2026-09-08; v0.7.34.
- Decision: project own submitted cash policies/positions and retained submission/decision events through the existing source read rules. Centralize the existing read predicate for source pages and projections; require actor-office continuity and matching policy/position event linkage for history.
- Alternatives considered: restrict all cash records to the current Treasury office, which would hide authorized independent cross-office review; infer completion from status; treat policy/as-of dates as deadlines.
- Goal fit: one source of cash evidence should preserve who prepared and reviewed each version without widening access or implying a deadline.
- Tradeoff: draft creation and instrument-exception detail history remain in source audit. Current source status is separate from historical actions; read loss hides projections.
- Evidence/status: focused cash contracts and actual lifecycle replay cover handoffs, review outcomes, UAT, office/read loss and malformed event linkage; all 17 focused tests and 179 dependent tests passed.
- Revisit when: expanding detailed exception completion or when an accepted local workflow supplies actual structured targets.

### D-025 — Apply report mutation authority by source domain

- Date/checkpoint: 2026-09-08; v0.7.35.
- Decision: require Finance operational authority for manual generation and run decisions using the stored definition's finance_ dataset namespace; retained control-gate evidence also identifies Finance decisions. UAT membership overrides Finance operational/head grants. Keep non-Finance roles, read/download permissions and trusted scheduler execution separate.
- Alternatives considered: deny all reporting mutations for UAT membership, including unrelated social-welfare roles; rely only on hidden controls; trust the caller's definition fields; alter automated schedule execution during a user-action repair.
- Goal fit: financial preview must remain read-only without weakening the shared municipal reporting platform or inventing new approvals.
- Tradeoff: related configuration, template, schedule and Finance control mutations require their own source audit (FIN-GAP-018). This checkpoint closes the named manual/run boundary only.
- Evidence/status: UAT generation and department-head review both succeeded before the fix (2 failed denial tests, 1.137 seconds). All 50 focused reporting tests and 606 project tests passed.
- Revisit when: adding a new Finance dataset namespace or governing automated execution identities; preserve source-domain classification and current stored ownership.

### D-026 — Enforce statement service authority before evidence changes

- Date/checkpoint: 2026-09-09; v0.7.36.
- Decision: use a Finance governance predicate that combines active operational identity, current stored office and the existing action permission/head rule. Apply it to mapping, note and comparison mutation services and their page controls. Reload source records before checking ownership and evidence.
- Alternatives considered: rely on view decorators; test only UAT; deny read/export access along with mutation; claim all reporting governance fixed after one service family.
- Goal fit: every financial evidence mutation must preserve accountable office ownership and independent review, regardless of caller.
- Tradeoff: starter seeding remains a trusted setup path; remaining accountability, local-form and template/schedule service families stay explicitly open under FIN-GAP-018.
- Evidence/status: three note reviews succeeded with UAT/head, foreign-office and ungranted actors before repair (1.397 seconds). All 28 focused tests and 612 project tests passed. Maker-checker tests now explicitly grant both duties before verifying self-review rejection.
- Revisit when: changing governance action roles or adding new service entry points; keep source reads and retained exports independently authorized.

- v0.7.36 continuity maintenance: archived superseded checkpoint instructions in FINANCE_CHECKPOINT_HISTORY.md and made CONTINUE.md a current handoff. Replaced its stale universal-full-suite rule with the pulled master AGENTS.md proportional-testing policy; preserved all historical evidence and external gates.

### D-027 — Preserve evidence visibility while enforcing package/form authority

- Date/checkpoint: 2026-09-09; v0.7.37.
- Decision: apply the shared Finance governance guard to accountability recipes/packages and local-form starter, test, acceptance and successor services. Check the stored owning office after reload. Preserve role-based navigation independently of mutation authority and retain separately permitted read/export access.
- Alternatives considered: trust view permissions; require every package source to belong to its assembling office; remove preview navigation when mutation rights disappear; treat a new scope denial as a business-validation error.
- Goal fit: assembling traceable inter-office evidence requires authorized source links while only accountable office actors may alter the bundle or its acceptance evidence.
- Tradeoff: starter cross-office denial is now PermissionDenied. Maker-checker fixtures explicitly grant both duties and refresh permission caches. Generic template/definition/schedule governance remains a separate open slice.
- Evidence/status: three unauthorized profile/form reviews succeeded before repair (2.699 seconds). All 31 focused tests and 622 project tests passed, including preview-navigation checks without export grants.
- Revisit when: local acceptance introduces authorized cross-office witnesses or a different package ownership policy; do not infer those rights from readable evidence.


## D-028 - Stored source authority for report configuration

- Date: 2026-09-09. Status: implemented and verified in v0.7.38.
- Decision: definition and schedule forms check current owning-office action authority, and template preflight/promotion services reload stored evidence before authorization and lifecycle validation. Finance sources exclude UAT even with head or combined grants. Finance promotion previews also require report-generation authority because they consume financial data.
- Goal: keep report preparation and official layout changes attributable to the office responsible for the shared transaction history.
- Alternatives/tradeoffs: a global reporting UAT prohibition would also remove established non-Finance roles. Domain-aware checks retain those roles and separately authorized reading/export. Service reloads preserve the existing caller refresh contract; this does not claim comprehensive concurrent template lifecycle repair.
- Evidence: four unauthorized configuration paths reproduced before repair; 65 focused and 629 project tests passed, including stored-owner checks and the authorized non-Finance preview-role promotion lifecycle.
- Revisit when: accepted local policy authorizes cross-office configuration ownership or introduces a different Finance namespace. Stored report generation evidence is tracked separately as FIN-GAP-019.


## D-029 - Persisted generation evidence and lifecycle

- Date: 2026-09-09. Status: implemented and verified in v0.7.39.
- Decision: reload manual templates before readiness checks and snapshots. Lock/reload the run before generation; retained states remain no-ops. Read schedule configuration from stored records, reject inactive schedules and lock current advancement. Preserve caller refresh behavior, idempotent ledger entries and retained failure audits for retries.
- Goal: ensure report outputs remain traceable to stored configuration and cannot rewrite retained evidence because a caller holds stale or altered objects.
- Alternatives/tradeoffs: adding end-user mutation permissions to trusted scheduler execution would change the existing automation contract. This repair preserves that contract while making persisted evidence authoritative. Generation holds the default-store run lock while rendering; Finance source reads remain in the separate store. Database transactions cannot roll back file storage, and this checkpoint does not claim an off-host concurrency/storage-failure qualification.
- Evidence: two altered-title assertions failed and a forged retry reached the mocked dataset builder before repair. All 69 focused reporting tests passed in 8.257 seconds; all 633 project tests passed in 191.264 seconds. System, migration-drift, compilation and diff checks passed.
- Revisit when: introducing queued workers, a new renderer or a stronger cross-store snapshot contract; qualify lock behavior with the deployment database before production acceptance.


## D-030 - Personal report handoffs and attributed history

- Date: 2026-09-09. Status: implemented and verified in v0.7.40.
- Decision: Waiting follows the user's generated reports through review/approval, plus their reviewed reports handed to approval, under current run-register scope. Current authorized actions exclude the run before the common display cap. Completed by me uses explicit generated/review/approve/supersede events for that account; scheduled generation and automatic supersession side effects are excluded from personal action credit.
- Goal: connect the reporting step to the same governed work history without inventing task states or mistaking a background job for an employee's completed action.
- Alternatives/tradeoffs: all visible office reports would violate the user's chosen personal Waiting scope. Report events retain an account identity but no separate historical department label; current source office/read scope is enforced without inventing a historical office snapshot. Period dates are coverage dates, not deadlines; generation/review timestamps explain elapsed handoff age.
- Evidence: All 29 focused Finance reporting tests passed in 6.530 seconds; all 184 My Work/reporting dependency tests passed on final executable source in 62.449 seconds. System, migration-drift, compilation and diff checks passed. Existing read/download and service mutation rules are unchanged.
- Revisit when: adding explicit report assignment, notifications, richer historical actor snapshots or background-worker identity. Accountability packages remain a separate adapter.


## D-031 - Accountability action parity and personal handoffs

- Date: 2026-09-09. Status: implemented and verified in v0.7.41.
- Decision: introduce current-office read selectors shared by source views and My Work. Preparation and independent review actions follow the existing profile/package permissions, editable/submitted state and maker-checker exclusions. Existing source validation and pinned checksums explain exceptions; invalid approval evidence does not hide the legitimate return action. Waiting follows own submitted versions, and completion credits explicit submitted/returned/activated-or-approved events.
- Goal: make the accountability endpoint of the financial chain visible without treating recipe activation as package approval or copying source authority into task state.
- Alternatives/tradeoffs: adding Waiting alone would omit the next person's work queue. A generic department-wide queue would ignore current grants and independent review. Approved cross-office evidence remains readable through the accepted package recipe; package mutation still belongs to its owning office. Draft/evidence selection detail and automatic predecessor supersession stay in source audit rather than being credited as additional completed decisions.
- Evidence: All 13 focused accountability tests passed in 7.533 seconds; all 188 My Work/reporting dependency tests passed in 66.194 seconds. System, migration-drift, compilation and diff checks passed. No mutation rules, schema or money calculations changed.
- Revisit when: accepted local policy changes recipe ownership, authorized reviewers or evidence disclosure; richer actor-office history still requires retained source evidence.


## D-032 - Operational identity for named field assignments

- Date: 2026-09-09. Status: implemented and verified in v0.7.42.
- Decision: a shared assignment predicate requires authenticated active non-UAT identity and the stored assigned account. Apply it to exercise owners/witnesses, defect resolution owners and stakeholder reviewers, plus source controls and task-role eligibility. Preserve the explicit owning-office manager alternative for defect resolution and separately authorized assigned read/export access.
- Goal: keep field qualification and stakeholder decisions attributable without allowing a preview or inactive identity to become an operational decision-maker.
- Alternatives/tradeoffs: requiring same-office membership would wrongly remove established cross-office owners and witnesses. A page-only fix would leave direct service calls open. The assignment remains the authority; the operational identity check is an additional mandatory boundary.
- Evidence: two unauthorized exercise actions reproduced in 1.980 seconds; All 52 focused field/My Work tests passed in 25.593 seconds; all 644 project tests passed in 196.190 seconds. System, migration-drift, compilation and diff checks passed. Tests cover all four service entry points, unchanged audit/state after denial and source control visibility.
- Revisit when: local qualification policy changes named assignment, active-account requirements or preview access; do not infer broader office authority from a named assignment.


## D-033 - Field cycle, exercise and defect handoff attribution

- Date: 2026-09-09. Status: implemented and verified in v0.7.43.
- Decision: Waiting projects own cycle reconciliation submissions, submitted exercise results and submitted defect corrections. Child records retain their existing distinct task identities and current source read scope, including named cross-office access. Completion credits explicit cycle and child submission/decision events only after matching the audit target cycle, department and retained child ID to the current record.
- Goal: show progress through qualification without mistaking an owner's submission for independent acceptance or attributing another cycle's audit evidence to the user.
- Alternatives/tradeoffs: a single cycle-level completion would hide who submitted and who independently accepted a result. Reporting every event as completion would over-credit setup/export detail. Original exercise/correction due times are not invented as new reviewer deadlines; Waiting ages from retained submission. Current source status stays separate from historical action.
- Evidence: All 36 focused field-workflow tests passed in 13.056 seconds; all 224 field/My Work/reporting dependency tests passed in 80.786 seconds. System, migration-drift, compilation and diff checks passed. No source mutations or financial calculations changed.
- Revisit when: extending reconciliation/readiness/qualification plan and run coverage, stakeholder/cutover decision history or returned-cycle successor work. These remain separate coverage items.


## D-034 - Returned field-cycle successor action

- Date: 2026-09-09. Status: implemented and verified in v0.7.44.
- Decision: add a preparation-role source action for returned cycles without a linked successor. Share it across the source register, My Work groups/Returned view and the source detail link. Prefill only the predecessor on the existing new-cycle form; the user supplies the new plan and stages fresh source evidence. Once a successor exists, the old preparation action disappears while its returned record remains.
- Goal: make the prescribed correction path discoverable without editing rejected evidence or treating the previous cycle dates as the new cycle's deadline.
- Alternatives/tradeoffs: reopening the returned cycle would blur retained evidence; leaving it only in oversight would hide the preparer's next step. The shortcut preserves the existing form's current-office predecessor choices and does not introduce a new mutation rule or automatically copy authority/source locks.
- Evidence: All 38 focused field tests passed in 14.222 seconds; all 117 field/My Work/operations dependency tests passed in 60.348 seconds. System, migration-drift, compilation and diff checks passed.
- Revisit when: local procedure requires explicit branching or a separate approved successor authorization. Existing linked cycles remain visible as historical evidence.


## D-035 - Stakeholder and cutover decision attribution

- Date: 2026-09-09. Status: implemented and verified in v0.7.45.
- Decision: Waiting follows stakeholder records the user prepared once the source cycle is reconciled, and cutover authority records they prepared/submitted. Current exact actions remain excluded. Completion resolves the retained acceptance/decision child ID under its matching cycle and labels conditional, rejected, authorized, declined and rolled-back events explicitly.
- Goal: show who owns the last governance steps while keeping partial acceptance, technical qualification and actual cutover authority distinct.
- Alternatives/tradeoffs: a generic approved/completed label would misrepresent conditions or rejection. Stakeholder Waiting starts when both the record exists and reconciliation opens its decision gate; the cutover effective date does not become an invented approval deadline. Recorded synthetic test decisions do not establish real LGU acceptance or production readiness.
- Evidence: All 39 focused field tests passed in 20.003 seconds; all 118 field/My Work/operations dependency tests passed in 63.530 seconds. System, migration-drift, compilation and diff checks passed. No decision services or authority rules changed.
- Revisit when: changing accepted stakeholder routes, conditional-acceptance policy or cutover governance; retain the independent source gates and exact recorded scope.


## D-036 - Local-form preparation, witnesses and personal handoffs

- Date: 2026-09-09. Status: implemented and verified in v0.7.46.
- Decision: finish the existing local-form action family before expanding the remaining field-plan families. Reproduce and repair misleading witness queues and missing submission/preparation actions. Keep source validation unchanged for acceptance, adding a read-only distinction between real preparation errors and only pending witnesses. Waiting follows own current test submissions and form acceptance submissions; completion resolves form/category/attempt identity, evidence checksum and attributed actor before crediting a test event.
- Goal: make locally accepted output forms a continuous governed workflow from preparation through practical tests and independent acceptance, without equating a submitted test with a witnessed pass.
- Alternatives/tradeoffs: a generic preparation row would hide all witness waits; a generic completion row would blur test failure, pass and form acceptance. Obsolete test attempts remain in retained history but no longer count as required current witness work. Source task revisions now reflect test-state changes within a form version.
- Evidence: both source/queue mismatches reproduced (2 failures, 1.267 seconds); All 26 focused local-form tests passed in 26.042 seconds; all 200 reporting/My Work/operations dependency tests passed in 183.489 seconds. System, migration-drift, compilation and diff checks passed. A Python 3.11 multiline f-string syntax error in the first static check was corrected before tests were started.
- Revisit when: local policy changes required test categories, witness roles or accepted form routes. The remaining field plans/runs and detailed transaction history stay explicitly open.


## D-037 - Field integrity failures and governed negative decisions

- Date: 2026-09-09. Status: implemented and verified in v0.7.47.
- Decision: resolve detected checksum mismatch recovery before adding remaining field-plan work projections. Keep positive acceptance blocked on a mismatch. Permit the existing independent reviewer or assigned witness to return a still-pending record with a reason, retaining the stored digest, recomputed digest and mismatch in the new audit event. Existing submission events remain unchanged.
- Goal: make recovery from a detected integrity failure explicit and traceable, without turning a negative decision into approval of changed evidence or requiring direct status edits.
- Alternatives/tradeoffs: silently resetting the digest hides the discrepancy; blocking both decisions leaves the source's own return instruction unusable. Ordinary model immutability, reviewer authority, maker-checker, UAT exclusion and required reasons remain in force. The planned change does not bypass structural model validation; invalid relations or unparseable source data still require controlled investigation.
- Evidence: seven paths reproduced blocked returns in 2.738 seconds. All 112 focused field/My Work tests passed in 65.532 seconds; all 657 project tests passed in 239.539 seconds. System, migration-drift, compilation and diff checks passed. Positive approval, unauthorized return, self-review and missing reason are checked separately from the intended negative decision.
- Revisit when: introducing a dedicated integrity-incident process or changing local correction authority. A returned cycle continues through a successor; plans and tests continue through their existing permitted correction/rerun paths.


## D-038 - Separate field-plan handoffs and inspectable review history

- Date: 2026-09-09. Status: implemented and verified in v0.7.48.
- Decision: reconciliation, readiness/support and qualification plans have distinct preparation/review actions, personal submission Waiting and attributed submission/approval/return history. Source register filters and My Work share the same selectors, independent creator/submitter exclusions and acting-office authority. Cycle execution work remains a separate identity.
- Goal: make the owning office's next governance step visible without implying that a submitted plan completes the cycle or its actual field acceptance.
- Alternatives/tradeoffs: a single cycle task cannot distinguish simultaneous plan reviews; copying plan status into a task store would create competing authority. Plan dates do not become review deadlines. Returned age uses the retained matching plan event, with missing evidence disclosed. A cycle screen now shows the latest 20 integrity-backed reviews and their stored/observed digests; earlier audit history remains retained and older reviews without this metadata are not retroactively certified.
- Evidence: All 43 focused field tests passed in 33.763 seconds; all 122 field/My Work/operations dependency tests passed in 95.255 seconds. System, migration-drift, compilation and diff checks passed. An initial focused run was stopped after spotting a missing default in the new test-helper call; the helper was corrected before restarting tests.
- Revisit when: local policy adds assignment, explicit deadlines or governed plan successors. Scheduled reconciliation runs and qualification-cycle evidence remain the next separate child families.


## D-039 - Qualification evidence reference correction

- Date: 2026-09-09. Status: implemented and verified in v0.7.49.
- Decision: allow existing draft/returned evidence to correct execution and rules/forms references through a service that reloads and locks the stored record, checks the owning qualification plan's office and management authority, requires a reason, and records before/after evidence. Keep cycle, plan, sequence and preparer fixed. Submitted/accepted evidence stays locked; new acceptance requires a fresh submission.
- Goal: make a reviewer's requested reference correction achievable without duplicate rows, direct database edits or silent replacement of the qualifying cycle.
- Alternatives/tradeoffs: recreating the row collides with its retained plan/cycle identity; editing every model field would blur actual cycle reruns with clerical reference corrections. Wrong-cycle/sequence changes and real reruns remain governed separately; this route is deliberately limited to evidence references.
- Evidence: two source-link failures reproduced in 3.552 seconds. All 46 focused field tests passed in 38.724 seconds; all 662 project tests passed in 273.285 seconds. System, migration-drift, compilation and diff checks passed.
- Revisit when: adding explicit cycle replacement or withdrawal policy. Preserve the old submitted snapshots and the independent reviewer requirement.


## D-040 - Scheduled runs and qualifying-cycle handoffs

- Date: 2026-09-09. Status: implemented and verified in v0.7.50.
- Decision: add shared source selectors and distinct personal actions/Waiting/history for scheduled reconciliation runs and qualification evidence. Qualification authority, routes and audit custody resolve through the qualification plan's cycle; the observed cycle stays a separate evidence identity. Run review retains its existing submitter exclusion, while qualification review excludes both preparer and submitter. Opening a scheduled run is attributed separately from submitting its evidence.
- Goal: show the actual owning office and next step while preserving exact qualifying-cycle lineage and the distinction between a reconciled run and one reviewed with open exceptions.
- Alternatives/tradeoffs: flattening these records into the cycle hides simultaneous work and risks attributing evidence to the wrong parent. Scheduled-run targets remain the original plan date plus configured grace in actionable rows; returns do not extend them. Waiting age follows retained submission without inventing another approval deadline. The source panel adds before/after reference corrections alongside integrity-backed reviews.
- Evidence: All 48 focused field tests passed in 41.326 seconds; all 127 field/My Work/operations dependency tests passed in 94.146 seconds. System, migration-drift, compilation and diff checks passed.
- Revisit when: changing schedule policy, qualifying-cycle replacement or review separation; preserve existing source authority before changing task selection.


## D-041 - DV amendment office ownership after Accounting posting

- Date: 2026-09-09. Status: implemented and verified in v0.7.51.
- Decision: require the explicit amendment permission, active non-UAT identity and membership in the office on the stored case's pinned Finance Setup release. Recheck the stored case before returning even an idempotent amendment result. Share the rule with the source control. Preserve the existing allowed stages and pre-instrument cutoff, including legitimate Accounting amendment after Treasury handoff.
- Goal: keep each fact under its owning Finance office and preserve immutable financial/posting evidence while permitting the existing controlled date/signatory correction workflow.
- Alternatives/tradeoffs: requiring current custody would block the established Accounting-to-Treasury amendment test; accepting a generic grant from every office lacks an object boundary. This default follows the pinned Finance owner, not the current department of a historical employee. It does not create a cross-office delegation policy or claim LGU policy acceptance.
- Evidence: two denial assertions failed in 3.461 seconds before repair. All 69 focused voucher-workflow tests passed in 42.735 seconds; all 668 project tests passed in 272.103 seconds. System, migration-drift, compilation and diff checks passed. Existing post-JEV amendment replay is the compatibility contract for owning Accounting authority; wrong-office, UAT, stale caller, idempotent replay and unchanged financial evidence were verified.
- Revisit when: an implementing LGU explicitly delegates this correction to another office; represent that delegation as governed source scope rather than widening a global permission.
