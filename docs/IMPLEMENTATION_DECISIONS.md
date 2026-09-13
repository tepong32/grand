# GRAND implementation decision log

This is the side record for turning-point implementation decisions made during autonomous work. It supports the user's next review; it is not LGU policy approval or production acceptance. Routine edits and test output stay in the changelog and continuation notes.

## Project goal used for decisions

The [Finance roadmap](FINANCE_ROADMAP.md#product-outcome) calls for one web application with a shared transaction history and workspaces shaped around the office that owns each step. Facts should be entered once and remain traceable from request through Budget, Accounting, Treasury, reporting and close. The [project roadmap](ROADMAP.md) keeps specialized processing in its own workspace, with employee dashboards summarizing and linking to that work.

Accordingly, turning-point decisions should improve operational clarity without copying authoritative records, inventing financial authority, weakening maker-checker or office scope, or claiming that automated tests constitute LGU acceptance. Practical accessibility and recovery matter alongside functional coverage.

## Review queue

- **D-083:** Correct an incorrectly posted receipt through a separately reviewed exact reversal, preserve its original history and protect every downstream withholding boundary.

- **D-082:** Record actual remittance receipts as independently reviewed explicit original-liability allocations; preserve the outward batch and filing history.
- **D-081:** Reconcile every cancelled check before correcting deductions; retain its evidence and retire its replacement route only through the posted correction. The 2026-09-12 extension applies the same rule to independently reviewed, exactly reversed bank returns.

- **D-080:** Retain all claim shares on one exact historical-payment reversal line, using the existing journal allocation evidence and independent posting audit; never select one credit or fabricate split financial reversals.

- **D-079:** Split a consolidated historical liability into reviewed invoice identities over the original credit; preserve exact application shares, dated parent/invoice capacity and pinned approval evidence through settlement and corrections.

- **D-078:** Allocate consolidated DVs and partial checks explicitly across original claims; reserve the whole group atomically and retire only the shares of an independently posted closing return.

- **D-077:** Attribute historical claims and prior applications through independently reviewed metadata over unchanged journal lines; reconcile report projections and pin the approval version used by each new DV reservation.

- **D-076:** Validate new prior-payable reservations against their effective date and intervening posted movements; retain the existing original-credit lock and count active holds only once.

- **D-075:** Correct posted prior-payable deductions by exact source reversal, protect unremitted balances and reopen the DV only after independent posting; allow reasoned withdrawal only before posting.

- **D-074:** Generate reviewed earlier accruals through the existing posting request and original claim; require explicit recognition evidence, independent posting and a distinct pre-DV correction route.

- **D-073:** Reserve original claim capacity across the existing separate-store DV handoff; post only actual deduction/payment effects, retain exact payment reversals and recover interrupted operations from pinned evidence.

- **D-072:** Identify individual claims and their applications on immutable journal lines; derive dated outstanding amounts, serialize source-capacity/recognition checks and retain actual reversal lineage before enabling prior-payable DVs.

- **D-071:** Select statement funds at the ledger source, retain every financial row/column, pin selection into issued evidence and reject arbitrary post-calculation filtering.

- **D-070:** Require consistent four-statement evidence for new notes; issue immutable bundles containing actual reports and printable notes, retain historical two-member records, and serialize note approvals before candidate locks.

- **D-069:** Classify historical and mixed posted cash through independently reviewed allocations; preserve financial history, serialize decisions on the source journal and retain report-specific classification versions.

- **D-066:** Separate explicit nominal closing transfers and their reversals from performance-statement activity while retaining complete ledger/report evidence; this is a prerequisite for M01 financial-statement completion.

- **D-065:** Prioritize complete eGAPS-informed office workflows and outputs, familiar account-based web navigation, maintainable rule/form changes and authorized WFH; preserve existing financial and acceptance controls.

- **D-058:** Follow scheduled/registered work handed to another owner through return and review, exclude the user's current actions, and use only current handoff evidence for age.
- **D-057:** Retain scheduling, defect registration and each recorded escalation as distinct personal actions, without implying completion, resolution or that GRAND sent a notification.
- **D-056:** Follow the source stager's pending review handoff and credit retained staging/decision events only against their exact immutable source version.
- **D-055:** Give independent source-layout reviewers an exact task and share its eligibility with source-page controls; retain the existing service decision boundary.
- **D-054:** Credit voucher synchronization separately from JEV posting, requiring matching retained request/ledger proof across the two stores.
- **D-053:** Show pending reopen requests in Waiting for the current requester, using the request timestamp and existing independent-decision scope.
- **D-052:** Separate amendment authorship from final signature-return recording, validate retained round/print lineage, and interpret legacy events only against their original round.
- **D-051:** Credit DV print and packet actions only when the event matches retained child evidence; keep superseded versions as history under current read access.
- **D-050:** Keep payment form amounts, choices and office/state controls consistent with retained recovery and source actions; retain visible readiness explanations.
- **D-049:** Match each printing action to its existing source dependencies; preserve reasoned replacement printing and existing-packet reuse without new grants.
- **D-048:** Reuse source action selectors for voucher preparation, independent review and ordered signature controls; keep separately authorized UAT reads and suppress duplicate pending amendments.
- **D-047:** Bind DV output generation and legacy packet linking to the stored pinned Finance owner, preserving Accounting artifact work across custody; recheck stored packet visibility.
- **D-046:** Share existing return destinations and posted/draft-JEV blockers between the source service and form; expose the control only to its current office.

- **D-045:** Use the existing Accounting validation selector on the voucher page, preserving governed exceptions and readable source notices.

- **D-044:** Put My Work actions first; keep coverage and record identifiers in native, keyboard-accessible disclosures.

- **D-043:** A reasoned DV return supersedes obsolete signing authority and interrupted amendments; corrected work must receive fresh review.

- **D-042:** Preserve signatory snapshots across paper reprints and resolve pending amendments through retained print lineage.

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


## D-042 - Amendment-aware controlled reprint lineage

- Date: 2026-09-09. Status: implemented and verified in v0.7.52.
- Decision: a replacement signing copy must clone the governed signature/custody snapshots of the superseded printed round, resetting signature return status without reselecting live master signatories. Resolve a pending amendment through the same-case print-supersession chain to its immutable original signature round. Refuse final completion if that linkage cannot be established.
- Goal: distinguish paper replacement from a new date/signatory decision, preserve who was actually selected, and resume the correct Accounting/Treasury stage only after replacement signatures complete.
- Alternatives/tradeoffs: rewriting the amendment's original round would destroy immutable evidence; re-querying active signatories can change a deliberate acting assignment. Existing print-supersession relationships can retain the round lineage without a new mutable amendment pointer or a historical data backfill. Original signed/declined tasks and obsolete output files remain historical evidence.
- Evidence: two reproduced failures in 3.120 seconds. Repeated reprints, selected output/task snapshots, missing-lineage rollback and unchanged original amendment evidence verified. All 76 focused voucher/signature tests passed in 43.931 seconds. All 670 project tests passed in 272.577 seconds. System, migration-drift, compilation and diff checks passed.
- Revisit when: introducing a distinct governed signatory change while an amendment is already pending. A paper reprint must not silently perform that policy change.

## D-043 - Returned DV correction supersedes prior signing authority

- Date: 2026-09-09. Status: implemented and verified in v0.7.53.
- Decision: on a governed return to DV preparation or renewed signatures, mark existing signing copies and outputs superseded while retaining their immutable evidence. A pending non-financial amendment interrupted by a return to preparation receives an explicit superseded status, never a completed status. Record affected copy/amendment identities in the existing reasoned return event, which already owns actor, time and reason.
- Goal: keep material correction and paper replacement distinct, prevent obsolete paper from authorizing a corrected DV, and ensure corrected amounts/details receive the normal fresh review before later processing.
- Alternatives/tradeoffs: blocking every return until an amendment completes prevents legitimate correction; silently completing the amendment misstates evidence. Rewriting its original round or resume stage loses lineage. One additive status choice plus the retained return event records supersession without duplicating reason/actor/time fields or backfilling historical decisions.
- Evidence: two source-service assertions failed in 3.056 seconds before repair. Obsolete copies, interrupted amendment status, corrected/renewed rounds and final review stage, signed historical evidence, replay and audit-failure rollback verified. All 80 focused voucher/signature tests passed in 43.644 seconds. All 674 project tests passed in 304.236 seconds. System, migration-drift, compilation and diff checks passed.
- Revisit when: introducing a dedicated amendment withdrawal/resubmission process; preserve governed return reasons and distinguish actual completion from supersession.

## D-044 - My Work actions before implementation detail

- Date: 2026-09-09. Status: implemented and verified in v0.7.54.
- Decision: collapse the long coverage explanation, technical task/case/type/revision identifiers and view mechanics under native disclosures. Keep task subject, next action, source gate, exceptions, office scope, timing and source state visible. Give each record disclosure a source-specific accessible name and an explicit keyboard focus outline.
- Goal: employees should find the work and owning queue without reading implementation detail; retain identifiers and coverage for support, audit and export comparison.
- Alternatives/tradeoffs: removing metadata would weaken traceability; leaving every field expanded put the mobile task below multiple screens of explanation. Native details/summary supports keyboard use without another JavaScript state or permission contract. Exports and selectors are unchanged.
- Evidence: all 79 My Work/operations tests passed in 61.874 seconds. System, migration-drift and diff checks passed. Isolated authenticated browser checks covered desktop, 390px and 320px layouts, native Space/Enter toggling, Tab navigation, visible focus, exact source navigation and console inspection. See [browser QA](FINANCE_MY_WORK_BROWSER_QA.md). Full suite NOT RUN for this isolated template-only change; v0.7.53 passed all 674 project tests.
- Revisit when: adding substantive task fields or changing export/support identifiers. Keep operational constraints visible and details accessible.

## D-045 - Voucher detail follows the real validation action

- Date: 2026-09-09. Status: implemented and verified in v0.7.55.
- Decision: derive the validation form permission and main-step banner from accounting_validation_action_queryset, the same selector already used by the source action queue and My Work. Keep service-level validation authoritative and preserve independently approved case overrides and effective administrator exemptions. Clarify the routing message without implying all correction controls are unavailable.
- Goal: the source page and personal handoff must agree about which office/account can perform the next review; users should not be invited into a predictable maker-checker rejection.
- Alternatives/tradeoffs: copying self-review logic into the template would create another policy definition; broadening My Work would surface unauthorized work. Reuse the existing selector and leave its source-service rules intact. Scoped notice contrast and a human-readable pinned template title/version address browser-observed readability defects without restyling shared global UI.
- Evidence: two source-page assertions failed in 3.190 seconds before repair. Independent review, self-review exclusion, current-office custody, governed exceptions and UAT verified. Desktop/320px source pages and keyboard-scrollable evidence checked; fixed-width reason fields and raw template labels corrected. All 77 focused voucher tests passed in 46.346 seconds. All 84 My Work/operations/signature dependency tests passed in 56.615 seconds. System, migration-drift, compilation and diff checks passed. See [source browser QA](FINANCE_VOUCHER_DETAIL_QA.md).
- Revisit when: extending detail-page parity to another stage; reuse that stage's source selector and distinguish a main workflow action from separate correction controls.

## D-046 - Reasoned voucher return routes follow source state

- Date: 2026-09-09. Status: implemented and verified in v0.7.56.
- Decision: extract the existing stage-to-return-destination map and retained DV/instrument/posted-JEV/materialized-draft restrictions into a small shared source contract. Use it in both the locked return service and ReturnCaseForm. Keep the reason, version/idempotency and mutation checks; scope the visible return control to the current office. Show a retained-source blocker when no route is available instead of an unusable form.
- Goal: an employee should select a real governed correction destination without discovering predictable restrictions only after submission. Posted financial evidence must still require its adjustment/reversal/replacement route.
- Alternatives/tradeoffs: filtering a copied template list would diverge again; removing service restrictions would weaken retained financial controls. Share only existing routes and blockers, with no new route or automatic financial reversal. Preserve each existing rejection reason and transaction boundary.
- Evidence: Two route/current-office assertions failed in 3.132 seconds before repair. Verified current stage choices, current office/UAT, posted/materialized blockers and draft discard recovery, forged targets/caller stage, successful correction and existing rollback/history behavior. All 84 focused voucher/custody tests passed in 46.247 seconds. All 678 full-project tests passed in 334.918 seconds. System, migration-drift, compilation and diff checks passed. Isolated browser confirms the two permitted validation-stage destinations.
- Revisit when: adding a new governed correction route or changing posting recovery; update the shared contract and service tests together.

## D-047 - Stored owner authority for DV artifacts and legacy custody links

- Date: 2026-09-09. Status: implemented and verified in v0.7.57.
- Decision: use the existing pinned Finance-owner boundary for output generation and legacy packet association, with explicit active/non-UAT permissions. Reload and lock the source case before owner checks, including idempotent replay. Reload the TracePoint item and its current packet before checking existing association and visibility.
- Goal: only the owning office can generate or associate financial evidence, while Accounting can still work on its retained DV artifacts after custody moves. Caller-supplied owner or packet fields cannot expand authority.
- Alternatives/tradeoffs: generic grants do not delegate ownership. Requiring current custody would break the existing Accounting output-after-Treasury and linking-during-Budget workflows. Reuse the pinned-owner boundary already governing nonfinancial amendments; keep TracePoint's existing participant/office visibility policy.
- Evidence: Three reproductions produced seven failed assertions in 4.682 seconds. Verified unrelated-office generation/new-link/replay, forged stored-owner/current-packet inputs, stale association, HTTP/page denial, UAT and retained financial/file evidence. Existing owner output-after-Treasury and linking-during-Budget workflows remain valid. All 90 focused voucher/custody tests passed in 60.994 seconds. All 684 full-project tests passed in 407.127 seconds. System, migration-drift, compilation and diff checks passed.
- Revisit when: adding explicit artifact delegation or changing TracePoint visibility; any policy change needs its own accepted scope and source tests.
- Edge case: cases without a pinned configuration owner fail closed for artifact authority, including amendments. Verification also covers inactive accounts. An initial full run was stopped after source review identified this missing-owner guard; only the final source's completed runs count toward the checkpoint.

## D-048 - Source action parity for voucher review and signature forms

- Date: 2026-09-09. Status: implemented and verified in v0.7.58.
- Decision: deny mutation display for combined-grant UAT accounts while preserving their separate read/audit permissions. Use existing payable and DV preparation selectors for office and maker-checker scope, and the signature selector for the next eligible task in the displayed and submitted form. Use the existing source queue filter for the main-task banner. Suppress a new amendment while replacement signatures are pending.
- Goal: the personal queue, source form and source mutation boundary should agree about who can act and which retained step comes next. Readable source evidence and incomplete-readiness explanations remain available to authorized readers.
- Alternatives/tradeoffs: duplicating actor/office/order rules in templates would diverge again; widening the queue would weaken controls. Reuse existing source contracts and preserve administrator exemptions, immutable signature evidence and the separate pinned-owner artifact route. Printing dependencies and payment-form controls remain separately tracked under FIN-GAP-029.
- Evidence: Five page/HTTP tests produced 13 failed assertions in 16.500 seconds. Combined-grant UAT reads and denied controls, Budget-certifier exclusion and existing exemption, own/wrong-office payable review, signature order and pending amendment controls verified. All 174 focused voucher/My Work/operations tests passed in 301.273 seconds. All 689 full-project tests passed in 237.536 seconds. System, migration-drift, compilation and diff checks passed. Mutation services remain authoritative and unchanged.
- Revisit when: adding source actions or exemptions; update the selector and its direct service/HTTP/page tests together instead of adding another independent rule.
- Verification limitation: the first full-regression attempt was interrupted by loss of the tool host and had no completion summary. It is NOT RUN - ENVIRONMENTAL (incomplete), retained in `.tmp/finance-v0758-full-interrupted.log`; only the restarted, completed run can count as checkpoint evidence.

## D-049 - Printing actions retain their source dependencies

- Date: 2026-09-09. Status: implemented and verified in v0.7.59.
- Decision: signing-copy preparation must carry its existing DV output grant and pinned-owner scope. Physical-print recording remains a separate action. New packet assembly needs the existing TracePoint preparation authority; reusing a linked packet does not create one and keeps its existing route. Reasoned replacement remains available without counting it as the pending main action while signatures are elsewhere.
- Goal: employees receive actionable work that agrees with the authoritative Finance and physical-custody services, while retained copies and correction lineage remain intact.
- Alternatives/tradeoffs: granting everyone packet creation or combining all printing permissions would widen authority. Hiding all replacement work once a packet circulates would remove an existing recovery route. Reuse source predicates and distinguish the three steps in queues and forms.
- Evidence: PASS: 112 voucher/custody tests in 49.996 seconds. PASS: 82 My Work/operations tests in 49.149 seconds. System, migration-drift, compilation and diff checks passed. Reproduction: two tests produced six failed assertions and one missing-owner form-construction error in 3.321 seconds. Tests preserve existing-packet reuse, replacement printing, denied grants, office scope and source-read access. No source mutation-service or schema changes. Full suite NOT RUN - OUT OF SCOPE for bounded read selectors and form visibility; affected voucher/custody plus all My Work/operations dependencies cover the changed contracts. The v0.7.58 full baseline passed 689 tests. Browser NOT RUN - OUT OF SCOPE for conditional forms without layout changes; rendered-page assertions verify controls. Production/LGU gates remain open. FIN-GAP-029 retains payment-control and generic workbench-attention findings.
- Revisit when: explicit printing delegation or physical-packet policy changes; update the source services and their queue/form contracts together.

## D-050 - Payment form readiness follows retained recovery

- Date: 2026-09-09. Status: implemented and verified in v0.7.60.
- Decision: calculate replacement defaults using the source service's active-check statuses; exclude stale/returned instruments from release choices while explaining the required recovery. Limit Treasury and cancellation controls to the current office and eligible state, and legacy new custody links to nonterminal cases. Initial advice preparation is distinct from reviewing or progressing an existing batch. Generic signature-stage attention must use the same real print/signature actions as exact queues.
- Goal: staff should see the correct next step without re-encoding financial facts or retrying an action that its authoritative service already rejects.
- Alternatives/tradeoffs: changing issued amounts, reviving returned checks or widening permissions would corrupt retained history or weaken authority. Preserve service rules and the existing correction/reversal/replacement chain; repair the read-side invitations and defaults only.
- Evidence: Five reproductions produced ten failed assertions across two runs (8.231 and 5.681 seconds). PASS: 177 voucher/custody/My Work/operations tests in 96.163 seconds. PASS: 692 full-project tests in 248.224 seconds. System, migration-drift, compilation and diff checks passed. The first focused run failed one new test because its added Accounting issue grant changed the fixture routing office; the test now removes that grant before source issuance and asserts the retained Treasury destination. This was FAIL - CAUSED BY CURRENT WORK (test fixture), repaired before final verification. Full regression covers the shared workbench filter, queue/export dependencies and payment recovery workflows. Browser NOT RUN - OUT OF SCOPE for conditional controls and field choices without layout changes; rendered-page and real recovery tests verify the change. No mutation-service/schema changes or live migration.
- Revisit when: changing payment recovery or advice policy; source guards, forms, task readiness and history must change together with explicit evidence.

## D-051 - Retained print and packet actions in personal history

- Date: 2026-09-09. Status: implemented and verified in v0.7.61.
- Decision: project signing-copy preparation, physical-print recording and packet assembly from their retained actor events only after matching the same-case print job, version and actor field. Preparation also matches output identity/checksum; print recording matches the retained count; assembly matches retained packet/item and checkpoint evidence. Batch-load children and omit malformed or inconsistent references.
- Goal: staff can follow the work they actually performed through correction and custody movement without another authoritative record or inferred personal credit.
- Alternatives/tradeoffs: current job status cannot establish who performed an earlier step. Bare events with inconsistent child references are insufficient. Keep stable event identities, distinguish current copy state, retain superseded work as history and never imply that historical preparation authorizes signing or payment. Current source read access and UAT exclusion still apply.
- Evidence: PASS: 178 voucher/custody/My Work/operations tests in 93.699 seconds. System, migration-drift, compilation and diff checks passed. The initial focused 89-test run passed in 53.892 seconds; final verification follows integer-range hardening. Coverage includes the real three-version print/reprint/amendment chain (seven retained actions), custody movement, stable identities with updated supersession evidence, malformed/oversized/missing/foreign references, actor/stage mismatch and UAT/read-access loss. Full suite NOT RUN - OUT OF SCOPE for a bounded read-only history adapter with all voucher and My Work/operations dependencies exercised; v0.7.60 passed 692 full-project tests. Browser NOT RUN - OUT OF SCOPE: existing task layout is unchanged; service/projection and source-page regressions supply this checkpoint evidence. No source mutation-service/schema changes or live migration. Amendment creation/completion and detailed posting/reopen history remain separate next slices.
- Revisit when: introducing a new retained print event or changing its evidence schema; preserve original attribution and version lineage.

## D-052 - Amendment history preserves author and recorder attribution

- Date: 2026-09-09. Status: implemented and verified in v0.7.62.
- Decision: amendment creation must match the retained version, author, source route, dates and financial snapshot. Completion must match the final recorded signature, actual/original rounds and controlled-print lineage when applicable. Credit the final custody recorder separately from the amendment author and physical signatories. Keep superseded interrupted amendments as creation history, never infer completion from later ordinary signatures.
- Goal: preserve each person's actual contribution through governed document correction without changing money, posted entries or source authority.
- Alternatives/tradeoffs: selecting the latest print job would misattribute older amendments. Legacy completion events without round metadata are interpreted only against their original amendment round and retained recorder evidence; ambiguous or inconsistent evidence is omitted rather than guessed. Modern events must prove the explicitly retained actual round and print job. Current read access and UAT exclusion remain.
- Evidence: PASS: 86 amendment/My Work/operations tests in 129.341 seconds. PASS: 95 voucher/custody tests in 103.726 seconds. System, migration-drift, compilation and diff checks passed. Real workflows verify distinct author/final-recorder attribution, multi-generation print lineage, original-round legacy compatibility and interrupted amendment supersession. Synthetic inconsistent actor, amount snapshot, version, print-job, round and malformed/legacy references are excluded; UAT and revoked read access hide history. Full suite NOT RUN - OUT OF SCOPE for this bounded read-only adapter with all voucher/custody and My Work/operations dependencies exercised; v0.7.60 passed 692 full-project tests. Browser NOT RUN - OUT OF SCOPE because the existing task layout is unchanged. No source mutation-service/schema changes or live migration.
- Revisit when: migrating historical event schemas or adding new amendment workflows; any backfill requires its own evidence, never a fabricated completion.

## D-053 - Personal Waiting for period-reopen requests

- Date: 2026-09-09. Status: implemented and verified in v0.7.63.
- Decision: add only current `REOPEN_REQUESTED` records whose retained requester is the signed-in user and whose Accounting department is currently readable. Use the reopen-request timestamp and independent reopen-review queue. Keep the existing exclusion of current source actions before the display cap, UAT exclusion and source read checks.
- Goal: the user can follow a correction request they submitted without confusing it with the earlier period-close checklist or inventing a new approval workflow.
- Alternatives/tradeoffs: attributing every reopen to the original close preparer would expose someone else's later request as personal work. Returning all office requests would violate the user's Waiting preference. A return/approval ends that pending handoff; a resubmission follows its current requester and timestamp. Existing retained close/reopen history is unchanged.
- Evidence: PASS: 90 My Work/operations/period-close tests in 133.889 seconds. System, migration-drift, compilation and diff checks passed. Tests cover approval, rejection/resubmission, a requester distinct from the original close preparer, source navigation, current-action exclusion and UAT/read/office loss. Full suite NOT RUN - OUT OF SCOPE for the isolated read-only Waiting query; all My Work/operations and period-close source regressions cover the changed contract. Browser NOT RUN - OUT OF SCOPE because the existing task layout is unchanged. No source mutation-service/schema changes or live migration.
- Revisit when: adding explicit delegation or changing reopen ownership; preserve the distinction between prior close work and the current reopen request.

## D-054 - Personal history for verified voucher posting synchronization

- Date: 2026-09-09. Status: implemented and verified in v0.7.64.
- Decision: project only retained synchronization events attributed to the user under current voucher read scope. Match case/request/JEV identities, recorded source route and Accounting office, posted status/attribution, exact positive balanced ledger totals and source/rule checksums using the existing source-link verifier. Batch-read each database independently. Credit the synchronization actor from the voucher event; the ledger poster may be a different person.
- Goal: show the completed handoff back to the shared case without duplicating the original posting action or mistaking a current status for historical proof.
- Alternatives/tradeoffs: current `POSTED` flags alone cannot prove the handoff. Requiring the synchronizer to be the original poster would misattribute authorized recovery by another Accounting poster. Current voucher scope controls this case-history projection; ledger proof is checked internally without granting new ledger mutation or access. Inconsistent proof is omitted. Returned-item reviews have no separate posting event: their retained voucher reversal synchronization supplies the history, rather than fabricating a review completion.
- Evidence: tests exercise distinct poster/synchronizer accounts, replay, recognition/payment/reversal handoffs, malformed/foreign references, source checksum and posted-audit drift, one-cent ledger drift and UAT/read loss. PASS: final 180 voucher workflow/custody/My Work/operations tests in 128.334 seconds. PASS: full 695-test project suite in 250.542 seconds before the final presentation-only refinement. PASS: system, migration-drift, compilation and diff checks. The first final affected run failed one newly added assertion because its JEV fixture had no note (180 tests, 98.481 seconds; FAIL - CAUSED BY CURRENT WORK, test fixture). The assertion was moved to the real synchronization fixture and the affected suite rerun. Full suite NOT RUN again after the note-label/title refinement: final affected regressions cover the shared template and source adapter. No mutation-service/schema changes or live migration; user database unchanged. Browser checks use isolated synthetic two-store fixtures, not LGU acceptance. Browser review also clarified synchronization wording and distinguished completed Record notes from active Exceptions.
- Revisit when: adding a source posting kind or changing synchronization evidence; preserve independent actor attribution and both database boundaries.

## D-055 - Source-layout review discoverability and control parity

- Date: 2026-09-09. Status: implemented and verified in v0.7.65.
- Decision: expose current pending drift sources in draft cycles as exact review tasks, restricted to the current Finance office and an independent authorized reviewer. Reuse the selector for register attention, counts, task navigation, cycle-page links and the review form. Keep service-side revalidation unchanged.
- Goal: an independent reviewer can find the next blocked handoff without searching every cycle, while preparers do not see a decision they cannot perform.
- Alternatives/tradeoffs: generic cycle preparation does not reach reviewers and does not identify the changed version. Merely hiding the self-review button leaves direct forms inconsistent. Completed/superseded/rejected versions remain readable on the cycle, but do not offer a new review form. The source stager's Waiting/history follows in the next adapter phase; no ownership is inferred from cycle creation.
- Evidence: one real source-staging regression reproduced the absent exact task (FAIL, 1 test in 2.249 seconds). PASS: 133 cutover/My Work/operations tests in 101.312 seconds; system, migration-drift, compilation and diff checks passed. Initial reproduction failed one real source-staging task assertion (1 test, 2.249 seconds). Tests cover independent task/source navigation, self-review exclusion, acceptance/start, rejected-source replacement, supersession, UAT and permission loss. Full suite NOT RUN - OUT OF SCOPE for this read-only selector and form-eligibility refinement: affected field lifecycle and shared work/operations suites cover the changed contracts, with v0.7.64 full-project baseline recorded separately. Browser NOT RUN - OUT OF SCOPE: existing layout unchanged; rendered links and form responses verified by integration tests. No schema/service mutation changes or live migration; user database unchanged. The first 133-test affected run errored on a missing import in the new external-lock test (100.629 seconds; FAIL - CAUSED BY CURRENT WORK, test setup); the import was corrected and the entire affected suite rerun.
- Revisit when: source review ownership or the review lifecycle changes; retain independent attribution, current-office scope and UAT exclusion.

## D-056 - Personal source-version handoffs and retained history

- Date: 2026-09-09. Status: implemented and verified in v0.7.66.
- Decision: Waiting follows the current source stager when a draft cycle's current drift version awaits review. Completed history resolves audit events through the unique cycle/version pair, matches immutable source metadata with JSON types preserved and credits the retained staging or independent-decision actor. Current source read scope and UAT exclusion remain.
- Goal: distinguish source preparation from cycle authorship and independent approval, while preserving the correction history of superseded source versions.
- Alternatives/tradeoffs: crediting the cycle creator would misattribute another person's source staging. Using current approval status alone would invent an action. Historical source metadata supplies attribution; the projection neither reads raw CSV row values nor claims current file validity, field qualification or LGU acceptance. Source layout decisions retain their independent actor and recorded outcome.
- Evidence: PASS: final 134 cutover/My Work/operations tests in 108.173 seconds; 3 initial focused tests in 8.226 seconds; system, migration-drift, compilation and diff checks passed. Tests cover a stager distinct from the cycle creator, CSV and external locks, independent acceptance/rejection, replacement/supersession, malformed evidence including JSON type drift, stable event identity, current read loss and UAT exclusion. Full suite NOT RUN - OUT OF SCOPE for the read-only field-source adapters; complete field lifecycle and shared work regressions cover the changed contract, with the v0.7.64 full baseline recorded separately. Browser NOT RUN - OUT OF SCOPE: uses the existing verified task layout with no template changes. No source mutation-service/schema changes or live migration; user database unchanged.
- Revisit when: source identity, audit serialization or staging ownership changes; never silently reinterpret ambiguous historic events.

## D-057 - Retained field scheduling and defect helper actions

- Date: 2026-09-09. Status: implemented and verified in v0.7.67.
- Decision: add recorded exercise scheduling, defect registration and escalation events to personal history. Scheduling/registration match the source creator and original source state. Escalation uses the event's recorder, count, timestamp and note, preserving earlier recorders when a later follow-up changes the source's latest escalation fields. Existing child/cycle identity, current source scope and UAT checks apply.
- Goal: explain who handed work to an owner and who recorded follow-up, separately from the eventual exercise result or independent defect resolution.
- Alternatives/tradeoffs: crediting the latest escalation actor for every event would erase earlier contributions. A recorded escalation is evidence entered by the actor, not proof GRAND delivered a message. Export receipts remain in source audit rather than being presented as financial completion.
- Evidence: PASS: final 134 cutover/My Work/operations tests in 106.795 seconds; 3 initial focused lifecycle tests in 6.898 seconds; system, migration-drift, compilation and diff checks passed. Tests cover scheduling ownership through rerun, cross-cycle exclusion, UAT/read loss, registration, two differently attributed escalation events, later resolution, and malformed recorder/count/time/state/note evidence. Full suite NOT RUN - OUT OF SCOPE for the bounded read-only field-history adapter; the full field lifecycle and shared work suites cover its dependencies, with the v0.7.64 full-project baseline recorded separately. Browser NOT RUN - OUT OF SCOPE: existing verified task layout unchanged. No schema/source mutation-service changes or live migration; user database unchanged.
- Revisit when: introducing actual messaging or changing scheduling/defect ownership; preserve the distinction between preparation, follow-up and independent acceptance.

## D-058 - Personal Waiting for prepared work with another owner

- Date: 2026-09-09. Status: implemented and verified in v0.7.68.
- Decision: include exercises scheduled and defects registered by the current user when the source names another owner; carry preparation attribution into the submitted-result/review handoff. Exclude current actions on the exact child record before display limits. Use the retained latest return time for correction handoffs only when cycle, department, owner, state and current submission timing match; invalid latest evidence yields unknown age instead of an older return date.
- Goal: fulfill the user's prepared-or-submitted Waiting rule without turning it into all office work or suggesting that the creator can perform the owner's or independent reviewer's action.
- Alternatives/tradeoffs: submission-only tracking loses the initial assignment and returned correction. Creator-only tracking would retain actionable records in Waiting. Scheduling/registration remains a source operation, not a new task-assignment authority; this does not implement generic delegation, shared views or notifications.
- Evidence: PASS: final 136 cutover/My Work/operations tests in 116.260 seconds; full 699-test project suite in 292.911 seconds on final executable source; 3 initial focused tests in 7.921 seconds. System, migration-drift, compilation and diff checks passed. Tests cover initial handoff to a distinct owner, submission, multiple returns/resubmission, acceptance, exclusion of current witness/review actions, mismatched latest owner evidence without fallback, UAT and read revocation. Browser NOT RUN - OUT OF SCOPE for the unchanged task layout; prior desktop/320px and keyboard evidence remains linked in the browser QA documents. No schema/source mutation-service changes or live migration; user database unchanged. Full regression is software evidence, not operational scrutiny or LGU acceptance. Final commands: `.venv/Scripts/python.exe manage.py test finance.test_cutover finance.test_work_tasks finance.test_operations --noinput` and `.venv/Scripts/python.exe manage.py test --noinput`.
- Revisit when: generic delegation or assignment changes are introduced; preserve named source ownership and independently recorded handoff timing.

## D-059 - Validate core operations before expanding collaboration

- Date: 2026-09-09. Status: scrutiny in progress; production remains NO-GO.
- Decision: after the documented personal-handoff adapter queue, prioritize the mandatory operational scrutiny of the implemented Finance core. Refresh official-source evidence and exercise native MySQL recovery with synthetic data before adding generic following, shared views or notifications.
- Goal: reliable, independently reviewable municipal transactions and recoverable financial history. Additional collaboration features do not establish these controls.
- Alternatives/tradeoffs: broader assignment and messaging would require ownership/privacy decisions and would not close the existing operational gate. A same-host disposable MySQL rehearsal provides engineering evidence, but cannot replace the actual LGU's compatible off-host restore, named witness, accepted forms or transaction replay.
- Evidence: the starting v0.7.68 full suite passed 699 tests. The new five-digit TIN branch round-trip check passed with all 29 Finance reporting tests in 8.924 seconds. Source retrieval limitations, native execution and outstanding traceability are recorded in [the scrutiny report](FINANCE_SCRUTINY_2026-09-09.md); that report is explicitly incomplete.
- Revisit when: a reproduced critical gap changes the remediation order, or the LGU supplies the missing acceptance evidence. Preserve all deferred roadmap items and never infer official acceptance from synthetic execution.

## D-060 - Coordinate native capture without merging the databases

- Date: 2026-09-09. Status: implemented and verified in v0.7.69 for the supported topology. Native concurrency/restore and connection-loss/retry checks pass. PASS: final full SQLite suite, 708 tests in 314.043 seconds; final full MySQL 8.4.12 suite, 708 tests in 854.600 seconds. Both aliases remained separate. System, migration-drift, compilation and diff checks passed. The final affected native suite also passed 178 tests in 182.916 seconds.
- Decision: retain separate default and Finance schemas/artifacts, but hold one verified MySQL server-wide read lock for the duration of both dumps. Use a dedicated connection, validate both aliases against the same server identity, detect lock-connection loss, bound lock acquisition and fail closed when privileges, identity or supported topology cannot establish the boundary. Retain capture evidence separately from restore acceptance.
- Goal: prevent a completed financial entry from entering a recovery set while its earlier source record is omitted by an older default-store snapshot.
- Alternatives/tradeoffs: two independent transactional dumps demonstrably fail. A warning or operator checkbox does not enforce consistency. Merging the databases violates the project boundary. A single-server read lock temporarily blocks writes and therefore belongs in an approved operational window; it needs explicit database privilege. Different-server deployments require a separately engineered coordinated capture mechanism and must not silently fall back to the unsafe writer. No actual deployment privilege or maintenance setting is changed by this synthetic work.
- Evidence: [FIN-GAP-032](FINANCE_GAP_REGISTER.md) records the native interleaving and orphaned restored posting. MySQL documents that [FLUSH TABLES WITH READ LOCK](https://dev.mysql.com/doc/refman/8.4/en/flush.html) holds a global read lock across the server's databases until release. That is a capture mechanism, not proof of LGU recovery acceptance.
- Revisit when: the actual deployment requires separate MySQL servers, a different database engine, lower downtime or a managed backup service. Keep such capture routes blocked until their own concurrency, failure and restore tests establish equivalent controls.

## D-061 - Preserve Finance identities with native database enforcement

- Date: 2026-09-09. Status: implemented and verified in v0.7.69. PASS: final full SQLite suite, 708 tests in 314.043 seconds; final full MySQL 8.4.12 suite, 708 tests in 854.600 seconds. Both aliases remained separate. System, migration-drift, compilation and diff checks passed. The final affected native suite also passed 178 tests in 182.916 seconds.
- Decision: widen the payable projection's source-kind field to retain the existing 27/40-character identifiers, and use a text field for its complete source-reference list: a valid four-obligation consolidation exceeds the former 160-character limit. Never truncate source UUIDs. Replace Budget's unsupported conditional uniqueness for original request references, nonblank obligation numbers and active payable allocations with database-generated nullable keys and ordinary unique constraints. The database computes the keys on inserts and updates; drafts without numbers and historical correction/allocation versions retain their prior semantics.
- Goal: make the intended financial persistence controls hold on MySQL as well as SQLite, and allow the authoritative Budget-to-payable route to complete without truncating lineage identifiers.
- Alternatives/tradeoffs: shortening existing identifiers would rewrite their meaning/history; disabling strict SQL or ignoring native failures would hide the broken handoff. Application-only duplicate checks do not provide the required database invariant. Generated keys are internal implementation fields, not new user input or official financial identifiers.
- Migration boundary: inspect existing identity groups before schema changes and stop if duplicates exist. No automatic deletion, renumbering, merging or fabricated correction is allowed. Migrations are being tested only on disposable databases; the user's existing database remains unchanged. Other native conditional-constraint warnings remain a separate service/invariant audit.
- Evidence: the first native full run had 2 failures and 2 errors among 706 tests in 855.461 seconds, while SQLite passed. `d809977` already contains the undersized field and unsupported constraints. The initial repair exposed the active-allocation duplicate check; after extending the repair, all five focused native tests passed in 30.021 seconds. FIN-GAP-033/034 and the scrutiny report retain the exact tests and final status.
- Revisit when: another supported backend imposes different generated-column restrictions or existing deployment data fails the duplicate preflight. Preserve identity and correction lineage instead of weakening the constraint.

## D-062 - Preserve rollback and give explicit bank-match conflict feedback

- Date: 2026-09-09. Status: implemented and verified in v0.7.70. PASS: full SQLite run, 711 tests discovered in 355.841 seconds (710 executed; one MySQL-only case skipped); full MySQL 8.4.12 run through the committed native runner, all 711 tests in 767.251 seconds. System, migration-drift, compilation and diff checks passed.
- Decision: enforce active bank-row and journal-line match identities with generated nullable keys and ordinary unique constraints. Translate known MySQL deadlocks and named active-match collisions into a reload-and-check message only after the owning manual/automatic-match transaction has exited. A nested match leaves the exception to the outer automatic-match boundary. No action is implicitly retried, and unrelated database failures remain failures.
- Goal: prevent an opaque HTTP 500 during normal competing bank work while preserving exactly one active identity, complete rollback, immutable history and the preparer's control over a new attempt.
- Alternatives/tradeoffs: a broad retry mechanism would repeat financial actions beyond this demonstrated failure. Changing shared lock ordering across every bank workflow introduces a larger concurrency change. Explicit conflict feedback requires the losing preparer to reload and inspect the current match. Stored uniqueness protects the intended identity independently of the incidental deadlock seen in the reproduction.
- Migration boundary: accounting/0011 rejects existing active duplicate row/line identities before schema changes. It does not deduplicate, repair source snapshots or rewrite reconciliation history. Only disposable test schemas have been migrated.
- Evidence: FIN-GAP-035's actual native HTTP reproduction returned 500/302 with one surviving match (1 failure, 6.792 seconds). The initial repaired native gate passed all 3 selected tests in 19.963 seconds; SQLite passed its applicable selected tests with the native-only case skipped (3 discovered, 12.228 seconds, 1 skip). Final broad suites include an additional unrelated-database-failure check and the complete rollback/explicit-retry case.
- Revisit when: another bank mutation exposes a different conflict or a supported engine requires different error handling. Do not expand automatic retry or suppress unrecognized integrity/database failures without a new bounded analysis.

## D-063 - Make native regression a repeatable project gate

- Date: 2026-09-09. Status: implemented in v0.7.70; final local native gate passed. Remote CI NOT RUN - ENVIRONMENTAL because GitHub CLI authentication is invalid; no remote result claimed.
- Decision: add `scripts/run_mysql_tests.py` and an independent MySQL CI service job. Require explicit disposable credentials/loopback port, strict native MySQL, fixed test schema names and fresh migrations. Disable local `.env` loading and isolate runtime files. The existing SQLite/security job remains.
- Goal: catch native field-capacity, identity and concurrent-request failures that SQLite alone cannot expose, and make the evidence reproducible without ignored rehearsal scripts or a conversation transcript.
- Alternatives/tradeoffs: retained test schemas are faster but can lose migration-seeded data after transaction-test flushes. Fresh schemas cost setup time and provide a reliable full-suite baseline. The CI-only root account belongs to its ephemeral service; local users can grant only the two fixed test schemas. Neither route grants production authority or validates off-host recovery.
- Evidence and usage: [FINANCE_NATIVE_TESTING.md](FINANCE_NATIVE_TESTING.md) records the portable command, fixed scope, artifact location, workflow triggers and source references. The v0.7.69 fixture failure is retained in the scrutiny report. Development-branch push alone does not trigger this workflow; report remote CI separately from local execution.
- Revisit when: the accepted production engine/version changes or a migration requires additional native facilities. Preserve the two-store router, explicit test scope and real LGU acceptance gates.


## D-064 - Audit native identity boundaries before selecting the next repair

- Date: 2026-09-09. Status: bounded source audit recorded in v0.7.71; native reproductions remain next work.
- Goal: preserve one current financial authority/evidence identity and trustworthy reconciliation without mistaking a sequential regression for concurrency proof.
- Decision: inventory all remaining first-party conditional identities and trace their service transactions. Prioritize competing first activations of close policies/accountability profiles, then cross-period outstanding-item correction. Respect the default/Finance router; observe joined native locks rather than assuming their coverage.
- Evidence: [the audit](FINANCE_NATIVE_INVARIANT_AUDIT_2026-09-09.md) reconciles 21 declarations with native warnings (15 Finance-related, six supporting). Two additional warnings belong to third-party email-address models. Known service locks and model validation can prevent some duplicates; no new duplicate-financial-record finding was reproduced in this slice.
- Alternatives/tradeoffs: replacing every conditional key at once would broaden migrations before understanding lifecycle and duplicate-data conditions. Ignoring warnings would leave native enforcement unexamined. A bounded audit provides a concrete reproduction order and preserves separate validation for each repair; it is not completion of scrutiny.
- Revisit when: native HTTP/transaction evidence exposes a material defect. Apply the critical-gap gate, preserve immutable history and refuse duplicate migration data before DDL. Never silently clean financial records, automatically replay actions, suppress warnings or patch installed third-party code to obtain a passing gate.

## D-065 - Familiar web workspaces and practical Finance completion

- Date: 2026-09-10. Status: direction authorized; initial navigation slice validated in v0.7.72. User clarification puts financial functionality and source-to-ledger-to-output proof before further UX or surrounding infrastructure work. eGAPS is the parity floor, not the design ceiling; see the authoritative order in [modernization priorities](FINANCE_MODERNIZATION_PRIORITIES.md).
- Goal: improve the eGAPS office experience through GRAND's individual accounts and web delivery, make national/COA/DBM-driven changes manageable and support authorized WFH.
- Decision: adopt [priorities M01–M08](FINANCE_MODERNIZATION_PRIORITIES.md). Prioritize missing statements, payable/source workflows and exact outputs; retain existing framework/collaboration deferrals. Familiar registers and next actions should lead, with technical evidence available through disclosures.
- Implementation boundary: reuse existing Budget, Accounting, Voucher and Treasury registers. Shortcuts must honor each destination's complete access contract, including separately granted allotment, ledger, bank-reconciliation, advice, cash and remittance reads. UAT membership does not stand in for those read grants. Remittance navigation and views share the existing conjunction of workbench access and remittance permissions; no new role or authority is created.
- Alternatives/tradeoffs: copying every eGAPS menu would expose unavailable functions and reproduce workstation navigation. A new universal workflow/configuration layer would defer practical coverage again. Existing reviewed configuration, templates and source registers provide the bounded change path; new accounting semantics still require implementation and validation.
- WFH boundary: account-based web navigation is a foundation, not an approved remote deployment. Physical signatures, printing, custody and instrument release retain their actual office procedure. Named-account remote access, failure/recovery exercises and LGU decisions remain required.
- Evidence: live 2026-09-10 Accounting/Budget menu and DV-register inspection; Cash Disbursement internals unreviewed after launcher loss/server error 735. Source confirms missing dedicated Cash Flow/Changes in Net Assets datasets and blocked prior-payable linking. The printable assessment retains the v0.7.71 baseline separately from subsequent work. No eGAPS mutation or runtime dependency.
- Revisit when: actual clerk sessions or accepted rule/form changes reveal a mismatch. Preserve the separate databases and M08 native scrutiny rather than declaring the broader modernization finished from a navigation pass.

## D-082 - Preserve the original remittance while recording actual returned money

2026-09-12 receiving-bank follow-up: [actual bank routing](FINANCE_RECEIPT_BANKS_2026-09-12.md) retains the selected approved setup item/release and explicit mapped ledger account in the receipt proposal. Review rejects intervening mapping changes; after approval, mapping edits cannot silently redirect the journal. The original fund/liabilities and legacy default-source shapes remain retained. Fees/netting and actual outgoing agency dispositions remain separate.

2026-09-12 follow-up: [pre-posting withdrawal](FINANCE_RETURN_WITHDRAWAL_2026-09-12.md) preserves the independent approval and records withdrawal separately. Only absent/discarded source journals permit allocation release. The batch and Finance journal locks prevent withdrawal from bypassing materialization or posting; posted receipt corrections require their own financial/source treatment.

2026-09-12: [actual receipt implementation and evidence](FINANCE_REMITTANCE_RETURNS_IN_PROGRESS.md). The original completed batch remains the historical outgoing payment. `RemittanceReturn` retains immutable partial/full receipt proposals, original debit allocations and independent Accounting decisions; the existing posting-request mechanism retains the incoming JEV and recoverable handoff. Reserve explicit source shares rather than inventing a proportional split or reusing the editable `returned` batch status. A separate domain receipt record is justified by simultaneous partial receipts and their independently retained decisions; no generic workflow engine is added.

Debit the original bank and restore only the allocated original withholding liabilities, preserving source-line and cash-purpose evidence. Incoming Finance postings become available only after operational reconciliation. Keep original and incoming JEVs distinct in exports. Retain verified filing evidence unchanged until its own explicit amendment workflow runs, with batch-first filing/return locks. A returned cash amount is not proof of a legally accepted tax amendment. Different receiving accounts, fees/netted receipts, later return corrections and non-cash agency dispositions remain explicit unfinished paths; revisit those with their real source evidence. This decision advances functional source-to-ledger-to-output coverage, not full Finance parity or operational/LGU acceptance.

## D-081 - Reconcile cancelled checks before reopening a deduction-bearing DV

2026-09-12 extension: [reviewed bank-return corrections](FINANCE_RETURNED_CHECK_CORRECTIONS_2026-09-12.md) reuse the original reissue decision and exact payment reversal, then independently post the existing deduction correction. Pin both source requests and review evidence; close the reviewed authorization only in the recoverable correction handoff. Preserve its original outcome and instrument history. A new return outcome/state machine is unnecessary for this bounded path; revisit intake presentation after actual operator trials. Case-first review locking aligns with replacement/correction actions. Close-without-reissue, remitted withholding and unresolved replacements remain outside this path. The earlier limits below describe the original cancelled-check checkpoint.

- Date: 2026-09-12. Status: implemented and validated in the v0.7.89 development checkpoint; see [actual evidence and remaining scope](FINANCE_CANCELLED_CHECK_CORRECTIONS_2026-09-12.md).
- Goal: let Accounting correct an erroneous deduction after Treasury cancels an unreleased check, without deleting the old instrument or recognizing the expense again.
- Decision: reuse the existing deduction-reversal request and case lock. Require every check's governed no-entry cancellation or exact independently posted payment cancellation; pin its identity, amount, actor/date and request checksums. Reproduce these before materialization and completion. The posted deduction correction retires old replacement eligibility; fresh DV approval/signatures and a new check use the corrected amount.
- Alternatives/tradeoffs: an unconditional instrument-exists block strands resolved cancellations. Removing that block without reconciliation could reopen a paid DV. Deleting checks or reusing their numbers loses custody evidence. A separate retirement table duplicates the retained correction decision; using the existing sealed payload keeps one authority but requires verifying the posted decision when determining current eligibility.
- Limits/revisit: generated-history adoption, released/bank-returned cycles, remitted withholding and discarded/superseded payment-request reconciliation remain separate unfinished paths. This change does not assert complete M02, exact local print acceptance or production readiness.

## D-080 - Preserve one financial line across shared-claim reversals

- Date: 2026-09-10. Status: implemented in the v0.7.88 development checkpoint with full SQLite regression and focused native/concurrency validation. [Scope and evidence](FINANCE_SHARED_APPLICATIONS_IN_PROGRESS.md).
- Goal: complete the historical source-to-ledger-to-output path when one payment settled several original credits.
- Decision: extend the existing journal allocation JSON with a source-keyed map of pinned approval/invoice shares. Keep the original reversal's financial line count, amounts, accounts and responsibility centers. Require exact reversal ancestry and seal the complete map in the independent posting event. Use a common source lookup and per-credit amount projection for dated capacity and outputs; lock all original credits in sorted order for posting.
- Alternatives/tradeoffs: selecting one `payable_origin` loses other credits; splitting the financial reversal fabricates a different source structure. A second application ledger would duplicate authority. The retained JSON map preserves the original journal but requires a portable JSON source lookup and explicit integrity checks instead of one direct source FK; the approved attribution members retain protected source references. Native query and competing-capacity validation are required. Revisit indexing only with measured ledger-scale evidence.
- Progress/limits: independent atomic group review, ordinary shared entry/review and actual HTTP-to-DV settlement scenarios are implemented. Compatible successors preserve pinned reservation evidence; partial returns, recovery, deduction corrections and retained CSV are validated. Generated-history adoption, later instrument/remitted-withholding corrections and LGU acceptance remain open; see the linked current validation record.

## D-079 - Retain reviewed invoice identities over consolidated historical credits

- Date: 2026-09-10. Status: implemented on `codex/finance-historical-claim-splits`; [scope and validation](FINANCE_HISTORICAL_SPLITS_IN_PROGRESS.md) are authoritative for checkpoint status.
- Problem: a historical consolidated credit may represent several invoices, while new DVs and subsidiary schedules need each invoice's outstanding balance and payment lineage.
- Decision: retain immutable invoice rows inside independently reviewed attribution versions, with stable invoice identities and exact shares of every historical application. Leave the posted financial lines unchanged. Native applications and DV reservations pin approved invoice evidence; check both original-credit capacity and individual-invoice capacity under the existing source locks. Returns preserve the original shares; returned proposals create successors instead of editing decisions.
- Alternatives/tradeoffs: rewriting the original journal would destroy retained evidence; duplicating the consolidated credit would overstate liabilities; inferred shares would invent invoice attribution. Explicit invoice/application entry adds reconciliation work once, then supports familiar DV selection and reproducible schedules without duplicate recognition. Exact reversal and maker-checker controls remain mandatory.
- Boundary: this covers multiple invoices within one original credit. Historical applications shared across distinct original credits require coordinated allocation and remain unfinished. Generated-cycle adoption, later instrument/remittance corrections, exact local outputs and human/operational acceptance remain separate requirements. Do not equate this checkpoint with complete eGAPS parity.

## D-078 - Retain explicit DV and check allocations across original claims

- Date: 2026-09-10. Status: implemented on `codex/finance-consolidated-dv`; seven direct/HTTP scenarios pass on SQLite and 31 native tests pass, including four selected reservation races. Final full project regression PASS: 805 discovered / 788 passed / 17 native-only skips, 313.148 seconds. [Implementation and validation](FINANCE_CONSOLIDATED_DV_2026-09-10.md).
- Goal: complete the next M02 daily-office path without duplicate expense recognition, ambiguous partial payments or lost correction lineage.
- Decision: reuse the existing DV, governed posting instructions, original liability credits and payment instruments. One immutable Finance group retains each claim's gross, each deduction-line share and net. Sorted source locks and one Finance transaction create all holds; the default case lock serializes workflow decisions. Deterministic group identity recovers only the same allocation after a cross-store interruption.
- Payment decision: require explicit shares for partial checks. Paying the exact remaining amount can use the unique remaining allocation. Replacement amount/shares equal the original instrument. Cancellation and bank return mirror its original posted application lines. Do not distribute deductions or partial payments by an invented proportional/FIFO convention.
- Partial closure: retain a retirement record linked to the independently posted closing reversal for each affected reservation share. Keep other instruments usable; subtract retired shares on the return date when testing new dated capacity. The retirement is a capacity decision over actual posted evidence, not another ledger posting or a mutable financial balance.
- Alternatives/tradeoffs: a multi-select alone cannot identify amounts or deduction shares; independent per-claim commits can leave a partly reserved DV; releasing the entire group for one returned check invalidates other checks. The group, per-instrument snapshot and exact retirement records preserve those distinct decisions without a new rule engine. Existing single-claim snapshots remain unchanged.
- Limits/revisit: one payee/fund per supported DV/JEV; historical source-line splitting and adoption of unreconciled generated history remain separate work. Generated earlier accrual on the same case retains its existing single original source. Post-instrument/remitted-withholding corrections and the remaining financial/office/output/acceptance gates remain open. The form table supports up to 100 rows; large-register performance and named-user/browser acceptance remain to be assessed.

## D-077 - Review historical attribution without rewriting the journal

- Date: 2026-09-10. Goal: make earlier posted liabilities usable in the M02 claim-to-DV workflow without duplicate recognition or overstated unpaid capacity. [Implementation, validation and limits](FINANCE_HISTORICAL_CLAIMS_2026-09-10.md).
- Decision: use versioned attribution evidence for an original liability credit and its full historical application lines. A different Accounting reviewer approves a current pointer; original journals/subsidiary records and older decisions remain immutable. Reuse existing dated claim capacity, DV reservations, posting and exact reversals. Pin the approval version in the reservation while allowing compatible later metadata corrections.
- Reporting: project approved identity/application metadata consistently into the claim register, payable schedule, GL control reconciliation and report source snapshots. Retain original subsidiary identities within evidence; never change stored detail or create a no-purpose journal to attach an invoice label.
- Concurrency: lock the existing Fund before source/application lines for attribution decisions and invoice identity checks. Reservation writers share the original credit lock. Stale approval bases, duplicate applications/identities and overcommitted amendments fail without advancing the approved pointer.
- Alternatives/tradeoffs: editing posted fields destroys historical evidence; a label-only overlay ignores old payments; a new recognition JEV duplicates the liability. Reviewed metadata requires actual reconciled documents and explicit completeness confirmation. The current one-claim-per-credit ledger cannot implicitly split consolidated historical amounts; dedicated allocation and multi-claim settlement remain financial work, not presumed support.
- Boundaries: exclude generated voucher/remittance cycles until their operational handoff can be reconciled safely. Protect identities already used by later financial links and application evidence already referenced by reversals. Preserve the broader M01/M03, exact-output, office, usability/WFH and operational/LGU gates.

## D-076 - Reserve payable capacity across dated posted history

- v0.7.86 follow-up: existing-key recovery must also recompute requested-date capacity while counting the retained hold once. A failing earlier-retry reproduction led to the bounded repair; 39 SQLite and 39 native tests pass, including actual interrupted DV recovery/payment/export and five selected races. [Validation](FINANCE_CLAIM_RECOVERY_DATE_2026-09-10.md). This extends the existing dated-capacity decision without adding a schema or inventing historical dates.

- Date: 2026-09-10. Goal: close a concrete M02 eligibility gap found while reviewing historical attribution. [Reproduction, validation and remaining work](FINANCE_DATED_CLAIM_RESERVATIONS_2026-09-10.md).
- Decision: a new reservation must fit at its requested effective date and every subsequent posted movement. Keep the existing original-credit lock and same-key recovery. Count an active reservation's whole amount once; its applications convert held to used capacity. Released holds retain only their posted consumption.
- Alternative/tradeoff: ending-balance-only validation accepts a backdated DV using capacity restored by a later reversal; checking only the requested day misses an intervening shortfall. Deferring the failure until posting leaves an invalid downstream handoff. The additional daily calculation reuses existing journal evidence and creates no new ledger or configuration framework.
- Boundary: this is current reservation eligibility, not a reconstructed historical reservation-status ledger. Existing active holds are conservatively committed. Posting still rechecks dated applications. Historical attribution, consolidated claims and broader financial/office/acceptance work remain open; no source metadata is inferred or rewritten.

## D-075 - Correct posted deductions without rewriting financial history

- Date: 2026-09-10. Status: implemented in v0.7.82 on `codex/finance-deduction-corrections`; [validation and limits](FINANCE_DEDUCTION_CORRECTIONS_2026-09-10.md).
- Goal: make the M02 posted-adjustment correction usable through the existing office workflow, then prove corrected settlement and signed tax output.
- Decision: an existing posting request pins an exact reversal of the original deduction JEV. It retains original rule provenance without inventing a new posting recipe; independent posting retires the zero-consumption claim reservation and reopens DV preparation. A pending correction reserves the available withholding amount against remittance allocation.
- Tradeoffs: silently editing the old JEV would destroy history. Re-running current mappings could reverse a different account. A new universal correction framework would add authority and maintenance overhead. Exact source reversal uses existing journal machinery, while requiring case/source locking and a shared Accounting-owner reservation boundary across setup releases.
- Limits/revisit: before any payment instrument, with sufficient unreserved withholding. Post-issuance, remitted-tax/refund/external-filing correction, historical attribution and consolidated claims remain required. Unposted withdrawal does not undo a posted correction. Revisit only with concrete downstream correction requirements and retained evidence.

## D-074 - Generate the original payable before DV preparation

- Date: 2026-09-10. Status: implemented in v0.7.81 on `codex/finance-earlier-accrual`; [validation and limits](FINANCE_EARLIER_ACCRUAL_2026-09-10.md).
- Goal: complete the M02 actual recognition-to-settlement chain, without adding a competing ledger or configuration framework.
- Decision: use the reviewed intake and reconciled full-claim allocations to queue an existing `VoucherPostingRequest`; require a configured delivery/acceptance or billing-validation recognition rule and explicit actual date/reference. Independent posting resumes DV preparation and supplies the named original liability credit used by settlement.
- Alternatives/tradeoffs: inferring recognition date from invoice date can misstate timing; fabricating a DV to generate recognition duplicates facts. Reusing the existing source handoff avoids a new journal/workflow model, but requires correct pre-DV return destinations and ordered case locks across recovery/correction paths.
- Limits/revisit: one claim/one fund; reviewed debit-allocation/credit-gross-payable recipes. No automatic invoice-date recognition, historical relabeling, posted-claim rewrite or arbitrary posting recipes. Broader corrections, attribution, consolidated claims, actual local policy/form and office acceptance remain required.

## D-073 - Settle prior-payable DVs without duplicate recognition

- Date: 2026-09-10. Status: implemented in v0.7.80 on `codex/finance-prior-payable-dv`; validation is recorded in [the integration report](FINANCE_PRIOR_PAYABLE_DV_2026-09-10.md).
- Goal: finish real earlier-payable settlement using the familiar DV/Accounting/Treasury workflow, preserving separate databases, independent decisions and maintainability.
- Decision: retain a Finance-side reservation against an original posted liability credit and pin its source/amount in the existing default-store validation and posting requests. Lock the original claim for reservations and journal applications; the case lock serializes per-case decisions. Recover an interrupted handoff with a deterministic case/version key. Release only unused evidence through a supported correction route.
- Accounting behavior: no-deduction validation proceeds without a second recognition JEV. Deductions reclassify the original payable; actual payment reduces it. Generated cancellation/bank-return entries must exactly mirror the original posted payment and restore the same reservation. A reviewed return closed without replacement retires only unused capacity after its reversal posts, preserving prior deduction applications and recoverable closing evidence. Existing rules and posting/reconciliation services remain authoritative. A detached manual reversal cannot leave the operational payment state unreconciled.
- Alternatives/tradeoffs: an aggregate payee balance cannot reserve an invoice, a default-store-only check cannot serialize against Finance journal posting, and a second expense JEV would duplicate recognition. The small source reservation is necessary cross-store commitment evidence, not a second ledger or generic workflow framework. Pinned releases and existing account mappings remain reusable; unsupported rule shapes fail before payment rather than producing a second expense.
- Boundaries/revisit: one original claim/fund per DV, partial settlement supported. Earlier-accrual generation, historical attribution, consolidated claims and corrections to posted deduction adjustments remain explicit work. Exact forms and actual LGU acceptance are separate. Expand only for demonstrated financial scenarios while retaining independent approval and source recovery.

## D-072 - Link individual payable claims on the existing journal

- Date: 2026-09-10. Status: source-ledger work in v0.7.79; [behavior, validation and unresolved DV integration](FINANCE_PAYABLE_CLAIMS_2026-09-10.md).
- Goal: complete M02 earlier recognition/settlement without duplicating expenses or confusing invoices belonging to one payee.
- Decision: identify the original liability credit and reference it from applied liability debits. Compute dated balances from posted lines and create matching immutable subsidiary detail at posting. Reuse ordinary JEV preparation, independent posting, reversal, register and archived-export paths.
- Safeguards: source-credit locks serialize competing applications; an existing fund-row lock serializes new claim identity checks. Check every dated cumulative application against the original credit. Only actual mirrored reversals restore capacity; later reversals cannot justify earlier overpayments.
- Alternatives/tradeoffs: aggregate payee balances cannot distinguish invoices. A separate mutable balance would duplicate ledger authority. Explicit links add clerical source selection while keeping the accounting history authoritative. Legacy unlinked sources remain unresolved evidence, not guessed invoice assignments.
- Boundaries/revisit: this does not implement the blocked DV routes or global cash/payment reservations. Next connect source selection, earlier-accrual requests, partial DV settlement, deductions and correction handoffs across the existing stores. A posted claim identity remains reserved after reversal; corrections use distinct references and explicit evidence. Revisit detailed invoice splitting when an actual supported scenario needs it.

## D-071 - Select source funds before calculating complete statements

- Date: 2026-09-10. Status: implemented in v0.7.78; see [validation and remaining work](FINANCE_STATEMENT_FUNDS_2026-09-10.md).
- Goal: finish concrete M01 source-to-ledger-to-output behavior before surrounding UX/framework work.
- Decision: use one common exact/list fund restriction on original posted journals in all four statement adapters. Reuse the existing definition form and retained run snapshot. Reject financial row filters, grouping, generic totals, custom row sorting and incomplete columns at definition validation and generation. Include scope in generated title metadata.
- Evidence: earlier Position/Performance could calculate the whole ledger and then hide rows while retaining a reconciled control status. The package guard rejected incomplete members but did not fix standalone generation. Multi-fund tests now check separate and combined amounts, original journal scope, actual exports and complete notes.
- Tradeoffs: existing invalid definitions fail a new generation and need correction; no silent reinterpretation or backfill of prior outputs. Position/Performance aggregate selected funds, while movement reports retain their per-fund detail. Selection stays in current report configuration rather than adding another selection workflow.
- Boundaries: preserve office/role restrictions, historical evidence and separate stores. Office-wide zero-opening declarations keep their existing meaning. Exact statutory presentation, local scope decisions and broader acceptance remain unproven; M02 payable linkage follows this repair.

## D-070 - Complete statement membership and retain issued package files

- Date: 2026-09-10. Status: implemented on `codex/finance-statement-package`; [validation and remaining scope](FINANCE_STATEMENT_PACKAGE_2026-09-10.md).
- Goal: advance M01 from individual calculations and identifier-only exports to usable four-statement notes and a reproducible download. Preserve original report bytes, independent decisions and actual financial consistency.
- Decision: add nullable Net Assets/Cash Flow references for historical compatibility, require all four for new creation/submission, and compare periods, posted journal evidence, closing net assets, operating result, cash balances and visible mandatory rows. Extend reference comparison to every retained fund/current/comparative movement row. Original two-member snapshots remain unchanged.
- Output: retain the first ZIP as an immutable file with checksum/date. It contains the four original reports, printable A4 notes and member hashes. Later downloads verify the issued artifact and member identity instead of regenerating it from changed user labels or source files. Existing note CSV exports remain historical aids; a manifest alone is not the complete downloadable package.
- Authority/concurrency: use existing note-export and report-download permissions together with current source visibility. Lock the department before version/candidate rows; reject an older candidate after a newer approval. This is source-specific consistency, not new general workflow machinery.
- Tradeoffs: packages retain each report's original format; they do not automatically turn an XLSX into an accepted statutory PDF. Historical packages remain reproducible, but new incomplete packages cannot pass by invoking old compatibility. Synthetic prompts, working reports, hashes and concurrency tests are not legal or local form acceptance.
- Next: fix common fund-scoped generation and the remaining standalone Position/Performance row-filter behavior. Rejecting an incomplete package member does not repair that underlying reporting function. Continue M02 afterward; do not divert into general UX/framework work.

## D-069 - Review cash-purpose allocations without rewriting posted finance

- Date: 2026-09-10. Status: implemented on `codex/finance-cash-allocations`; [validation and limits](FINANCE_CASH_ALLOCATIONS_2026-09-10.md).
- Goal: complete historical cash classification and mixed generated-payment reporting under M01 before expanding surrounding UX/framework work.
- Decision: attach immutable proposals and independent decisions to the posted JEV in the Finance store. Require exact positive allocations covering each scoped cash line, a supporting reference, current office/role authority and a pinned source/scope. New reports retain the chosen approved version; original journal and earlier output evidence stay unchanged.
- Concurrency: lock the same posted journal before proposal/version and review changes. An ordinary unique current pointer and ordinary `(entry, version)` uniqueness preserve native identities. Competing approvals based on the same version cannot both win; stale proposals are returned and replaced. This is a bounded source-specific workflow, not another policy/configuration engine.
- Alternatives/tradeoffs: rewriting posted fields loses original evidence; fake financial reversals change the ledger for a reporting-only purpose; a single scalar category cannot split one payment. Separate metadata adds one preparation/review step while preserving the independent decision and historical output. Current reporting-governance permissions plus Accounting source access are reused; additional general work-adapter expansion is deferred.
- Reversal boundary: inherit approved allocations only along an actual same-fund, exactly mirrored financial chain. Retain the original category and apply the current debit/credit sign. An explicitly reviewed classification on the reversing entry takes precedence.
- Limits/revisit: reviewer evidence determines real cash purpose; amount checks do not establish that every purpose is factually correct. Complete four-statement notes/packages, signed references, local cash scope/form acceptance and M02 prior-payable linkage remain open. Broader concurrency and LGU acceptance are not established by this path's native test.

## D-068 - Report cash from explicit source purposes and reviewed cash scope

- Date: 2026-09-10. Status: initial Cash Flow implementation validated in v0.7.75; native/source and broad SQLite regression passed. [Calculation, evidence and remaining functions](FINANCE_CASH_FLOW_2026-09-10.md).
- Goal: complete M01 cash reporting from actual source-to-ledger-to-output evidence, preserving separate stores and immutable financial history.
- Decision: reuse independently reviewed statement mappings for the cash/equivalent inventory and existing journal/posting-rule lines for cash purposes. Keep gross receipts/payments, mixed manual principal/interest, internal transfers, exchange effects, non-cash exclusions and actual reversal lineage distinct. Preserve blank legacy rule snapshot checksums; never infer cash purpose from an expense account or JEV description.
- Alternatives/tradeoffs: all assets are not cash; voucher recognition is not actual payment; netting every cash journal would lose gross flows. Explicit cash inventory and line purpose support correct calculations but leave old blank history as visible exceptions. A scalar generated bank instruction cannot allocate mixed purposes merely by adding a label.
- Next required functions: controlled historical classification without fake financial reversals, reviewed splits for mixed generated payments, and complete statement-package integration. These remain M01, not deferred UX/acceptance substitutes. Confirm actual local cash/equivalent and any overdraft scope and accepted form detail separately.

## D-067 - Classify actual net-assets movements in the existing ledger

- Date: 2026-09-10. Status: implemented and validated in v0.7.74 on the statement-movements branch. [Evidence and limits](FINANCE_STATEMENT_MOVEMENTS_2026-09-10.md).
- Goal: complete M01 financial calculations before additional UX or surrounding infrastructure.
- Decision: use explicit existing-JEV source choices for policy changes, prior-period errors, opening restatements, direct-equity revenue and other equity movements. Preserve independent posting, complete source evidence and reversal ancestry. Do not infer purpose from descriptions or create another ledger/configuration engine.
- Calculation: retain contra-account signs by statement class, reconcile movements against assets less liabilities per fund, and compute the prior-year comparison independently. Missing opening evidence, unexplained direct-equity movements and equation differences remain visible exceptions. Verified zero-opening declarations are evidence; absent journals alone are not. Only an actual reversal lineage can neutralize an unclassified adjustment for a same-period correction.
- Tradeoffs: explicit source classification adds a preparation choice and requires correction of ambiguous historical movements. It avoids falsely presenting every equity adjustment as operating performance or a prior error. A fixed accounting calculation with retained source classifications is easier to audit than arbitrary report-row arithmetic; future national/local presentation changes still require reviewed implementation/template changes.
- Limits/revisit: Cash Flow, complete statement-note/package integration, exact accepted layouts and local workflow replay remain open. Published municipal examples support the rows, not local legal acceptance. Revisit classification when concrete source transactions require a distinction not covered here.

## D-066 - Keep closing transfers out of period operating performance

- Date: 2026-09-10. Status: native numerical defect reproduced; repair verified in v0.7.73 through broad SQLite and affected MySQL regression plus XLSX amount assertions.
- Goal: correct source-to-ledger-to-output results before completing the missing M01 statements.
- Evidence: an independently posted 1,250.00 revenue-to-equity closing transfer made the performance statement report 0.00 surplus. [Reproduction and validation](FINANCE_STATEMENT_CLOSING_2026-09-10.md) retain actual commands, output assertions and the separate native-fixture correction.
- Decision: introduce an explicit nominal-closing JEV source using existing preparation, balancing and independent posting. Limit its account types to nominal/equity transfers. Follow actual reversal ancestry for statement classification; exclude closing transfers from operating activity but retain them in ledger, position balances and statement source evidence. Do not infer purpose from descriptions or silently relabel historical journals.
- Alternatives/tradeoffs: excluding all adjusting entries would hide real period adjustments. Reading free text cannot establish accounting meaning. A second reporting ledger would duplicate authority. The existing journal source and correction lineage provide the needed distinction, at the cost of an explicit classification and governed correction of old ambiguous closes.
- Boundaries: this does not complete Cash Flow/Net Assets statements, historical corrections, comparative/form fidelity or LGU acceptance. Other statement presentation questions, including contra balances, require specific reproduction before reliance. The time-zone prerequisite was fixed only to make native validation faithful, not to expand unrelated infrastructure.


## D-083 - Correct receipt posting errors without erasing actual payment history

Date: 2026-09-12. Development decision; not LGU policy approval.

The existing receipt workflow could withdraw unposted approval but could not correct a posted receipt. A detached journal reversal would leave its operational allocation and filing context unchanged. The chosen route retains an immutable error proposal, independent review and original receipt, reserves restored withholding under the existing Accounting-owner lock, and posts a separate exact reversal before releasing the original allocation from the correction date. Submission and posting both check financial mirrors. Unposted withdrawal preserves the approval and discarded request chain.

This uses existing source requests, journal posting, reservations and office permissions. It avoids editing posted history or treating an actual outgoing agency payment as a receipt correction. The tradeoff is a full receipt reversal and fresh replacement rather than an in-place partial edit; this retains an intelligible source-to-ledger chain. Revisit for independently authorized actual bank repayments, other banks/fees and agency credit/offset dispositions, without weakening dated capacity or filing evidence. See [scope, evidence and remaining work](FINANCE_POSTED_RECEIPT_CORRECTIONS_2026-09-12.md).

## D-084 - Connect actual collections and deposits to one retained source chain

Date: 2026-09-12. Development decision; not acceptance of an official receipt or local Treasury procedure.

Observed eGAPS collection/deposit menus identify a missing source workflow; balanced manual journals and bank matching do not capture receipts, explicit deposited shares or collector availability. Use immutable receipt/deposit source versions, independently reviewed existing Finance recipes and the existing Accounting posting service. A deposit moves receipt cash to its selected bank without recognizing revenue again. Treasury-office serialization coordinates reservations, corrections and cross-store recovery; posted correction releases require dated, verified exact reversal evidence.

Keep entry, review, journal posting and export permissions separate. A collection officer does not inherit disbursement or posting authority. Preserve rejected/withdrawn approvals, original posted sources and separately issued printable bytes. The tradeoff is explicit source versions and correction lineage rather than editable posted rows; it reuses existing setup, numbering and ledger contracts instead of introducing another workflow engine or ledger. Historical corrections retain their original recipe while taking the current numbering sequence.

This implements the reviewed cash-collection/deposit scenario, not all collection instruments, liquidation/advance subsidiaries, prescribed form layouts, actual refunds or full M03 parity. Revisit these boundaries against the actual inventory and local procedures; do not infer them from a menu or passing scenario. See [implementation, validation and limitations](FINANCE_COLLECTIONS_IN_PROGRESS.md).

## D-085 - Separate recognized officer advances from liquidation authority

Date: 2026-09-12. Development decision; local accounting timing and forms still require acceptance.

Use an explicit governed advance-asset instruction and the existing DV/payable/payment chain to retain officer identity and original source evidence. Do not infer an advance from an asset code, payee label or generic liquidation transaction kind. A reviewed gross asset/payable recognition recipe must name an employee payee; existing independent posting and actual bank release retain their separate meanings. Advance schedules and control comparisons use debit balances while payable and withholding outputs retain credit balances.

This reuses the existing journal/subsidiary and output mechanisms. The tradeoff is a narrowly supported recognition recipe rather than arbitrary advance timing or immediately claiming a complete liquidation module. Aggregate recognized assets cannot authorize liquidation. Next require explicitly selected original advances, actual release evidence, dated partial applications/refunds and correction lineage. Revisit the supported recipe against real local advance procedures, without rewriting posted history. See [scope and validation](FINANCE_ADVANCES_IN_PROGRESS.md).

## D-086 - Apply accepted expenses to the original released advance

Date: 2026-09-12. Development decision; not local form or operational acceptance.

Reuse the existing immutable voucher posting request, governed recipe and independent Accounting JEV for expense liquidation. Each application selects an original officer advance, retains accepted expense documents and verifies its actual reconciled disbursement. Serialize reservations and posting on the default case before Finance journal locks; check dated capacity at the application and all later known source boundaries. Pending/posting recovery consumes one reservation, and native races verify competing proposals, materialization and posting.

This closes a concrete source-to-ledger/output gap without another ledger or workflow engine. The tradeoff is explicit original-source evidence and an initial expense-only recipe; aggregate officer balances, generic “liquidation” labels and detached reversals cannot establish cash availability or corrections. Retain discarded drafts and independent withdrawal events; preserve previously exported bytes. Actual refunds, posted source corrections and other locally used advance scenarios remain the next functional work. See [scope and validation](FINANCE_ADVANCE_LIQUIDATIONS_2026-09-12.md).

2026-09-13 extension: [issuance-time payment evidence](FINANCE_ADVANCE_ISSUANCE_2026-09-13.md)
accepts the actual reviewed payment timing but still waits for actual officer release.
Native recovery testing requires case-before-posting-request order for ordinary voucher
reconciliation as well as advance applications; never automatically replay financial actions
to conceal an inverted lock order. Refund receipts remain separate unfinished functionality.

## D-087 - Retain actual officer refunds in the existing collection workflow

Date: 2026-09-13. Development decision; official receipt/form and LGU acceptance remain separate.

Use an explicit original-advance choice on the ordinary Treasury receipt. Retain the
officer and original Accounting source, post cash debit/advance credit independently,
and use existing deposit allocations and exact source corrections. Expense and refund
reservations share the original case lock and dated released capacity. A correction
restores capacity from its actual date; later corrections cannot fund earlier shortfalls.

This reuses existing immutable Treasury sources and Accounting journals instead of
adding a second refund ledger or treating returned officer money as revenue. The tradeoff
is explicit source selection and additional subsidiary validation through collection
review, posting and corrections. Preserve department/role boundaries, issued bytes and
the distinction between accounting correction and actual new cash movement. See
[scope, tests and remaining work](FINANCE_ADVANCE_REFUNDS_IN_PROGRESS.md). Revisit the
supported receipt basis against actual local cash/direct-bank practices and prescribed forms.
