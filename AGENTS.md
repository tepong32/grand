# GRAND - repository guide

## Project context and documentation map

Department-aware Django platform for municipal public services and internal operations. Core domains include assistance, identity/departments, reporting, records, physical custody, Finance setup, Accounting, Budget and vouchers.

### Durable boundaries

Product direction (2026-09-10, clarified): finish Finance functionality and demonstrate source-to-ledger-to-output parity first; eGAPS is the capability floor, not the design ceiling. Then complete the actual inventory, ordinary office scenarios, exact outputs, clerk usability and operational acceptance, in that order. Preserve account-based web access, authorized WFH and maintainable national/COA/DBM changes. Keep eGAPS untouched. Do not expand UX, framework, collaboration or surrounding infrastructure ahead of unresolved functionality unless needed to complete or validate it. Retain sound financial architecture and explicit on-site signature/custody duties. See [modernization priorities](docs/FINANCE_MODERNIZATION_PRIORITIES.md).

Keep the default and Finance databases separate; never merge Finance into the default store. Preserve department/role boundaries, independent maker-checker approval, immutable financial history and correction lineage. Finance UAT Viewer membership denies financial mutation even when operational permissions are also granted; preserve separately authorized read/export access. Production secrets/settings are environment-driven. GRAND creates valid backup/export artifacts; TraceSync transports them and does not establish backup validity or restore acceptance.

Performance statements separate explicit nominal closing transfers and their actual reversal lineage from period activity while retaining complete source evidence and position/ledger balances. Net-assets statements classify direct-equity movements explicitly, retain contra signs by account class and require opening/comparative evidence. Never infer journal purpose from free text or relabel posted history. See [closing boundary](docs/FINANCE_STATEMENT_CLOSING_2026-09-10.md) and [statement movements](docs/FINANCE_STATEMENT_MOVEMENTS_2026-09-10.md).

Cash Flow uses a reviewed cash/equivalent account scope and explicit cash-line purposes, with gross flows, non-cash exclusions, internal-transfer checks and retained reversal meaning. Blank legacy posting-rule snapshots retain their checksums. Historical/mixed purposes use separately reviewed allocations over immutable posted sources; never invent ledger reversals merely to attach reporting metadata. Lock the same source journal for proposal versions and approval changes, retain prior decisions/output versions, and require exact mirrored financial lines for reversal inheritance. See [cash-flow coverage](docs/FINANCE_CASH_FLOW_2026-09-10.md) and [allocation validation/state](docs/FINANCE_CASH_ALLOCATIONS_2026-09-10.md).

Native backup capture requires distinct schemas on one verified MySQL server and a held global read lock across both dumps. Missing privilege, lost lock identity or unsupported/different-server topology fails closed. Approve the server-wide write-pause window operationally; never substitute two independent snapshots or fabricated historical capture evidence. See DATABASE_BACKUP.md for the current supported recovery boundary.

New statement-note packages require all four statements with matching period, source journals, visible financial rows and cross-statement totals. Preserve historical two-member snapshots without backfilling approvals. Lock the existing department before note versions/approval candidates; stale older versions cannot replace newer approvals. Issued ZIPs retain original statement bytes and printable notes immutably. Bundle download requires both note export and current report-download/source visibility. See [package evidence and remaining fund-scope work](docs/FINANCE_STATEMENT_PACKAGE_2026-09-10.md).

### Development state

Personal-handoff adapters are implemented. Current work prioritizes missing Finance functionality and statement calculations; operational scrutiny follows functional completion. Generic following, shared views and notifications remain deferred. Read the current branch’s CONTINUE.md for its checkpoint; a documentation update from master does not merge or publish development-branch work. Production remains NO-GO until functional completion, broad regression, operational scrutiny, critical-gap verification and LGU acceptance pass. Preserve the separate database and existing acceptance gates.

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
