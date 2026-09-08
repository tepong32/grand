# GRAND - repository guide

## Project context and documentation map

Department-aware Django platform for municipal public services and internal operations. Core domains include assistance, identity/departments, reporting, records, physical custody, Finance setup, Accounting, Budget and vouchers.

### Durable boundaries

Keep the default and Finance databases separate; never merge Finance into the default store. Preserve department/role boundaries, independent maker-checker approval, immutable financial history and correction lineage. Production secrets/settings are environment-driven. GRAND creates valid backup/export artifacts; TraceSync transports them and does not establish backup validity or restore acceptance.

### Development state

Finance functional work remains ongoing. Read the current branch’s CONTINUE.md for its checkpoint; a documentation update from master does not merge or publish later personal-handoff work from development branches. Production remains NO-GO until functional completion, broad regression, operational scrutiny, critical-gap verification and LGU acceptance pass. Preserve the separate database and existing acceptance gates.

### Read next

- [README.md](README.md)
- [CONTINUE.md](CONTINUE.md)
- [docs/ROADMAP.md](docs/ROADMAP.md)
- [docs/FINANCE_ROADMAP.md](docs/FINANCE_ROADMAP.md)
- [docs/IMPLEMENTATION_DECISIONS.md](docs/IMPLEMENTATION_DECISIONS.md)
- [docs/FINANCE_ROADMAP_COMPLETION_AUDIT.md](docs/FINANCE_ROADMAP_COMPLETION_AUDIT.md)
- [docs/FINANCE_OPERATIONAL_SCRUTINY.md](docs/FINANCE_OPERATIONAL_SCRUTINY.md)
- [docs/DATABASE_BACKUP.md](docs/DATABASE_BACKUP.md)
- [docs/DEPLOYMENT_RENDER.md](docs/DEPLOYMENT_RENDER.md)
- [Continuation entry point](CONTINUE.md)

### Project validation

Use the documented Python 3.11 environment. Start with `python manage.py test <affected_app_or_test_label>`; include dependent Finance/Accounting/Budget/voucher/reporting tests when their contracts change. Preserve both test-database aliases. Finance Completion Gate, cross-cycle changes and production readiness require substantially broader regression and operational validation.

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
