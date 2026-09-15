# GRAND - repository guide

## Project context and documentation map

Department-aware Django platform for municipal public services and internal operations. Core domains include assistance, identity/departments, reporting, records, physical custody, Finance setup, Accounting, Budget and vouchers.

### Durable boundaries

Cheque exceptions (2026-09-15): user has no local procedures and authorizes public-source
research, modular implementation and human resolution of rare cases. Missing local
paperwork must not block ordinary Finance development. Separate reported presentation,
actual bank disposition and system approval; never invent acknowledgement, release or
ledger evidence. Use reviewed applicable posting rules and retained physical custody.
See [modular design and implementation checkpoints](docs/FINANCE_CHEQUE_EXCEPTION_DESIGN.md).

Product direction (2026-09-10, clarified): finish Finance functionality and demonstrate source-to-ledger-to-output parity first; eGAPS is the capability floor, not the design ceiling. Then complete the actual inventory, ordinary office scenarios, exact outputs, clerk usability and operational acceptance, in that order. Preserve account-based web access, authorized WFH and maintainable national/COA/DBM changes. Keep eGAPS untouched. Do not expand UX, framework, collaboration or surrounding infrastructure ahead of unresolved functionality unless needed to complete or validate it. Retain sound financial architecture and explicit on-site signature/custody duties. See [modernization priorities](docs/FINANCE_MODERNIZATION_PRIORITIES.md).

Keep the default and Finance databases separate; never merge Finance into the default store. Preserve department/role boundaries, independent maker-checker approval, immutable financial history and correction lineage. Finance UAT Viewer membership denies financial mutation even when operational permissions are also granted; preserve separately authorized read/export access. Production secrets/settings are environment-driven. GRAND creates valid backup/export artifacts; TraceSync transports them and does not establish backup validity or restore acceptance.

Performance statements separate explicit nominal closing transfers and their actual reversal lineage from period activity while retaining complete source evidence and position/ledger balances. Net-assets statements classify direct-equity movements explicitly, retain contra signs by account class and require opening/comparative evidence. Never infer journal purpose from free text or relabel posted history. See [closing boundary](docs/FINANCE_STATEMENT_CLOSING_2026-09-10.md) and [statement movements](docs/FINANCE_STATEMENT_MOVEMENTS_2026-09-10.md).

Cash Flow uses a reviewed cash/equivalent account scope and explicit cash-line purposes, with gross flows, non-cash exclusions, internal-transfer checks and retained reversal meaning. Blank legacy posting-rule snapshots retain their checksums. Historical/mixed purposes use separately reviewed allocations over immutable posted sources; never invent ledger reversals merely to attach reporting metadata. Lock the same source journal for proposal versions and approval changes, retain prior decisions/output versions, and require exact mirrored financial lines for reversal inheritance. See [cash-flow coverage](docs/FINANCE_CASH_FLOW_2026-09-10.md) and [allocation validation/state](docs/FINANCE_CASH_ALLOCATIONS_2026-09-10.md).

Native backup capture requires distinct schemas on one verified MySQL server and a held global read lock across both dumps. Missing privilege, lost lock identity or unsupported/different-server topology fails closed. Approve the server-wide write-pause window operationally; never substitute two independent snapshots or fabricated historical capture evidence. See DATABASE_BACKUP.md for the current supported recovery boundary.

New statement-note packages require all four statements with matching period, source journals, visible financial rows and cross-statement totals. Preserve historical two-member snapshots without backfilling approvals. Lock the existing department before note versions/approval candidates; stale older versions cannot replace newer approvals. Issued ZIPs retain original statement bytes and printable notes immutably. Bundle download requires both note export and current report-download/source visibility. All four statements select source funds before calculation and preserve every required financial row/column; arbitrary statement-row filters and regrouping are rejected. See [package evidence](docs/FINANCE_STATEMENT_PACKAGE_2026-09-10.md) and [fund-scoped generation](docs/FINANCE_STATEMENT_FUNDS_2026-09-10.md).

Individual payable claims use original posted liability credits and linked applications on the existing journal. Check dated capacity and remaining DV reservations under source-credit locks and new claim identities under the existing fund lock. A new reservation must fit its effective date and subsequent posted movements; later reversals cannot fund earlier shortfalls, and applications consume an active hold rather than counting twice. Existing-key recovery must also recheck the requested date with the retained hold counted once; see [recovery validation](docs/FINANCE_CLAIM_RECOVERY_DATE_2026-09-10.md). See [dated reservation checks](docs/FINANCE_DATED_CLAIM_RESERVATIONS_2026-09-10.md). Default-store case locks serialize validation; deterministic case/version reservation evidence supports interrupted cross-store recovery. Prior-payable payment/cancellation/return uses exact source links and governed rules, never duplicate expense recognition or detached manual reversals. Do not infer historical invoice attribution or treat a payable balance as free capacity/Treasury cash. See [claim ledger](docs/FINANCE_PAYABLE_CLAIMS_2026-09-10.md) and [DV integration, recovery and limits](docs/FINANCE_PRIOR_PAYABLE_DV_2026-09-10.md).

Earlier accruals use the existing governed posting request before DV creation. Require actual recognition date/evidence and a reviewed gross-payable recipe; independent posting creates the original claim. Serialize pre-DV materialization, return and reconciliation on the default case lock. A posted accrual cannot be erased by returning its payable; later DV corrections retain it. See [earlier-accrual boundary](docs/FINANCE_EARLIER_ACCRUAL_2026-09-10.md).

Historical claim identity/applications use independently reviewed attribution versions over unchanged posted lines. Approval shares the Fund/original-line lock order with claim recognition and reservations; current links must reproduce their retained evidence. DV reservations pin the approval version they used. Capture one approved attribution set per output; do not reread current pointers between amounts and retained evidence. Payable schedules, report sources and control reconciliation use the same reviewed projection while retaining original subsidiary detail. Never infer omitted payments, split a consolidated line implicitly, or adopt an unreconciled generated payment cycle into a second settlement route. See [historical attribution and limits](docs/FINANCE_HISTORICAL_CLAIMS_2026-09-10.md).

Posted prior-payable deductions are corrected by exact source reversal, followed by independent posting and a fresh DV reservation. The v0.7.89 cancelled-check checkpoint permits correction after every unreleased check has a reconciled no-entry cancellation or exact posted payment cancellation; pin its evidence and retire replacement eligibility only after the deduction correction posts. See [the active correction boundary](docs/FINANCE_CANCELLED_CHECK_CORRECTIONS_2026-09-12.md). Pending corrections and remittance allocations share the Accounting-owner reservation lock across releases; display labels are not deduction identities. No posted JEV or tax evidence is rewritten. See [deduction correction boundary](docs/FINANCE_DEDUCTION_CORRECTIONS_2026-09-10.md).

Consolidated DVs retain explicit per-claim gross/deduction/net allocations for one payee and fund. Create the entire Finance reservation group atomically under sorted original-credit locks; recover only the same immutable allocation. Partial checks require explicit shares, and replacements retain the original shares. Closing a returned check retires only its independently posted shares on the actual return date, preserving other instruments and earlier-date capacity controls. See [consolidated settlement](docs/FINANCE_CONSOLIDATED_DV_2026-09-10.md).

### Development state

The v0.7.112 development principal-redemption checkpoint links a new receipt to the exact posted
bank-return receivable and reserve that principal once. A replacement manager's/cashier's
cheque stays pending until independently confirmed clearing; later dishonour selects a
new linked return instead of reopening the original reservation. Exact receipt correction
retires its hold only after reconciliation and preserves dated deposit history. Versioned
internal TracePoint associations retain separate physical handovers, independent mistaken-link
withdrawal and joint visibility for custody-bearing outputs. External delivery, combined
penalties and officer timing remain open. See
[current redemption scope](docs/FINANCE_CHEQUE_REDEMPTIONS_IN_PROGRESS.md).

Incoming cheque bank returns have a validated v0.7.111 development checkpoint. Reuse collection sources with
explicit original receipt/deposit links and a generated active return identity. The
first reviewed treatment credits only the original whole-cheque bank amount and debits
an explicit receivable; combined deposits and earlier clearing stay intact. Source-error
correction retires the return only after its exact reversal posts and reconciles, with
dated replacement checks. Preserve the original cash-flow purpose; mixed-purpose returns
need explicit component treatments. See [active scope](docs/FINANCE_CHEQUE_RETURNS_IN_PROGRESS.md).

Outgoing cheque presentation reports retain original Treasury ownership, independent
Accounting findings and immutable exports. Case-first locks and a generated active key
serialize open reports and conflicting actions. Financial closure requires the original
completed source; no-entry replacement issuance cannot hide an unfinished release payment.
Never fabricate physical release or acknowledgement to close a bank finding. See the
[v0.7.110 development checkpoint](docs/FINANCE_PAYMENT_PRESENTATIONS_IN_PROGRESS.md).

Incoming cheque capture retains instrument identity and requires whole-amount
deposit allocations. Independent bank clearing proposals pin the original posted receipt,
whole deposit and bank evidence; correction and clearing share the Treasury lock.
Never infer clearing from posting or create a duplicate bank credit for clearing.
The v0.7.108 development checkpoint is locally validated; dishonour and redemption remain unfinished.
Officer cheque refunds must not release capacity as if they were cash. See
[current cheque scope](docs/FINANCE_CHEQUE_COLLECTIONS_IN_PROGRESS.md).

Direct-bank collection receipts now retain explicit bank-credit references and reviewed
bank mappings through ordinary/multi-charge capture and officer refunds. Posted bank
credits are excluded from cash deposit capacity and selection. Preserve original advance
locks/subsidiaries and pinned routing; never infer a legacy receipt's payment method from
its account code. This is included in v0.7.108; initial validation had 34 SQLite tests passed/five native
skips and all 39 native tests passed, including five races. This is not cheque lifecycle
or form acceptance. See [bank collection scope](docs/FINANCE_BANK_COLLECTIONS_IN_PROGRESS.md).

Multi-charge receipts are included in v0.7.108: combine explicit amounts from existing reviewed
collection types only when their cash account, fund and release agree. Keep distinct
cash-flow purposes on separate cash lines; deposit the full receipt cash once. Retain
each recipe and one actual receipt total; review detects changed recipes and posting
uses pinned approvals. Deposits and exact corrections reuse the original source route.
See [scope and validation](docs/FINANCE_COLLECTION_CHARGES_IN_PROGRESS.md).

Netted remittance receipts are included in development v0.7.108 after
integrated v0.7.107: retain explicit
reviewed gross liability allocations, deducted fee expense/evidence and actual net bank
credit. Fee expense selection is independently reviewed and pinned; later setup changes
cannot reroute it. Keep no-fee proposal history unchanged and reverse cash, fee and
withholding together through the existing receipt correction. See
[scope and current validation](docs/FINANCE_RECEIPT_FEES_IN_PROGRESS.md), D-092.

The v0.7.106 returned-advance checkpoint pins new bank-return JEVs to their original payment with
distinct purpose evidence and unchanged cash-flow meaning. Availability reads retain
the original release while withholding observed returns. Original correction
now pins the reviewed return, retires its authorization during posting reconciliation,
and excludes only verified retired instruments from replacement release evidence.
Fully corrected liquidations and refund/deposit histories pin dated journal/source,
fund and department evidence before original reversal and reproduce it afterward
without recursive reuse authorization. Outstanding applications remain blocked;
do not open correction based on BANK_RETURNED status alone. See
[current work and validation](docs/FINANCE_RETURNED_ADVANCES_IN_PROGRESS.md).

Unpaid original advance corrections use an exact independently posted reversal before
reopening the existing payable/Budget/DV route. The active cancelled-check extension
requires all checks to be unreleased with reconciled cancellation evidence; only posted,
reconciled original corrections retire old replacement routes. Issuance-time cancellations
pin exact original payment reversal lineage. See [current validation](docs/FINANCE_CANCELLED_ADVANCES_IN_PROGRESS.md).
Replacement recognition pins its
predecessor; initial intake allocations remain historical while guided revisions
validate current allocations. Linked Budget corrections lock default-store fiscal
issuance boundaries and cases before Finance locks, serializing with replacement DV
issuance. Paid/returned-instrument original corrections remain open. See
[scope and validation](docs/FINANCE_ADVANCE_RECOGNITION_CORRECTIONS_IN_PROGRESS.md).

Posted expense-liquidation corrections use exact independently posted reversals and
retain original request/JEV/subsidiary evidence. Only reconciled correction movements
restore dated expense/refund capacity; exclude correction debits from original advance
selection. Replacements pin their corrected predecessor. Case-before-Finance locking
and independent discarded-draft withdrawal remain mandatory. See [posted expense-liquidation corrections](docs/FINANCE_LIQUIDATION_CORRECTIONS_2026-09-13.md), D-088.
Released/returned original-recognition corrections and other advance scenarios remain open.

Officer cash refunds reuse the Treasury receipt/deposit source and credit the original
advance subsidiary. Refund and expense holds share dated capacity and default-case-first
locks. Independent withdrawal preserves evidence; exact posted receipt correction releases
its hold only from the correction date, after allocated deposits are corrected. See
[refund implementation and validation](docs/FINANCE_ADVANCE_REFUNDS_IN_PROGRESS.md).
Expense-liquidation corrections are covered by D-088; original corrections progress
through D-089/D-090 above. Released/returned scenarios remain unfinished.

Voucher posting reconciliation acquires the default case before its posting request,
including payment recovery, to match advance reservations and avoid lock inversion.
Issuance-time advance posting remains distinct from actual officer release; only actual
release with claimant/receipt supplies liquidation capacity. See
[issuance source evidence](docs/FINANCE_ADVANCE_ISSUANCE_2026-09-13.md).

Officer advances retain explicit employee asset/payable recognition and [source-linked expense liquidation](docs/FINANCE_ADVANCE_LIQUIDATIONS_2026-09-12.md), D-085/D-086. Verify actual released payment evidence, select the original advance, reserve dated amounts under the default case lock and independently post accepted expenses against that asset. Keep default-case-before-Finance lock order, scope reservation locks to liquidation requests, preserve exact subsidiary evidence and require witnessed independent withdrawal before releasing unposted holds. Standard Accounting roles have specific advance read/export access; UAT mutation denial remains. Cash-refund coverage is recorded in D-087; expense corrections are covered by D-088 and original corrections by D-089/D-090 above; released/returned and other advance scenarios remain open. Do not infer or relabel historical advances; see CONTINUE.md for current validation.

The v0.7.98 development [M03 collection/deposit](docs/FINANCE_COLLECTIONS_IN_PROGRESS.md) checkpoint connects receipt capture, explicit partial deposits, independent posting, corrections and retained printable source copies. Copies preserve original rendered content/evidence and recheck current read/export authority; later corrections do not rewrite earlier copies. Native allocation/correction/materialization races, role boundaries and full SQLite regression pass. This does not establish official receipt/form parity, all collection instruments, liquidation/advances or operational acceptance. Continue missing functional breadth; further remittance fees/dispositions remain open and must not indefinitely displace the observed missing domains.

The v0.7.96 development checkpoint supports governed [posted receipt correction](docs/FINANCE_POSTED_RECEIPT_CORRECTIONS_2026-09-12.md), D-083: retain original receipt/payment/filing evidence, reserve dated restored withholding, independently post an exact reversal, then release allocations from the correction date. Both submission and posting verify mirrored financial lines. Unposted withdrawal requires all retained drafts discarded and preserves approval history. Actual [partial/full receipts](docs/FINANCE_REMITTANCE_RETURNS_IN_PROGRESS.md) and [corrected settlement](docs/FINANCE_RETURNED_REMITTANCE_SETTLEMENT_2026-09-12.md) are implemented and tested. The v0.7.97 [receiving-bank route](docs/FINANCE_RECEIPT_BANKS_2026-09-12.md) pins approved setup/mapping evidence through incoming posting, exact correction and exports; later mapping edits cannot reroute approval. Fees/netted receipts and actual agency payment/credit/offset dispositions remain open.

Cancelled and reviewed bank-return payment cycles support governed deduction correction followed by fresh DV settlement, retaining original instrument and review history. Dated withholding capacity checks every later posted boundary; later restorations cannot fund earlier shortfalls. See [returned-check corrections](docs/FINANCE_RETURNED_CHECK_CORRECTIONS_2026-09-12.md), [issuance-source handling](docs/FINANCE_ISSUANCE_BANK_RETURNS_2026-09-12.md), [dated withholding](docs/FINANCE_DATED_WITHHOLDING_CORRECTIONS_2026-09-12.md) and D-081.

Reviewed [historical invoice splitting](docs/FINANCE_HISTORICAL_SPLITS_IN_PROGRESS.md) and [shared applications](docs/FINANCE_SHARED_APPLICATIONS_IN_PROGRESS.md) preserve immutable original lines, complete approval groups, pinned invoice shares and dated capacity through DV settlement, returns, corrections and outputs. See D-080. Generated-history adoption remains unfinished.

Personal-handoff adapters are implemented; generic following, shared views and notifications remain deferred. Prioritize missing Finance functionality and statement calculations before operational scrutiny. CONTINUE.md records the current development checkpoint and actual validation; development capabilities do not establish master integration or full Finance parity. Production remains NO-GO until functional completion, broad regression, operational scrutiny, critical-gap verification and LGU acceptance pass. Preserve separate databases and existing acceptance gates.

### Read next

- [README.md](README.md)
- [CONTINUE.md](CONTINUE.md)
- [docs/ROADMAP.md](docs/ROADMAP.md)
- [docs/FINANCE_ROADMAP.md](docs/FINANCE_ROADMAP.md)
- [docs/IMPLEMENTATION_DECISIONS.md](docs/IMPLEMENTATION_DECISIONS.md)
- [docs/FINANCE_ROADMAP_COMPLETION_AUDIT.md](docs/FINANCE_ROADMAP_COMPLETION_AUDIT.md)
- [docs/FINANCE_OPERATIONAL_SCRUTINY.md](docs/FINANCE_OPERATIONAL_SCRUTINY.md)
- [Current scrutiny evidence](docs/FINANCE_SCRUTINY_2026-09-09.md)
- [Native identity audit and reproduction scope](docs/FINANCE_NATIVE_INVARIANT_AUDIT_2026-09-09.md)
- [docs/DATABASE_BACKUP.md](docs/DATABASE_BACKUP.md)
- [docs/DEPLOYMENT_RENDER.md](docs/DEPLOYMENT_RENDER.md)
- [Continuation entry point](CONTINUE.md)

### Project validation

Use the documented Python 3.11 environment. Start with `python manage.py test <affected_app_or_test_label>`; include dependent Finance/Accounting/Budget/voucher/reporting tests when their contracts change. Preserve both test-database aliases. Finance Completion Gate, cross-cycle changes and production readiness require substantially broader regression and operational validation.

Finance persistence changes require native MySQL validation as well as SQLite: SQLite does not expose all field-capacity failures, and MySQL omits conditional unique constraints. Budget and active bank matches use generated nullable keys for their required conditional identities. Preserve migration duplicate preflights; investigate historical duplicates instead of silently rewriting financial evidence. Use the fresh two-store runner in [FINANCE_NATIVE_TESTING.md](docs/FINANCE_NATIVE_TESTING.md): a prior transaction-test flush removes migration-seeded data while retaining migration records. A passing sequential suite does not establish concurrency safety for other unsupported constraints. Bank-match conflicts are reported only after the owning transaction rolls back; never implicitly replay financial actions or continue inside an aborted automatic-match batch.

## Repository continuity and proportional testing

- Maintain this root AGENTS.md in version control as portable operational context. Preserve applicable nested instructions. Update it in the same phase as durable architecture, security, integration, major completion/deferral or testing-policy changes.
- Keep this file concise: identity, boundaries, decisions and a documentation map. Replace stale summaries; never append transcripts, line-by-line diaries or duplicate full specifications.
- Before substantial work read AGENTS.md, CONTINUE.md (and its canonical handoff target), the relevant roadmap/architecture/feature documents, recent Git history/status and affected tests. Reconcile stale snapshots against source; do not ask the user to repeat documented context.
- At task completion update the canonical handoff for immediate state, actual validation, blockers and next steps; update the roadmap for agreed direction changes and specialized architecture/feature/audit/testing documents where applicable. Cross-link instead of duplicating them. Do not invent completed phases or new priorities.
- Test the changed area first: direct unit/feature tests, related integration tests and dependent regressions. Expand for shared models/services/utilities, auth/permissions, middleware, schema/migrations, settings/environments, shared UI, cross-app APIs, reporting, jobs or build/deployment changes. Uncertain impact requires broader validation.
- Full suites are appropriate for broad refactors, cross-module/security/infrastructure changes, major milestones and release/production gates, not automatically every isolated edit. Preserve stricter project-specific safety, reachability, hardware and release checks.
- Record relevant commands, scope rationale and outcomes in the handoff or appropriate validation report: PASS; FAIL - CAUSED BY CURRENT WORK; FAIL - PRE-EXISTING (with evidence); NOT RUN - OUT OF SCOPE (with rationale); NOT RUN - ENVIRONMENTAL (with limitation).
- Investigate failures before calling them unrelated. Fix regressions caused by the change and document evidence for pre-existing failures. A skipped test or unperformed human/operational acceptance is never a pass.
- Keep documentation, code and validation evidence sufficient for a fresh session to resume without a conversation transcript.
- Install additional standalone software/tooling under C:/xxx/_INSTALLS/_HERE/_xxx unless the user specifies otherwise.
