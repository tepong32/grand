# CI class-ownership compatibility blocker — 2026-10-24

## Approved repair: current status

The user explicitly answered “Approve compatibility repair.” Implemented only
`FORM1_INTAKE_ORIGINAL_OWNER=0`, retaining intake on worker 6 and every existing
gate/job/test. All nine prior synthetic owner 3 unit identities remain, now with an
explicit synthetic pin; two added checks assert the actual production pin 0,
complete coverage and rejection of any other original owner. Fresh unit PASS 11/11.
Complete application discovery PASS 3,061 IDs /374 classes, every original ID
retained and each selected once across all 8 unchanged workers. This is static
discovery, not 3,061 executed passes. Final native Budget run PASS 297/297, zero skips, 357.957s on the same final source.
Hosted candidate/primary CI and release/integration remain NOT RUN.

## Observed failure and proposal before approval

**VERIFIED local failure; integration BLOCKED.** This is not a hosted Actions run.
No CI source, rule, job, timeout, coverage assertion or required gate was changed.

Complete current discovery finds 3,061 distinct tests /374 classes. The unchanged
`scripts/ci_test_runner.py:24` rejects every eight-worker partition because
`budget.test_form1_package_intake.Form1PackageIntakeTests` has sorted index 112,
original owner 0; the retained rule requires original owner 3 before moving it to
worker 6. The failure occurs before application tests execute.

The exact accepted `f1711038e30c0e684e99b4fd5172eebacfe99436` versions of
`budget/tests.py` and `budget/test_quarterly_concurrency.py` were loaded in memory
into disposable settings. These are the only existing test modules modified by the
Finance slice; its new support module contains only plain mixins. Discovery of that
baseline projection finds 3, 029 tests and the **same 374-class set**, same index 112
and same error in all eight partitions. All baseline IDs remain in current discovery,
with 32 added methods. No accepted worktree was edited or used for test execution.
This establishes **FAIL — PRE-EXISTING** for this pure class-name partition rule;
it is not a complete baseline runtime/test pass.

Source comparison 04b25bf→f1711038 shows five added Assistance classes before the
intake class: CitizenMutationConcurrencyTests, CitizenMutationTests,
DocumentAtomicityTests, NotificationCoordinationTests and UnqualifiedStorageTests.
Four additional Records/Telegram classes sort later. Five preceding classes shift
107 (owner 3) to112 (owner 0). The earlier Finance candidate added two more classes;
its first local passes predate this review. Those new Budget scenarios now live in
existing AnnualBudgetPreparationTests /QuarterlyPlanningConcurrencyTests via plain
mixins, retaining every prior ID and adding no discovery class. New-layout focused/
native results must be recorded separately; earlier passes are retained unchanged.

## Separate proposal; not implemented

The smallest compatibility proposal is an explicitly reviewed original-owner pin
of 0 for this exact class inventory, retaining the intake move to6, all existing
whole-class assignments, complete discovery, exact-revision coverage aggregation,
zero-native-skip enforcement and every required job. This is a CI policy change
and requires the separate owner decision mandated by
[testing policy](TESTING_AND_EVIDENCE_POLICY.md#database-and-ci-gates).
No automatic retry, omitted test, wider timeout or relaxed assertion is proposed.

[Static proposal](evidence/finance-budget-2026-10-24/ci-compatibility-proposal.json)
records all eight candidate counts, retained prior IDs and32 added methods. Counts
are not runtime/load-balance evidence. Before implementation, review the class
movement and available durations; then test the partition/aggregation guards,
complete discovery/ownership and all mandatory exact-candidate/primary jobs.
A larger stable-assignment redesign is outside this bounded proposal.

Alternative: relocate the accepted security test classes to different existing
owners/namespaces. This changes more verified test identities/fixture lifecycles
and needs broader revalidation. Do not rename tests merely to satisfy a numeric
pin without a coherent ownership and evidence plan.

Until a separately approved repair and required exact-revision gates pass, do not
integrate or publish a release. Local Budget behavior can be checkpointed with this
blocker recorded. Finance remains NO-GO for production.
