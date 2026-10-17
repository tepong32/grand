# GRAND carry-over checkpoint

User direction 2026-10-17: first reach a reviewed integration-ready GSO checkpoint,
VM-commit it, then carry GSO into GRAND and continue GSO/Finance development on
parallel branches of that one repository. This supersedes treating official local
form details as a prerequisite for development integration. Use fill-in placeholders.
The original complete-system requirements remain; this checkpoint is not production
acceptance, completed historical import or a COA compliance certificate.

## Source and review scope

Product source3e2e535 (PAR preparation release), inventory migration0029 and optional
adapter0007. Actual GRAND candidate a533482, remote master32ab046. Preserve the
candidate's Finance work and production NO-GO. Latest user direction explicitly
requires considering the paused Finance work: use a533482 as the trial base,
retain its history, and validate the combined candidate before primary promotion.

Review covered application imports, authority/department adaptation, swappable
user relations, adapter dependencies, native router behavior, URL/template namespaces,
private-storage configuration and the test boundary. Existing receiving/custody/
stock/Finance race and recovery receipts remain in validation; this is an integration
review, not a claim to have independently re-audited every historical line.

- Product modules have no direct imports of the standalone user/src/home shell.
  Native user relations use AUTH_USER_MODEL and swappable migration dependencies.
  Access helpers resolve native Department/EmployeeProfile and explicit permissions;
  Finance UAT mutation restrictions remain. No role auto-grant is part of transfer.
- Both inventory and inventory_finance tables belong to default. GRAND's router
  reserves finance for accounting/budget and disallows other migrations there.
  Adapter FKs point to default authorities; retained native Finance UUIDs/snapshots
  are not cross-database foreign keys or automatic posting authority.
- Adapter initial migration depends on departments0005 and vouchers0038; existing
  actual-GRAND harness verifies these alongside all inventory/adapter migrations.
  Keep every migration name and portable identity; do not squash or regenerate.
- All templates are namespaced inventory/inventory_finance. Mount the existing
  named routes at /gso/inventory/ and /gso/claim-support/ using GRAND authentication.
  Do not bring standalone login, password-reset, src/settings or root URL configuration.
- GRAND does not currently define DISPOSAL_PRIVATE_ROOT. Destination wiring must
  explicitly provide a protected root and validate it outside public media/static
  locations, carrying the existing shell's safety requirements into native settings.
  The test harness supplies isolated storage; that alone is not destination wiring.
- Standalone tests use user.models and cannot be copied into GRAND's default test
  discovery unchanged. Native gso_integration_tests cover the shared-authority paths;
  wire those into GRAND's actual test/coverage runner, preserving standalone tests
  in the source repository for traceability. Do not silently discard failures or
  claim the native suite replaces every standalone test's coverage.

## Transfer and integration sequence

1. Create a separate GRAND codex trial integration branch/worktree from the latest
   paused Finance candidate a533482, preserving its original branch and coordination
   note. This incorporates the user's latest instruction to consider the last Finance
   work. Remote master remains32ab046; candidate and remote feature match.
   Existing candidate CI38976836601 passed security and mysql but verify failed
   because three SQLite shards were cancelled. This is incomplete validation,
   not evidence of a code defect or a pass. Combined release must satisfy all gates.
2. Copy only tracked product files under inventory/ and inventory_finance/, excluding
   standalone test*.py/tests.py for explicit later adaptation. Review receipt at
   .tmp/grand-transfer-review.json pins181 product files and43 excluded test files.
   Keep source repository/history and record exact release SHA in the target commit.
   Transfer native integration tests and relevant docs separately with their source
   receipt; adapt test discovery and harness URL/configuration to real destination.
3. Register the two apps, mount namespaced routes, configure/validate private storage
   and add native GSO navigation under existing permissions. Reuse native users,
   departments, Records, sessions, Finance settings and backup ownership.
4. Exclude operator DBs, prototype authentication/session data, .env, uploads,
   backups, caches, private test receipts and the standalone user/src/home apps.
   This is code integration, not a business-data import. Later imports use explicit
   identity maps and retained source evidence; user confirmed prototype credentials
   were isolated, so do not invent a live credential-reuse incident.
5. On disposable native databases, validate actual destination settings, migration
   plan/application, default/finance placement, private downloads, native grants/UAT,
   critical receiving/stock/custody/Finance paths and PAR preview. Reuse focused tests
   during edits; run broad native/hosted gates at this major integration checkpoint.
6. Confirm actual trial-branch test results, then GRAND VM-commit and merge only
   after target review and required GRAND gates.
   Publication is user-authorized; retain all required CI and production restrictions.
   Subsequent GSO and Finance work uses parallel branches of the GRAND repository;
   the GSO source repository becomes the preserved pre-integration reference.

## Decision evidence

The unchanged product apps already passed actual-GRAND native workflows at prior
milestones. This checkpoint adds native PAR authorization/no-write coverage and a
single full native GRAND run on current source. Record its actual result in CONTINUE
and validation before the checkpoint VM commit. Passing authorizes development
carry-over with the destination wiring above; it does not claim that wiring is done.

Validation: full actual-GRAND native suite PASS147/147, zero skips,64.560s on
a533482; both disposable schemas destroyed. See CONTINUE for the exact command.
Destination wiring and combined hosted release gates remain pending.
