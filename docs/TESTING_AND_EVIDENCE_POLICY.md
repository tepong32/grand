# Risk-Based Testing and Evidence Reuse

Status: repository-wide development policy. This policy improves local feedback efficiency; it does not weaken any required merge, release, security, Finance, or production gate.

## Purpose

Run the smallest sufficient local verification for the current change, then expand according to risk. Avoid repeating identical successful checks without a code, test, dependency, configuration, schema, or environment change that could invalidate their evidence. Do not optimize for a low test count; optimize for fast, trustworthy feedback while preserving complete required coverage.

## Required workflow

Before testing, identify:

1. The exact changed files and behavior, including templates, migrations, settings, dependencies, generated artifacts, and test fixtures.
2. Affected callers, workflows, roles/permissions, data boundaries, and downstream behavior.
3. The relevant tests and prior evidence, including the exact commit/source state, test identities, runtime settings, database backend, dependencies, and environment.
4. The risk tier below, and any mandatory verification gate that applies regardless of tier.

Run focused tests first at a coherent checkpoint. Do not start duplicate or overlapping processes for the same work. If a focused test fails, investigate and preserve the actual failure before expanding or rerunning; never relabel a failure as a pass because a later, different command succeeds.

## Risk tiers

| Change class | Minimum local verification |
| --- | --- |
| Documentation-only | Diff/format/link or document-specific checks. No application test suite unless the document changes executable instructions, contracts, or policy relied on by automation. |
| Isolated copy, template, or navigation | Relevant rendering/view tests, role/access checks where applicable, and the affected user journey or dependent navigation regression. |
| Local business rule or contained workflow | Focused unit/feature tests plus directly affected integration and downstream workflow tests. |
| Shared service/model, cross-office flow, auth/permissions, API, report, job, settings, or common UI | Focused tests plus affected dependent workflows and regression coverage for shared consumers; expand if impact is uncertain. |
| Finance calculations or writes, source-to-ledger attribution, audit/private evidence, authorization, migrations/schema, transaction boundaries, concurrency/idempotency, quantities/custody, destructive actions, or recovery | Focused tests plus the required native database/backend and relevant integrity/security/integration checks. Expand broadly whenever impact crosses boundaries or cannot be bounded confidently. |
| Broad refactor, dependency/runtime change, build/deployment infrastructure, milestone, candidate integration, or release | Broad or full applicable validation and all established exact-revision gates. |

These are minimums, not ceilings. A change spanning tiers uses the highest relevant tier. A test skipped by a backend or environment is not evidence that the behavior passed there.

## Reusing prior evidence

Reuse a prior pass only when it is demonstrably relevant and all assumptions that affect the result remain unchanged:

- the exact relevant source and configuration state;
- test identity and assertions;
- dependencies/runtime and relevant environment;
- schema/migration assumptions and database backend;
- permissions, fixtures, or external conditions that the test depends on.

Record the prior commit or evidence reference, its scope, and why it remains applicable. A nearby commit, similar test name, successful SQLite run, or unchanged service file alone is not sufficient. Any relevant change invalidates the affected evidence and requires a fresh run. Preserve failed/cancelled runs and explain their status; they are not passes.

## Database and CI gates

- SQLite is useful for fast local feedback but does not replace native MySQL evidence for behavior that depends on MySQL semantics or for required native Finance persistence coverage.
- SQLite-only skips must be identified as skips. They must never be counted as native passes. Required native MySQL coverage must actually execute.
- Keep the established hosted exact-candidate/exact-published-revision CI and release gates intact. Do not weaken assertions, coverage, partitions, required jobs, timeouts, retries, or status checks as a shortcut.
- Any proposal to change hosted CI policy is a separate evidence-backed proposal: measure actual job and setup durations, identify duplicated work, prove complete coverage and dependency/order assumptions, assess failure/retry behavior, and obtain an explicit owner decision before changing required gates.
- Do not infer that a cancelled, partial, stale, or different-revision CI run authorizes integration or publication.

## Reporting

For each meaningful checkpoint, record concise evidence in `CONTINUE.md` or the relevant validation report:

- changed scope and risk tier;
- exact commands/tests and the relevant test identities;
- pass/fail/skip/deferred/unavailable outcome, including counts and duration when available;
- prior evidence reused and the reason its assumptions remain valid;
- failures retained and investigated;
- required native/backend, security, integration, or broader checks still outstanding;
- next action and any real blocker.

Use unambiguous statuses such as PASS, FAIL - CAUSED BY CURRENT WORK, FAIL - PRE-EXISTING (with evidence), NOT RUN - OUT OF SCOPE (with rationale), NOT RUN - ENVIRONMENTAL (with limitation), SKIPPED BY BACKEND, and CANCELLED. A skip, cancellation, unperformed human acceptance, or missing environment is never a pass.

## Sensitive-information review before VM commit

Owner instruction, 2026-10-24: perform a quick local review of repository-tracked
content and the final intended/staged commit for credentials, tokens, API/private
keys and similar sensitive information. Inspect findings without printing values.
Remove exposed real secrets from source using the existing environment/private
configuration pattern; preserve legitimate synthetic fixtures and placeholders.
Re-scan the final candidate. Record scope, redacted classifications and limitations.

Keep unrelated ignored private configuration, operator databases and recovery
archives in place and out of commits/logs/uploads. A quick text scan does not
establish exhaustive detection or inspect binary/database records. If a real
credential was already committed/published, flag revocation/rotation: current-file
removal cannot revoke it or erase history. Published-history rewriting, protected
data deletion and service credential changes require separate authorization.
This review supplements all existing checks; it does not replace any CI gate.

## GRAND-specific safety boundary

Finance remains NO-GO until its documented financial-rule, native persistence, cross-office, output, human acceptance, and operational gates are satisfied. Risk-based local testing does not certify official accounting interpretations, forms, signatures, production readiness, migration readiness, backup/recovery, or LGU acceptance. Do not deploy or run production operations without explicit authorization.

## Codex session protocol

Use this procedure for each implementation session and each meaningful change set. It operationalizes the policy above; it does not replace project-specific acceptance criteria or mandatory CI gates.

1. **Scope before execution.** Read `AGENTS.md`, the relevant roadmap/feature contract, and the current `CONTINUE.md` checkpoint. Inspect the actual working-tree diff and identify changed files, behavior, callers, affected roles, persistence, external boundaries, and likely regressions. Do not run suites merely to rediscover already-documented project context.
2. **Choose the risk tier.** Classify the change using the highest applicable tier in this policy. If impact cannot be bounded confidently, move up a tier. State the selected tier and required checks in the session plan or checkpoint.
3. **Run the smallest useful fresh checks first.** Run tests for the changed behavior and its closest regression boundary. Prefer one coherent focused command over multiple overlapping commands. Wait for an owned test process to finish before starting a conflicting runner. Capture exact command, test IDs/count, result, and duration when available.
4. **Expand at decision points.** Add dependent workflow, authorization, integration, backend-specific, security, migration, or broader regression checks when the change crosses a boundary, a focused result exposes a defect, shared consumers may be affected, or risk remains uncertain. Do not repeatedly rerun a broad suite after every isolated edit when a relevant focused check gives timely feedback; instead run the appropriate broader set at the next coherent integration/milestone checkpoint.
5. **Finance is never a shortcut tier.** For Finance calculations/writes, source-to-ledger attribution, permissions, audit/private evidence, transactions, concurrency/idempotency, migrations, recovery, quantities/custody, or destructive actions, run focused checks plus all relevant integrity/security/integration and required native MySQL validation. Never defer a critical check merely to save time. A feature-focused pass does not establish Finance acceptance or production readiness.
6. **Reuse evidence narrowly.** Before reusing a previous result, record its exact commit/source identity and test scope, then verify that relevant code/configuration, assertions, dependencies/runtime, schema/backend, fixtures/permissions, and environment assumptions are unchanged. Re-run only the invalidated or newly affected checks where the policy permits. If any assumption is uncertain, obtain fresh evidence.
7. **Keep gates unchanged.** Preserve established exact-candidate/exact-published-revision hosted CI, native MySQL, security, release, Finance acceptance, integration and human/operational acceptance gates. Do not change workflow definitions, required jobs, assertions, coverage, retries, timeouts, partitions, or branch protections as part of ordinary feature work. Any CI-efficiency redesign requires a separate measured, coverage-proven proposal and explicit owner approval.
8. **Report honestly and stop at evidence boundaries.** Distinguish PASS, FAIL, SKIPPED BY BACKEND, CANCELLED, NOT RUN, DEFERRED and UNAVAILABLE. Explain why checks were not run and list remaining required checks. Never turn a skip, partial run, stale run, different-revision pass, or human acceptance not performed into a pass.
9. **Update the handoff.** At a coherent checkpoint or session end, update `CONTINUE.md` with the changed scope, risk tier, exact validation evidence, reused evidence and justification, failures/deferred checks, remaining gates, and next action. Update durable instructions or feature contracts only when the change establishes a lasting rule; cross-link instead of copying long policy text.

### Session stopping rule

A session may finish a bounded implementation slice when its focused acceptance checks pass and the remaining broader checks are explicitly scheduled for the next appropriate integration gate, provided no mandatory check was deferred and the handoff clearly states what remains. A failing focused check, unresolved critical integrity/security issue, unknown high-impact blast radius, or required gate failure blocks that slice from being described as complete. Continue other independent, safe work only when doing so does not obscure or bypass the blocker.

