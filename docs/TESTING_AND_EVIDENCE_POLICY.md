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

## GRAND-specific safety boundary

Finance remains NO-GO until its documented financial-rule, native persistence, cross-office, output, human acceptance, and operational gates are satisfied. Risk-based local testing does not certify official accounting interpretations, forms, signatures, production readiness, migration readiness, backup/recovery, or LGU acceptance. Do not deploy or run production operations without explicit authorization.
