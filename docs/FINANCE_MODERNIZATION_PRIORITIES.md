# GRAND Finance modernization priorities

Direction accepted by the user on 2026-09-10. This is a focused work queue under the [Finance roadmap](FINANCE_ROADMAP.md), not a replacement roadmap or a production-completion claim.

## Authoritative delivery order (clarified 2026-09-10)

Finish GRAND Finance as a complete and demonstrably usable successor. eGAPS capability and familiar office workflows are the parity floor, not the design ceiling. Frameworks, configurable datasets, menus and passing tests do not substitute for demonstrated functional parity.

1. Complete concrete financial gaps and prove source-to-ledger-to-output behavior.
2. Complete the actual eGAPS inventory and identify unmatched locally used functions/reports.
3. Demonstrate ordinary Budget, Accounting and Treasury scenarios end-to-end, including corrections.
4. Match required DV, OBR, JEV, advice, RCI/RD, tax and financial-statement outputs: layouts, signatories, copies and printing behavior.
5. Validate realistic clerk workflows and familiar navigation; improve next actions, My Work/status visibility, duplicate encoding and audit transparency through individual web accounts and authorized WFH.
6. Complete concurrency, recovery, access, change/reproduction and LGU acceptance assurance.

Preserve sound architecture, immutable financial history, balancing, independent approval, auditability and database/recovery boundaries. Do not expand UX, framework, collaboration, discovery, qualification, acceptance or other surrounding machinery before unresolved Finance functionality unless required to complete or validate the current priority. Native validation needed for a financial persistence change is such a prerequisite; unrelated infrastructure expansion is not. The already implemented navigation slice is retained, but further UX work follows functional completion.

## Product goal

Improve the eGAPS office experience through GRAND: familiar Budget, Accounting and Treasury registers and terminology, delivered on the web through individual accounts and current department/role permissions. Support authorized work from home without making physical custody, wet signatures or instrument release appear remote when they still require an in-office act. eGAPS remains an untouched reference; do not modify its files, records or databases or introduce a runtime dependency.

Make future national-government, COA and DBM changes manageable through reviewed, effective-dated rules, mappings and editable forms wherever the existing engine supports them. A new accounting behavior may require code and tests; never promise that every regulatory change is configuration-only. Preserve prior versions and issued evidence, and confirm current authority and local applicability before official use.

## Accepted priorities and evidence

The evidence column records the original assessment baseline. See Current execution below for subsequent implementation and validation.

| ID | Outcome | Current evidence / gap | Acceptance |
|---|---|---|---|
| M01 | Complete essential statements | eGAPS exposes Cash Flow and Changes in Net Assets/Equity; GRAND's registered statement datasets currently cover Position and Performance only. | Implement supported movements/classifications and independently reconciled statements; retain current accepted references and exact local forms. Cash position is not a cash-flow statement. |
| M02 | Complete payable recognition and settlement | `vouchers.services.validate_accounting` blocks earlier accrual and existing-payable settlement; the linking control remains future work. | One supported earlier-recognition-to-settlement chain without duplicate recognition; partial settlement, correction/reversal and source controls tested on both stores. |
| M03 | Resolve collection, liquidation and subsidiary breadth | eGAPS exposes collection/deposit and liquidation. GRAND has manual journals, configured liquidation decisions and payable/withholding subsidiaries, not demonstrated complete equivalent coverage. | Enumerate actual enabled scenarios; implement and replay missing source capture, outstanding balances, refunds, subsidiary controls and outputs. |
| M04 | Finish the read-only eGAPS inventory | Accounting/Budget menu review on 2026-09-10; live DV register observed. Cash Disbursement was enabled but not inspected internally after launcher loss. JEV navigation encountered server error 735. | Resume only safe navigation in a usable session; record menu observations separately from demonstrated behavior. No record actions, printing, export, repair or database access implied. |
| M05 | Match everyday office work and outputs | Budget exposes receipts/proposals, continuing authority/augmentation, financial plan/allotment advice and distinct accountability schedules. Accounting exposes RCI/RD, advice and BIR 2306/2307. Frameworks and source datasets do not prove each output. | Accepted report/form inventory; redacted supplier, existing-payable, advance/liquidation, receipt/deposit, returned-check and month-end examples with matching totals, timing, references and outputs. |
| M06 | Familiar, account-based web UX | GRAND already has permission-shaped workspaces and My Work. Some landing/detail copy exposes technical controls before everyday tasks; Budget entry currently goes directly to obligations. | Familiar register shortcuts, plain office language, clear next actions and expandable technical evidence; current destination permissions and source scopes preserved. Measure clerk search, encoding, corrections, screen changes and duplicate entry. |
| M07 | Maintainable changes and authorized WFH | Versioned setup, templates, web accounts and deployment foundations exist. Remote operational acceptance is unproven. | Demonstrate a reviewed rule/form change and old-output reproduction; named-account remote access/session/security and network-failure exercises; explicitly identify on-site signatures, printing and custody duties. No production exposure or remote-access deployment without its operational gates. |
| M08 | Finish operational assurance | v0.7.70 native baseline passed; policy/profile and outstanding-item concurrency scrutiny is incomplete and Docker startup is blocked. | Resume native reproduction in a disposable environment; retain recovery, segregation, named-user, printer and LGU acceptance gates. No production GO inferred from a UI or synthetic test. |

## Delivery rules

- Prioritize missing daily capabilities and output fidelity over new collaboration/framework expansion. Generic following, shared views and notifications stay deferred.
- Retain exact decimals, independent decisions, separate default/Finance stores, authoritative source checks and immutable correction lineage. Simplify their presentation rather than removing controls.
- The initial M06 navigation slice is retained. The clarified priority now puts M01–M03 financial gaps first; further M06 work follows functional completion. Financial persistence changes still require native validation.
- Use existing report, rule, form and task mechanisms; avoid a competing configuration framework or parallel authoritative status/ledger.
- Record observed eGAPS features, implemented GRAND behavior and external acceptance separately. No percentage-complete score based on menu counts.
- The 2026-09-10 comparison is source/menu evidence, not official legal interpretation or numerical parity. Refresh applicable primary sources before implementing financial calculations.

## Current execution

Current v0.7.86 prerequisite: [recovered claim dates](FINANCE_CLAIM_RECOVERY_DATE_2026-09-10.md) now receive the same dated-capacity scrutiny as new holds, without reserving the amount twice. The earlier-retry bypass was reproduced, then fixed; 39 affected SQLite and 39 native tests pass, including interrupted DV recovery/payment/export and five selected races. No schema or original-evidence changes. Historical source-line allocation and the preserved financial/office/acceptance work remain open.

Current v0.7.85 M02 work: [consolidated DVs](FINANCE_CONSOLIDATED_DV_2026-09-10.md) retain explicit claim gross/deduction/net and partial-check allocations, atomic Finance holds and exact payment/return/replacement lineage. A closing return retires only that check's shares on its actual date; other checks and replacement advice remain usable. Group deduction correction and interrupted handoff recovery are covered. PASS: seven focused SQLite scenarios, 31 native tests with four selected races, final full project 805 discovered / 788 passed / 17 native-only skips, 313.148 seconds. An older Budget fixture failure was reproduced on v0.7.84 and corrected without relaxing production guards. Consolidated historical source-line splitting, unreconciled generated-history adoption, later corrections and preserved M01/M03, office/output/usability/acceptance gates remain open. Production remains NO-GO.

Earlier checkpoint entries retain historical evidence; their remaining-work statements are superseded where a later checkpoint explicitly advances that work.

Current v0.7.84 M02 work: [historical claim attribution](FINANCE_HISTORICAL_CLAIMS_2026-09-10.md) independently reviews original credits and prior applications without changing journals. Claims, DV selection/reservations, exact reversals, payable schedules and report controls share the approved links. Each DV retains its selected approval version. Main implementation PASS: 5 focused SQLite tests; 41 native tests including six selected races; broader Finance regression 596 discovered / 581 passed / 15 native-only skips. After the final report-version consistency repair: 171 affected reporting/claim tests passed with 1 native-only skips, and 17 native tests passed. Consolidated historical line allocation, multi-claim DVs, generated-cycle adoption and remaining corrections are still open, alongside the preserved M01/M03 and office/acceptance gates. Production remains NO-GO.

Current v0.7.83 M02 prerequisite: [dated claim reservations](FINANCE_DATED_CLAIM_RESERVATIONS_2026-09-10.md) reject capacity restored only after the requested date or interrupted by a later posted application. Actual DV rejection, later-date payment and claim CSV pass. Validation: four focused SQLite tests; 30 native MySQL tests including five existing races; broader Finance regression 588 discovered / 576 passed / 12 native-only skips. Historical attribution, consolidated claims and the preserved financial/acceptance gates remain open. Production remains NO-GO.

Current v0.7.82 M02 work: [posted-deduction correction](FINANCE_DEDUCTION_CORRECTIONS_2026-09-10.md) supports exact reversal before any payment instrument, protected withholding capacity, independent posting, fresh DV validation/payment, signed tax output and pre-posting withdrawal. Historical attribution, consolidated claims, post-issuance/remitted-tax corrections and remaining Finance/acceptance gates are still open. Consult the actual validation record.

Current v0.7.81 M02 work: [earlier-accrual generation](FINANCE_EARLIER_ACCRUAL_2026-09-10.md) queues a reviewed pre-DV recognition request, creates the original named payable after independent posting and connects it to later DV deductions/payment without another expense. Pre-DV correction, immutable source evidence and recoverable handoffs use the existing stores and workflow. Read its actual validation record. Historical attribution, posted-adjustment corrections and consolidated multi-claim settlement remain unfinished; Finance production remains NO-GO.

Current M02 DV work: [prior-payable integration](FINANCE_PRIOR_PAYABLE_DV_2026-09-10.md) links one original claim/fund to a DV, reserves its gross amount and propagates applications through deductions and the governed payment/return cycle. Continue earlier-accrual request generation, historical attribution and outstanding correction scenarios; no wider parity or acceptance completion is claimed. Read the validation record for actual run status.

Current v0.7.79 M02 source work: [individual payable claims](FINANCE_PAYABLE_CLAIMS_2026-09-10.md) adds invoice-level journal links, dated outstanding amounts and explicit reversal behavior. Connect the still-blocked DV routes and earlier-accrual request generation next. Historical source attribution, payment/deduction/correction handoffs and actual office acceptance remain open.

Current v0.7.78: [source fund selection and complete rows](FINANCE_STATEMENT_FUNDS_2026-09-10.md) align Position/Performance with Net Assets/Cash Flow. Read the validation record for actual evidence. M02 prior-payable linkage follows; exact statement forms/reference comparisons and real office acceptance remain incomplete. The following entries retain their historical checkpoint scope.

The [four-statement package work](FINANCE_STATEMENT_PACKAGE_2026-09-10.md) adds all four note members, source/total consistency, movement-statement reference comparisons and immutable downloads containing actual report files and printable notes. M01 still requires common fund-scoped generation and protection against hidden rows in standalone Position/Performance reports; the package guard does not substitute for repairing those report paths. Then continue M02 prior-payable linkage.

Historical posted cash classification and mixed generated-payment allocations have advanced through a separate reviewed metadata path; [current implementation and validation](FINANCE_CASH_ALLOCATIONS_2026-09-10.md). Continue M01 with complete four-statement notes/packages and signed-reference controls after its regression gate, then M02 prior-payable linkage. Do not treat source calculation tests as exact local form acceptance.

M01 v0.7.75 checkpoint: [classified cash movements and source propagation](FINANCE_CASH_FLOW_2026-09-10.md) generate a comparative direct-method statement for supported lines. Its historical/mixed allocation gaps have advanced in the current work above; full statement-note/package integration remains open. Do not treat the dataset/preset as complete Cash Flow coverage or proceed to general UX while financial gaps remain.

M01 v0.7.74 checkpoint: the validated statement-movements branch adds a comparative net-assets output and corrects native-reproduced contra-account signs. [Calculation and validation record](FINANCE_STATEMENT_MOVEMENTS_2026-09-10.md). Cash Flow and complete statement-package/notes integration remain outstanding; exact local form acceptance is still separate. Existing statements below describing absent net-assets functionality refer to the original assessment baseline, not a completed parity gate.

The initial M06 navigation slice is implemented and validated; it does not close the broader UX acceptance requirement. Work now returns to source-grounded M01 missing statements and M02 payable linkage under the clarified functional-first order. See [CONTINUE.md](../CONTINUE.md) and [navigation validation](FINANCE_NAVIGATION_VALIDATION_2026-09-10.md) for actual evidence and immediate prerequisites.

M01 prerequisite: [FIN-GAP-036](FINANCE_STATEMENT_CLOSING_2026-09-10.md) fixes closing transfers erasing reported operating performance through an explicit closing/reversal distinction, verified on SQLite and MySQL in v0.7.73. Continue with the missing net-assets/cash-flow statements and their source classifications. This does not replace the missing-statement deliverables with a smaller completion claim.

M01 implementation entry points: `reporting/models.py` currently limits `FinanceStatementMapping` to Position/Performance; `statement_services.py` assumes only balance-sheet versus revenue/expense account coverage. `datasets.py` composes account balances, and `services.py` pins mappings for only those two dataset keys. Extend those contracts together with presets, forms, retained-run evidence and statement-package tests. Cash-flow classifications must distinguish actual cash movements from accruals and internal cash transfers; net-assets movements must distinguish opening balances, current results, closing transfers and other adjustments. Adding labels or treating every debit/credit as a cash flow cannot satisfy M01. Confirm applicable current primary references and local output requirements before selecting calculations; historical COA search listings alone do not establish current accepted forms.
