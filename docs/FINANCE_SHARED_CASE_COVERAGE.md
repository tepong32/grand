# Shared-case action coverage audit

This is the F1.5 functional adapter audit for FIN-GAP-003, not the mandatory post-Finance operational scrutiny. It maps the supported action stages in the Voucher Workbench to their exact source projections. A shared-case count and an instrument/child-action count use different units and need not be equal.

| Shared-case stage | Source action selector / projection | Evidence boundary |
|---|---|---|
| Shadow Budget draft | `legacy_budget_action_queryset` / legacy Budget task | Unlinked shadow compatibility only; explicit certification permission and current office |
| Payable preparation | `payable_action_queryset` / payable preparation task | Requesting/current office; retained claim and evidence gates |
| Payable review | `payable_action_queryset` / payable review task | Current Accounting office; excludes preparer/submitter |
| DV preparation | `dv_custody_action_queryset` / DV preparation task | Current office; Budget-certifier separation or governed exemption |
| Awaiting signatures | DV custody selector and `dv_signature_task_queryset` / print, custody and signature tasks | Current output/round and earliest eligible signature action |
| Accounting validation | `accounting_validation_action_queryset` / validation task | Current office; preparer separation or retained exemption/override |
| Recognition or event posting | `source_handoffs` and `journal_action_queryset` / source creation, JEV draft/review, source synchronization | Stored source/ledger identity; maker-checker; no duplicate draft/source task |
| Returned-item Accounting review | `returned_instrument_attention_queryset` / returned-payment task | Current and pinned Accounting office; excludes preparer; retained review version |
| Treasury check preparation | `treasury_payment_action_queryset` / check-preparation task | Current Treasury office and exact remaining amount |
| Accounting bank advice | `initial_advice_instruments` and `bank_advice_action_queryset` / initial check assembly or existing batch task | Current Accounting custody for its actions; independent review; explicitly permissioned Treasury submission remains distinct |
| Treasury release | `treasury_payment_action_queryset` / individual advised-instrument release task | Current Treasury office; acknowledged advice and exact retained claimant/release controls |

`apply_case_filters(... attention="ready_for_me")` additionally matches posting, advice and returned-item stages to those source selectors. A preparer waiting for independent advice/JEV review does not remain in a ready shared-case count merely because they hold the earlier preparation permission. Completed/cancelled case stages are not personal completion receipts; completed-by-me still requires attributed events in the later cross-cycle work.

Initial advice assembly projects each eligible issued instrument. Active draft/review/approved/submitted advice belongs to the batch adapter. Returned versions use their retained correction task. A check omitted from a successor and still pointing at the superseded version can re-enter assembly with its stable instrument Task ID and a changed source revision. The initial form uses the same scoped selector, preselects only an eligible UUID, and rejects stale/foreign links without creating a draft on GET.

Validation: 2 focused tests passed in 4.550 seconds; all 534 tests passed on the final source in 130.759 seconds. System, migration-drift, compilation and diff checks are clean. Edge layout verification passed at 1440px and 390px; the final 390px document scroll width is 390px. Existing stage-contract regressions live in `finance/test_work_tasks.py`; complete synthetic chains and the added source/initial-advice lifecycle, permission, stale-link and readiness tests live in `vouchers/tests.py`. This audit does not claim local legal/form acceptance or validate arbitrary corrupted historical imports.
