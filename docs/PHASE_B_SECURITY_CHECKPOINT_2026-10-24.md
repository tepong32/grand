# Phase B security checkpoint — 2026-10-24

## Baseline and boundaries

Parent: `5600a554b5f2333b089a7a9b168a8e93c5e44580`, the pushed P1 checkpoint
on `04b25bf7b1c18a1d3932596597ba629e240ba252`.
Original byte fingerprint: `694a0b0ba89e3371e05c776c5e564f2f69b9682b938f80daca6774030c2ccd42`.
Original P1 workspace: `C:/Users/Administrator/.codex/worktrees/grand-p1-20261023-2408aa82de6e`.
Current independent clone: `C:/Users/Administrator/.codex/worktrees/grand-secure-phase-b-20261024-6ea2569a2637`.
Branch: `codex/secure-phase-b-20261024`.

Before editing, the parent, clean index/tree, all 1,491 recorded source/helper
bytes, original refs and stash identities were verified. The existing uncommitted
48-file Phase B workspace, recovery archive, operator stores and other worktrees
are not implementation targets. No reset, stash application, Finance integration,
production operation or eGAPS access. New test databases/media are disposable.

Risk tier: authorization, private evidence, transaction/concurrency and shared
access contracts. Finance remains NO-GO. Finance implementation waits for explicit
review and acceptance of this security checkpoint.

## Final behavior and focused scope

- The existing owning default-store write lock and fresh credential/eligibility
  checks from P1 remain. SQLite reserves its writer before reading; InnoDB uses
  the owning row write lock followed by a current locking read. Staff SQL writes
  contend on that row. Token expiry/revision is rechecked after a wait. No implicit
  action retry. Citizen writes still save only name, email and phone.
- `AssistanceRequestEditForm` now rejects privileged or unknown submitted fields,
  including ownership, workflow/claim/activation fields and staff decisions. The
  entire edit fails with a generic form error/400; allowed contact changes remain.
- Document writes keep request-before-document locking. A late insert/timeline
  failure rolls back database rows and removes only the newly saved file; originals
  remain. Post-commit cleanup errors cannot remove a committed current replacement.
  A removed document is re-uploaded through its existing unique request/type row,
  retaining identity and removal/upload timeline, rather than failing a duplicate
  insert. These are current mutable attachments, not new immutable archives.
- Assistance/memo downloads reject unsupported filesystem roots as unavailable
  before opening storage. No remote-storage qualification or checksum backfill.
- Private-chat guards on start/link/unlink remain. The binding service also rejects
  missing tokens rather than falling back to internal snapshot authority. The
  private success message accurately states that notifications are disabled.
- Both staff notification callers pass the request to
  `telegram_bot/services/notification_service.py::send_telegram_update`.
  This is an intentional deny-all delivery gate, with no transport construction,
  async sending, enable flag or inferred qualification. Legacy, negative/group,
  newly bound and self-asserted qualified destinations are all denied. Email and
  staff decisions retain their existing behavior. There is no live delivery path.

Before enabling any notification, define independently reviewable persisted
qualification evidence, current destination/authority and revocation rules;
coordinate both callers and the service boundary, then qualify with mocked
transport. No production qualification policy is guessed in this checkpoint.
Storage cleanup can still require operational recovery if the storage itself
refuses deletion; the generic logged failure contains no path or credential.
A database transaction is not a general transactional-filesystem/outer-transaction
rollback guarantee. Production private media/proxy rules, log protection and
storage/recovery qualification remain open.

## Evidence and efficiency

Final runtime/test/helper fingerprint (1,499 files):
`35c8b18b6584e6701249cc875d20d68453f7ac2789cf58da56038aaeb55a3c53`.
The manifest covers current Python/HTML/text source, the retained baseline helper
bytes, new verification helpers and their input scopes. Documentation is recorded
separately. Historical evidence is retained, not overwritten or relabeled.

Python: `C:/xxx/_INSTALLS/_HERE/_xxx/grand-checkpoint209-pdf-venv/Scripts/python.exe`.
The isolated runners disable dotenv, replace both aliases and media/private/export/
backup destinations before Django setup, use local-memory email and explicitly
forbid real Telegram HTTP requests. Native setup uses an owned loopback clone of
an inactive system-only template, with identity/schema/strict/timezone/shutdown
checks intact. No operator database is a test connection.

Focused SQLite PASS: 42 discovered, 32 passed /10 native-only race skips,
1.042s test execution (84.219s including setup), exit 0. The native-only skips are
not passes. The affected native scope covers all focused behavior and races plus
Records, Assistance, Profiles, Reporting, authentication, shared GSO downloads and
department dashboard regressions. This replaces duplicate focused-native plus
expanded-native runs with one relevant native dependency run; it is not a full
project/Finance suite. Native PASS: 328/328, zero skips, 94.498s test execution
(367.922s including setup), exit 0. All ten owning-row races executed. Both
aliases were destroyed, the owned server stopped and the original system-only
template hashes matched. Both runs verified the same source/helpers unchanged.
AST parsing of all 1,121 fingerprinted Python files and `git diff --check` PASS.

Raw log SHA-256:
- SQLite: `0b30b13bfd1ab13f509ef0aa96f73f8d6f8da030d324dbf3d3a8d82d071db03d`.
- Native: `f645f18bfb7ab7768488703397994c1485ea26c512acb98f1d0542997c2ab4f1`.

Exact command arrays, test identities/skips, source manifests, raw compressed
logs, helper snapshots, runtime versions and native owner/VM preview receipts are
portable in `docs/evidence/phase-b-security-2026-10-24/`. No original recovery
archive, operator data or credentials is included. No fresh application-test
failure occurred; historical Phase B/P1 failure and parser records remain intact.
The final native set includes the dashboard own-custody grant/count assertion;
its service, template and tests remain unchanged.

NOT RUN: a second expanded SQLite run (the changed paths passed focused SQLite;
the native dependency run covers the affected shared graph), full-project suites,
hosted exact-candidate/master CI, browser/mail delivery, production media/proxy/log
protection, restore/recovery and operational/LGU acceptance. These are not passes,
not waived gates and not a production-readiness or integration approval.

The owning write-lock races use events and observed InnoDB lock waits, with both
persisted-state and competing-outcome assertions: approval, claim, deactivation,
PIN/email changes, expired-after-wait, stale delete/replace/upload and citizen-first
then staff approval. Both allowed and denied request, document, profile and chat
paths are included. Current wrapper identity parsing handles joined test output;
older receipts retain their documented parser discrepancy and supplemental audit.

## VM procedure and acceptance boundary

Inspected `C:/Users/Administrator/Desktop/GH/workflow_version_manager/README.md`,
the CLI and `version_manager/git.py`/`release.py`. CLI preview proposes a release
`v0.7.188`, changes VERSION/CHANGELOG and creates a tag. That operation conflicts
with this task's no-release/no-tag boundary and is NOT RUN.

The existing installed `GitService.commit(files, message)` operation is separate:
it stages only the explicit reviewed paths and creates one ordinary checkpoint
commit. Use that unmodified VM package helper for a tag-free checkpoint, inspect
its exact file list/message/parent/tree before execution, then verify the resulting
commit and clean tree. Do not call the release/tag/push-tag operations, change VM
implementation/configuration, merge master or claim this is a VM release. The
checkpoint still needs the owner's explicit acceptance; creating it does not
satisfy the acceptance condition or authorize Finance implementation.

## Next Finance milestone, after explicit checkpoint acceptance

Read-only inspection confirms canonical `codex/finance-cheque-redemptions` remains
at `ce0c7243fb6b2c189bd2356dba866261e8897508` (v112), with a September handoff.
It is not the current implementation baseline. The accepted security branch must
first be reconciled with the unmatched published v188–v210 work and preserved
local work; do not replace current source with that stale checkout or infer
acceptance from version tags.

The current baseline's `docs/FINANCE_ROADMAP.md` names evidence-backed numerical
Form 1 treatment through `docs/FINANCE_FORM1_TREATMENTS_IN_PROGRESS.md` as the next
functional milestone, only where official instructions and retained evidence
justify a recipe. Reconcile that direction against the newer chain before choosing
the bounded implementation; do not replay completed signing/UI work or invent
unsupported numerical/local policy. Finance NO-GO, exact-revision CI, native,
financial integrity, operational scrutiny and LGU acceptance gates remain intact.
No Finance implementation has begun during this security session.
