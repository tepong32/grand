# Ordinary clerk handoffs: scoped counts and current work

Bounded foundation checkpoint on `codex/finance-clerk-handoffs`, based on published
v0.7.171 / `06494330`. The original Finance goal and purchased Budget → Accounting
→ Treasury scope are unchanged. Production remains NO-GO.

## Findings and repairs

MEDIUM, pre-existing aggregate exposure: a requesting-office employee's department
dashboard counted other offices' voucher cases even though its linked workbench
excluded them. A six-case, two-office reproduction showed dashboard counts 2 / 4 /
2 versus the permitted queue/open/completed counts 1 / 2 / 1. The reproduction
failed before repair, with both test stores cleaned up. Git blame dates the global
query to August 26 and role-stage counting to August 28, before the recent auth pass.

Dashboard aggregates now reuse `vouchers.case_exports.visible_cases_for_user`,
including completed history. No new permission or narrower Finance-wide scope is
invented. Requesting clerks see their own office; the existing UAT viewer's broader
read scope remains intact. Read requests do not change case versions or stages.
Two new regression identities compare the dashboard with its actual workbench.

LOW, demonstrated navigation friction: one actionable payable was below eight
empty queues on the Accounting reviewer's My Work page. At 390 pixels wide the
page measured 5,878 pixels tall. Non-empty groups now appear first; the same empty
groups and exact queue links remain available in a closed native HTML disclosure.
The same fixture now measures 2,909 pixels, with no horizontal page overflow.
Expanding the disclosure restores all eight links. Counts, source queries, task
identities, CSV export, permissions and financial transitions are unchanged.
The existing table markup is shared by both lists rather than copied.

## Browser evidence

The existing ordinary-workflow fixture used real services to create approved
appropriation, posted ARO, certified OBR, source-linked payable and independent
opening evidence in isolated SQLite default/Finance stores. All authority,
documents and physical evidence are explicitly synthetic. Login state was supplied
for synthetic actors; this does not retest password sign-in or provision operators.

The requesting clerk followed dashboard → Finance → My Work → Waiting → the same
case. Waiting identifies Accounting's review queue and supplies no invented due
date. The independent Accounting reviewer sees one ready item linked to that same
case and OBR-2026-CYCLE-001, with claim/allocation 1,000 / 1,000 and difference zero.
The case displays its review controls. Treasury's dashboard/entry is reachable but
has no ready task for this earlier stage. No financial button was submitted.
Readback confirms unchanged case version 2, payable-review stage and one journal.

Desktop/mobile screenshots were inspected. Relevant retained examples:

- [Requesting-office waiting](../output/playwright/clerk-requesting-waiting-mobile-20261014.png)
- [Reviewer before](../output/playwright/clerk-reviewer-ready-mobile-20261014.png)
- [Reviewer after, mobile](../output/playwright/clerk-reviewer-ready-mobile-after-20261014.png)
- [Reviewer after, desktop](../output/playwright/clerk-reviewer-ready-desktop-after-20261014.png)
- [Original obligation and review controls](../output/playwright/clerk-reviewer-case-desktop-20261014.png)

The existing CLI's update notifier produced a process-exit assertion during a
version check. Its documented `NO_UPDATE_NOTIFIER` switch was used for subsequent
CLI invocations, which completed successfully; no software upgrade or application
setting change was made. The owned browser and loopback fixture server were closed.

## Actual validation

FAIL — PRE-EXISTING, reproduced: the new requesting-office count test failed on the
original global query; log `.tmp/clerk-dashboard-scope-before.log`, exit 1. PASS:
two focused tests after repair, 0.555s, no skips. Before the My Work simplification,
the 31-case dependent scope passed on SQLite / 14.990s and native / 19.890s.

Final PASS after all source/template changes: 31 exact cases on SQLite / 14.630s
and native MySQL / 19.586s, no skips, exit 0 and both stores destroyed. Scope:
department presets/dashboards, Finance entry/attention and existing voucher
requesting-office visibility/UAT read boundaries.

```text
python -X utf8 .tmp/intake_primary_sqlite.py departments.test_dashboard_presets departments.tests.DynamicDepartmentDashboardTests finance.test_operations vouchers.tests.VoucherWorkflowTests.test_requesting_office_case_visibility_is_department_bound_while_finance_remains_shared vouchers.tests.VoucherWorkflowTests.test_read_only_uat_viewer_can_preview_offices_without_action_authority --verbosity 2
python -X utf8 .tmp/intake_primary_native.py <the same labels> --verbosity 2
```

Logs/actual exit receipts: `.tmp/clerk-final-{sqlite,native}*`. Native used the
verified owned loopback fixture with fresh fixed test schemas; it was shut down
after test-store cleanup. `git diff --check` PASS. Installed-VM publication and
current-code remote CI are separate gates, recorded in CONTINUE.md.

NOT RUN — OUT OF SCOPE: full bank release/signing/office exercise, printer fidelity,
operational restore and LGU acceptance. The earlier service/output replay supplies
separate settlement evidence; this browser replay does not claim those later
screen actions were performed. FG-01/07/11 advance within this bounded scope, but
the full foundation gate remains open. See the [remaining work](FINANCE_REMAINING_WORK_2026-10-14.md)
and [ordinary output map](FINANCE_REQUIRED_OUTPUT_MAP.md).
