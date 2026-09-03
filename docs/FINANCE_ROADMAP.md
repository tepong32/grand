# GRAND Finance complete-cycle roadmap

Status: canonical delivery roadmap for the professional GRAND Finance sub-application. The current implementation is a shadow/UAT foundation, not yet the LGU's authoritative finance system.

## Product outcome

GRAND Finance will reproduce the essential control coverage and official outputs of the observed eGAPS Budget Monitoring and Management, eNGAS/accounting, and Cash Disbursement modules without reproducing their workstation-bound client, maintenance-file menus, repetitive encoding, or generic Add/Edit/Delete interaction.

The destination is one web application with a shared transaction history and role-shaped workspaces:

- **Requesting offices** initiate funded requests and follow their own transactions;
- **Budget** governs annual appropriations, allotment releases, obligations, adjustments, and budget accountability;
- **Accounting** validates payables, prepares DVs and JEVs, posts to the books, closes periods, and produces accounting reports;
- **Treasury** manages cash availability, payment instruments, advice status, release, and bank reconciliation;
- **Finance administrators and reviewers** govern master data, templates, roles, readiness, reconciliation, and audit evidence.

Users should enter a fact once, at the office that owns it. The same case, stable identifiers, pinned configuration, supporting-document references, physical-custody evidence, accounting entries, payment instruments, and immutable events must remain traceable from initial request through reporting and close.

## Evidence and authority labels

Every roadmap requirement and later implementation issue must use one of these labels:

- **Observed in eGAPS** — visible in the authorized read-only inspection of the installed client, navigation, configuration, or outputs; this does not prove the hidden business rule or exact operator sequence.
- **Official reference** — supported by applicable law, DBM/COA guidance, prescribed forms, or another authoritative issuance; applicability and current version still require local confirmation.
- **LGU-confirmed** — demonstrated with a redacted actual packet, approved local form, written procedure, or named-office sign-off.
- **GRAND-implemented** — present in code and covered by tests; this does not imply LGU acceptance or official use.
- **Unresolved** — evidence is missing, participants disagree, or a local policy decision remains open.

GRAND must never claim an eGAPS-equivalent or official-use workflow based only on matching menu names.

## Reference baseline

The national reference baseline currently includes the [DBM Budget Operations Manual for LGUs, 2023 Edition](https://www.dbm.gov.ph/wp-content/uploads/Issuances/2023/Local-Budget-Circular/Budget%20Operations%20Manual%20for%20LGUs%2C%202023%20Edition.pdf), the [DBM eBudget for LGUs user manual](https://www.dbm.gov.ph/wp-content/uploads/LGRCB/eBudget-for-LGUs/DBM_E-BUDGET-for-LGUs_USERS-MANUAL_v2_20211123-%281%29.pdf), and the applicable [DBM LGU budget-review service requirements](https://www.dbm.gov.ph/index.php/regional-offices/services-for-client-agencies/1652-review-of-lgu-budget). Before implementation, process owners must confirm the current issuances, COA rules/forms, appropriation ordinances, local procedures, bank requirements, and transaction-specific authorities that apply to the enabled LGU scope.

The eGAPS baseline is limited to the authorized read-only inspection recorded in [the modernization plan](EGAPS_GRAND_PLAN.md). Hidden validation, database behavior, operator steps, and local workarounds remain Unresolved until the [discovery protocol](FINANCE_PROCESS_DISCOVERY.md) supplies evidence.

## Non-negotiable design principles

- GRAND operates without an eGAPS installation, license, session, or database connection.
- Annual budget authority, allotment authority, obligation, accounting recognition, and cash payment remain separate concepts and balances.
- One finance case carries the full lineage; departments receive task-specific views rather than copied records.
- Maker-checker separation, least privilege, department scope, period locks, idempotency, and immutable audit events apply to every consequential action.
- Submitted, numbered, approved, printed, posted, advised, and released artifacts are corrected through return, supersession, adjustment, reversal, cancellation, or replacement—not silent editing or deletion.
- Before a DV/check issuance boundary, governed modification allowances may provide reason-required guided edits with before/after evidence, impact review, and reapproval; after issuance, the workflow must switch to the applicable successor, return, supersession, reversal, cancellation, or replacement path.
- Wet signatures remain first-class. A clerk recording a signed paper is not represented as a digital signature.
- TracePoint records physical custody; Records governs retained authoritative files; neither substitutes for a financial approval.
- Official reports and forms use approved, versioned templates and retain input, mapping, configuration, generator, and output checksums.
- Operational registers, reports, and transaction sets provide permission- and department-scoped exports where a defined business use requires them; every export carries its filters/as-of context and stable lineage, is atomically retained with a checksum manifest in the single TraceSync-ready export root, and is never mislabeled as an approved official form.
- Accessibility, responsive layouts, keyboard operation, plain language, explainable errors, saved work views, and visible next actions are release criteria, not polish deferred until the end.
- Contextual Internal How-Tos follow the employee's current department, permission, and page without being assigned to a named incumbent; private progress never transfers to a successor, and published instructions are versioned with the workflow they explain.
- Production cutover requires evidence-backed reconciliation and explicit approval. Completing a software workflow is not implicit authority to replace eGAPS.

## Complete-cycle domain model

```text
Plans, AIP, PPAs and revenue estimates
  -> proposed executive budget
  -> appropriation ordinance and review
  -> approved appropriations and opening balances
  -> allotment release orders
  -> ALOBS / ORS / OBR and obligation registry
  -> procurement, delivery, service or other valid claim
  -> accounting validation and payable recognition
  -> disbursement voucher
  -> controlled print, wet signatures and physical custody
  -> JEV review and posting
  -> cash availability and payment instrument
  -> accountant/bank advice where applicable
  -> release and acknowledgement
  -> registries, ledgers, reconciliation, reports and period/year close
```

The exact placement of obligation, payable recognition, JEVs, advice, and individual signatures varies by transaction type and local procedure. The workflow engine must support governed variants rather than hard-code one supplier-payment route for every case.

## Workstreams

The phases below are sequential acceptance gates, but implementation may advance supporting work in parallel when it does not bypass an earlier authority decision.

### F0 — Governance, evidence, and finance design authority

Deliver:

- named product owner and process owners for Budget, Accounting, Treasury, requesting offices, IT, management, and audit coordination;
- read-only eGAPS discovery authorization and prohibited-data rules;
- evidence register covering official issuances, approved local procedures, blank/redacted forms, and completed sample packets;
- terminology/data dictionary for appropriation, allotment, obligation, ALOBS/ORS/OBR, payable, DV, JEV, advice, payment, release, and close;
- transaction-type catalog and local responsibility/signature matrix;
- documented correction, cancellation, reprinting, reversal, replacement, emergency, and downtime procedures;
- security classification, retention, backup, recovery, continuity, and incident procedures.

Exit gate: each required step, field, balance, certification, signature, number, output, and exception has an owner, authority/evidence label, and acceptance example. Unresolved items are visible and block only the affected scope.

### F1 — Platform architecture, identity, roles, and audit foundation

Deliver:

- separate `grand_finance` store and service boundary with no eGAPS runtime dependency;
- stable cross-domain IDs and display snapshots without cross-database foreign keys;
- department-aware finance landing page, My Work queue, full-cycle search, notifications, and case timeline;
- curated roles for requesting offices, Budget, Accounting maker/reviewer/poster, Treasury maker/releaser, setup manager/approver, auditor/UAT viewer, and governed exemptions;
- append-only finance event model, state versions, row locking, idempotency receipts, and outbox/inbox recovery;
- finance calendar, fiscal years, accounting periods, business dates, close/reopen authority, and controlled numbering service;
- operational health, backup/restore rehearsal, and audit-log review tools.

Exit gate: synthetic users can access only their role-shaped queues; every consequential test action is permission-checked, concurrency-safe, recoverable, and attributable.

Implementation position: native MySQL logical backup creation now produces one verified, atomically published, checksum-manifested recovery set for both the default and Finance stores, with guarded retention, a separately retainable manifest hash, strict read-only copied-set verification, and an operator restore runbook. A non-root Python 3.11/Gunicorn container, WhiteNoise static delivery, two-store environment contract, stdout logging, minimal health probe, and non-secret configuration/live production preflight provide the deployable runtime foundation. The preflight checks explicit security and decision-reference settings, distinct MySQL identities, both live stores and migration plans, native clients, collected assets, and atomic media/export/backup storage without claiming restore or cutover acceptance. Actual Render topology, persistent/shared storage, backup publication schedule, off-host copying, encryption/retention decisions, monitoring, and a witnessed two-store restore rehearsal with reconciled control totals remain F1/cutover acceptance gates; a built image, preflight/integrity receipt, or created artifact is not represented as production- or restore-tested.

### F2 — Governed master data and opening readiness

Deliver:

- effective-dated funds, special accounts, offices/responsibility centers, PPAs/MFOs, projects, funding sources, chart/account mappings, subsidiary references, banks, payment methods, transaction/JEV types, payees, deductions, document rules, signatories, routes, and thresholds;
- draft, review, approve, schedule, activate, supersede, and retire lifecycles with import staging and duplicate review;
- fiscal-year readiness checklist separating technical setup, Budget approval, Accounting approval, Treasury readiness, and form readiness;
- opening-balance intake, validation, control totals, approval, posting, and reconciliation evidence;
- guided setup instead of routine Django Admin model editing.

Exit gate: an approved synthetic fiscal year can open with reconciled configuration and balances; no transaction screen requires free-text recreation of governed codes.

### F3 — Annual budget preparation, authorization, and review

Deliver:

- budget call, department ceilings, proposals, PPA targets, revenue/resource estimates, and consolidation;
- versioned department proposal, executive proposal, Sanggunian changes, and final approved budget;
- appropriation ordinance, supplemental/reenacted budget, review result, conditions, and effectivity records;
- classification by fiscal year, fund, office/responsibility center, PPA/project/activity, expense class/object/account, funding source, and appropriation type;
- approval snapshots, comparison views, change explanations, controlled import/export, and appropriation schedules;
- dashboards for proposed versus approved amounts and readiness to execute.

Exit gate: every approved appropriation traces to an authorized budget version and review status; proposals are never mistaken for spendable authority.

### F4 — Allotment release and obligation control

Deliver:

- Allotment Release Orders for locally applicable expense classes, reserves, releases, deferrals, and approved adjustments;
- authorized appropriation, prior release, current release, later release, and unreleased appropriation balances;
- requesting-office ALOBS/ORS/OBR initiation with Budget classification and certification;
- immutable Registry of Appropriations, Allotments and Obligations or locally approved equivalent;
- unobligated-allotment validation, concurrent balance protection, returns, releases, adjustments, cancellations, and period control;
- PPA/account drilldowns, utilization views, alerts, and budget accountability reports;
- authoritative linkage from every obligation to the approved appropriation and allotment movements that support it.

Exit gate: GRAND prevents duplicate or excess obligations under concurrent use and reproduces signed synthetic appropriation/allotment/obligation control totals with zero unexplained difference.

Implementation position: F4.1–F4.2 synthetic controls are implemented, including immutable allotment and obligation movements, requesting-office submission, Budget certification, concurrency protection, linked corrections, RAAO-equivalent balances, and portable exports. Exact locally accepted ARO/ALOBS/ORS/OBR/RAAO forms, numbering, signatures, and signed schedule reconciliation remain acceptance gates; see [Finance allotment control](FINANCE_ALLOTMENT_CONTROL.md) and [Finance obligation control](FINANCE_OBLIGATION_CONTROL.md).

### F5 — Request, procurement, delivery, payable, and voucher intake

Deliver:

- governed transaction variants for ordinary supplier, payroll, reimbursement, utility, financial assistance, cash advance/liquidation, infrastructure/progress billing, and other locally approved cases;
- references to requesting-office documents, procurement/contract milestones, inspection/acceptance, invoice/billing, payroll, travel, and claim evidence without duplicating authoritative modules;
- document completeness rules by transaction type, conditional requirements, waivers/exceptions, and return routes;
- payable recognition decision and obligation-to-final-claim adjustment;
- one case supporting valid one-to-one, one-to-many, many-to-one, partial, progress, and final-payment relationships where locally required;
- duplicate-payee/invoice/claim warnings with human review rather than automatic accusation.

Exit gate: the ordinary-supplier flow and each enabled variant reproduce a redacted completed case from request through a payment-ready, budget-supported payable.

### F6 — Disbursement Voucher and controlled paper workflow

Deliver:

- DV preparation with pinned setup, obligation links, gross/deductions/net reconciliation, supporting-document checklist, and maker-checker review;
- controlled DV numbering and exact locally approved forms;
- explicit `Ready to print -> Printed -> Awaiting wet signatures -> Signed packet returned` states;
- immutable print job/version, copy count, printer/form metadata where required, checksum, reprint/supersession reason, and invalidation of obsolete signing copies;
- transaction-specific signature routes, acting authority, refusal/return, absence, and replacement rounds;
- mandatory TracePoint packet/item creation or verified linkage at the locally approved custody point;
- finance gates that require the correct custody/signature evidence while preserving human confirmation of the financial decision.

Exit gate: a printed redacted DV packet, wet-signature route, returned packet, corrections, and reprint behavior match the approved local procedure and cannot drift from the stored version.

### F7 — Accounting recognition, JEVs, ledgers, and period control

Deliver:

- transaction-specific posting rules distinguishing recognition, adjustment, liquidation, payment, remittance, cancellation, and reversal entries;
- balanced JEV preparation, independent review/posting, source checksum, immutable lines, return, reversal, and replacement;
- cash receipts, check disbursement, general, and other locally required journal routes and posting batches;
- general and subsidiary ledgers, payable and withholding schedules, control-account reconciliation, and trial balance;
- period close checklist, adjusting/closing entries, governed reopen, and subsequent-period handling;
- correction orchestration across obligation, voucher, JEV, and later payment states.

Exit gate: every posted synthetic case balances, traces to its authority and source documents, updates the correct ledgers/schedules, and reverses without rewriting posted history.

Implementation position: F7.1–F7.4 synthetic controls are implemented. F7.1 supplies locally reviewable posting rules and governed JEV handoffs; F7.2 supplies payable/withholding subsidiary detail and control reconciliation; F7.3 carries payment events into Accounting; and F7.4 replaces direct close with human-modifiable Observe/Enforce policies, checksummed close evidence, independent approval, and ordered reason/authority-backed reopen. See [Finance transaction posting rules](FINANCE_TRANSACTION_POSTING_RULES.md), [Finance subsidiary controls](FINANCE_SUBSIDIARY_CONTROLS.md), [Finance payment-event posting](FINANCE_PAYMENT_EVENT_POSTING.md), and [Finance period close](FINANCE_PERIOD_CLOSE.md). Exact local close calendars, accepted adjustment/closing-entry procedures, broader required subsidiary ledgers, signed schedules/statements, redacted replay, and named-office acceptance remain parent-F7 gates.

### F8 — Treasury, advice, release, and bank reconciliation

Deliver:

- cash availability/cash-program checks distinct from budget availability;
- controlled check/ADA/payment-instrument issuance, printing where approved, custody, wet signatures, spoiled/cancelled number retention, and replacement lineage;
- advice batching, reconciliation, finalization, supersession, submission/acknowledgement evidence, and returned advice handling;
- authorized claimant and release controls, acknowledgement/receipt, unclaimed/stale/returned instruments, and terminal TracePoint evidence;
- payment-side JEV integration, check and disbursement registers, tax/deduction remittance linkage, bank statement import, and bank reconciliation;
- Treasury dashboards for cash position, instruments awaiting action, unreleased items, exceptions, and reconciliation age.

Exit gate: issued, signed, advised, released, cancelled, replaced, remitted, and reconciled instruments agree exactly with vouchers, JEVs, registers, and bank evidence.

Implementation position: F8.1–F8.5 synthetic controls are implemented. F8.1 covers cross-voucher withholding remittance through posted liability reduction. F8.2 covers checksummed monthly bank-statement versions, exact/guided posted-GL matching, adjusted-balance timing items, independent zero-difference reconciliation, Internal How-Tos, and portable evidence. F8.3 adds locally versioned Observe/Enforce cash policies, independently approved reconciliation-backed positions, issue reservations, configurable unclaimed/stale/returned classification, department guidance, and portable evidence. F8.4 adds retained multi-case advice versions, independent review, actual bank submission and acknowledgement/return evidence, acknowledgement-gated release, reasoned successors, and returned-payment reversal/reissue orchestration. F8.5 adds prior-reconciled timing-item carry-forward, age/overdue visibility, later-bank clearance across retained lineage, and reason-required reopening; see [Finance remittance execution](FINANCE_REMITTANCE_EXECUTION.md), [Finance bank reconciliation](FINANCE_BANK_RECONCILIATION.md), [Finance cash position and instrument ageing](FINANCE_CASH_POSITION.md), and [Finance bank advice and returned instruments](FINANCE_BANK_ADVICE.md). Exact official forms/rules, local ageing/escalation acceptance, and full consecutive-month redacted instrument-to-bank replay remain acceptance/delivery gates.

### F9 — Statutory outputs, management reporting, and accountability

Deliver:

- approved RAAO/budget accountability reports, budget-versus-actual, check/disbursement reports, journals, ledgers, trial balance, payable/tax schedules, BIR outputs, and locally required registers;
- financial statements and notes/schedules required for the approved scope;
- controlled report parameters, preparation, review, approval, archive, supersession, and reproduction receipts;
- drill-through from report totals to posted entries and source cases, subject to permissions;
- dashboard measures with definitions, freshness, period, and reconciliation status—never unexplained decorative totals;
- export/print accessibility and exact template regression coverage.

Exit gate: approved opening balances plus pilot transactions reproduce signed reference schedules/statements and every reported control total is explainable.

Implementation position: F9.1 supplies the immutable evidence and reproducibility foundation, while F9.2 adds the Budget/Accounting/Treasury operational catalog. F9.3 adds governed financial-position/performance composition, exact account coverage, visible ledger equations, source drill-through, and explained measures. F9.4 adds editable note packages pinned to exact statement runs, candidate-versus-locally-confirmed review, and independent zero-difference comparison against checksummed signed/redacted reference copies. F9.5 adds plain-language locally governed tax rules, multi-line DV tax evidence, rule/formula/ledger reconciliation, and detail/return-summary source schedules. F9.6 connects that governed scope to remittance allocations and independently reviewed external filing/payment references with amendment lineage. F9.7 adds locally editable and independently approved accountability-package recipes, cross-office exact-period evidence selection, immutable checksums, correction successors, and portable manifests. One automated [cross-cycle synthetic replay](FINANCE_CROSS_CYCLE_REPLAY.md) now proves that maker–checker fiscal readiness, reconciled opening balances, and the same authoritative appropriation/allotment/obligation can cross payable intake, DV, recognition and payment JEVs, acknowledged release, zero-difference bank reconciliation, and the controlled Treasury register; see [Finance accountability reporting](FINANCE_ACCOUNTABILITY_REPORTING.md), [Finance operational report catalog](FINANCE_OPERATIONAL_REPORT_CATALOG.md), [Finance statement controls](FINANCE_STATEMENT_CONTROLS.md), [Finance statement notes and signed-reference comparison](FINANCE_STATEMENT_NOTES.md), [Finance governed tax reporting](FINANCE_TAX_REPORTING.md), [Finance governed tax remittance and filing evidence](FINANCE_TAX_REMITTANCE_EVIDENCE.md), [Finance accountability-package profiles and assembly](FINANCE_ACCOUNTABILITY_PACKAGES.md), and the [F9 comprehensive review and handoff](FINANCE_F9_REVIEW_AND_HANDOFF.md). Current locally accepted forms/package contents, actual filing adapters/deadlines, exact layouts, complete signed/acknowledged package reproduction, named-office acceptance, and the parent F9 exit gate remain open.

### F10 — Templates and low-code form administration

Deliver:

- visual XLSX/PDF mapping for single values, repeating rows, totals, optional blocks, logos, and signatories;
- safe preflight, synthetic preview, workbook/mapping diff, impact review, approval, activation, rollback, and golden-output tests;
- form catalog covering budget, allotment, obligation, DV, JEV, advice, registers, receipts, ledgers, and statements;
- page geometry, print area, pagination, overflow, form stock, and printer-alignment validation;
- controlled template promotion independent of software deployment.

Exit gate: an authorized non-developer can update an approved blank form without code, and the system proves which version produced every output.

Implementation position: F10.1 adds inactive human-editable versions, safe preview generation, automatic same-period golden data/control comparison, plain-language form/print checks, template diffs, schedule-impact review, independent approval, deployment-free activation, reasoned rollback, append-only events, department roles, inline guidance, and TraceSync-ready receipts. F10.2 adds a department-bounded plain-language form register, an in-app catalog for all 31 source-anchored DBM LBP/LBA/LBR/LBE/LBAc candidates, 77 editable field/source/control/owner/print section groups with explicit local-resolution evidence, dynamic required/optional/conditional/repeating behavior, exact promoted-report or active-preflighted-workbook source locks, seven independently witnessed practical tests, maker–checker local acceptance, reasoned fully retested successors, schema-compatible historical reproducibility, guidance, and TraceSync-ready evidence; see [Finance visual template promotion and rollback](FINANCE_TEMPLATE_PROMOTION.md) and [Finance local-form inventory and acceptance](FINANCE_LOCAL_FORM_ACCEPTANCE.md). Starters remain unmapped, delivery-unconfirmed drafts with no reference, tests, or acceptance. Actual LGU forms, accepted authorities/decisions, golden outputs, devices, physical printer/form-stock trials, retained samples, and named-office sign-off remain open, so the parent F10 exit gate is not yet claimed.

### F11 — Reconciliation, shadow operation, training, and cutover

Deliver:

- role-based training curriculum, synthetic exercises, quick guides, supervisor runbooks, and support/escalation procedures;
- optional read-only eGAPS/redacted-export staging with source checksums and schema-drift detection;
- case, batch, period, register, ledger, and report comparison dashboards;
- limited shadow pilot, controlled parallel run, daily reconciliation, defect triage, and formal sign-off by enabled transaction type;
- security, privacy, accessibility, performance, printing, backup/recovery, business-continuity, and incident exercises;
- explicit authority matrix, cutover scope/date, opening reconciliation, rollback criteria, and eGAPS read-only retention plan.

Exit gate: Budget, Accounting, Treasury, requesting offices, IT, management, and audit stakeholders approve the enabled scope. GRAND becomes authoritative only through the recorded cutover decision.

Implementation position: F11.1 adds limited shadow/parallel cycles, exact comparisons, independent reconciliation, seven-party acceptance, exact-scope authority, rollback, guidance, and portable evidence. F11.2 adds versioned redacted CSV staging, automatic file/layout locks, safe inspection, predecessor/prior-version drift detection, independent drift acceptance, and retained replacements. F11.3 adds maker–checker local cadence/severity/escalation plans, scheduled checksummed run snapshots, reviewed-exception visibility, due/overdue defect triage, attributable escalation, independent correction acceptance, and minimum-run/final-resolution gates. F11.4 adds a maker–checker curriculum/quick-guide/supervisor/support plan, one independently witnessed role exercise per stakeholder, eight named nonfunctional exercise categories, reasoned reruns, private tutorial-progress separation, and stricter cutover readiness gates. F11.5 adds a locally editable maker–checker field-qualification plan, independently accepted consecutive-cycle evidence, explicit predecessor/parallel-run gates, and retained stakeholder/cutover signed-record references and checksums. F11.6 binds that plan and every field-cycle submission to exact current F10.2 accepted-form snapshots and checksums, with supersession/drift blocking readiness. F11.7 requires the backup/restore exercise to bind an exact off-host two-store set, approved/actual RPO/RTO, both restored stores and migrations, reconciled controls, a cross-store case, runtime-file/disposal evidence, resolved exceptions, independent witness passage, and the same immutable evidence in the cutover decision; see [Finance shadow operation, UAT acceptance, and controlled cutover](FINANCE_SHADOW_CUTOVER.md). A production/eGAPS adapter and the actual locally accepted content, field execution, forms, recovery results, pass conditions, and signatures remain open, so the parent F11 exit gate is not claimed.

## Current implementation position

| Capability | Current position | Roadmap consequence |
|---|---|---|
| Finance Setup Center | Foundation implemented | Extend through F2; existing activation does not open an authoritative fiscal year. |
| Standalone Accounting | Fiscal/fund/account setup, controlled opening intake/posting/reconciliation/export, F7.1 rule-backed JEVs, F7.2 subsidiary controls, F7.3 payment-event JEVs, F7.4 governed close/reopen, F8.1 remittance JEV orchestration, and F9.5 governed tax evidence/reporting implemented | Continue under F7–F9; validate the local close/tax policies, broaden required subsidiary ledgers, and complete accepted statements and official tax forms/filing evidence. |
| Voucher Workbench | Synthetic vertical slice through release plus F5.1–F5.3 payable controls and F6.1 controlled print/custody implemented | Complete accepted per-variant replay, exceptions, local form comparison, and paper-route acceptance without restoring a second budget balance. |
| Wet-signature handling | Print-versioned current rounds, reasoned reprints, and returned-packet gates implemented | Reconcile refusal/absence/replacement behavior and redacted paper circulation against the approved local procedure. |
| TracePoint | F6.1 creates/links a Finance packet item and configured signatory-office checkpoints without copying monetary fields | Validate the locally approved custody point/route; extend payment-side custody under F8. |
| Treasury | Check registration, cancellation/replacement, F7.3 payment posting, F8.1 remittance, F8.2/F8.5 bank reconciliation and timing-item lineage, F8.3 cash position/reservation/ageing, and F8.4 advice acknowledgement plus returned-payment orchestration implemented | Validate official advice/cash/check/BRS forms, entries, channels, ageing/escalation rules, thresholds, and named-office consecutive-month replay in F8. |
| Reporting/templates | Governed reporting, macro-free workbook preflight, F9.1 evidence/reproduction controls, the F9.2 operational catalog, F9.3 governed statement composition/explained measures, F9.4 note/reference controls, F9.5–F9.6 governed tax schedules/filing evidence, F9.7 accountability-package assembly, F10.1 template promotion/rollback, and F10.2 local-form acceptance with 31 in-app DBM candidate starters exist | Compare applicable starters with current local forms, populate actual references and accepted package profiles, resolve every candidate section, perform witnessed golden/output/accessibility/printer/recovery trials, confirm filing/remittance evidence and TIN custody, reproduce a complete signed/acknowledged package, and obtain named-office acceptance through F10–F11. |
| Shadow operation and cutover | F11.1 governed cycles/cutover, F11.2 source staging/drift controls, F11.3 approved cadence/run/defect gates, F11.4 curriculum/support plus witnessed readiness exercises, F11.5 consecutive-cycle/signed-reference gates, F11.6 exact accepted-form lineage, and F11.7 structured two-store recovery/cutover binding implemented | Populate and accept actual F10.2 forms, select every applicable form in the qualification plan, confirm local plan/content/pass-condition/RPO/RTO values and any production adapter, complete the actual isolated two-store restore and field exercises/cycles, and obtain actual seven-party/cutover records before claiming authority. |
| Annual budget, appropriation, allotment, and obligation registry | F3.1–F4.2 implemented; F5.1–F5.3 consume, allocate, version, and recheck authoritative obligation UUID/checksum lineages | Reconcile accepted schedules/forms and complete per-variant replay before official use. |

The [Finance field-acceptance starter pack](finance-field-acceptance/README.md) now translates the immediate field-evidence queue into one editable, non-technical workbook. It inventories the 2023 DBM LGU budget-form families with verified printed-manual/PDF page anchors, supplies 70 official-source candidate field/control mappings across every listed form, leaves transaction-specific COA documentary rules explicitly unconfirmed, and prepares the seven practical tests, role exercises, consecutive-cycle comparisons, local decisions, exact-form lineage, and structured recovery inputs required by the implemented F10/F11 workflows. It does not change the open acceptance position in this table.

The earlier statement that printing was the first confirmed voucher mismatch remains true only inside the implemented voucher subcycle. From a complete-cycle perspective, F5.1 covers the original obligation handoff, F5.2 supplies governed variant/checklist infrastructure plus independent readiness review, and F5.3 supplies versioned payable relationships, recognition/adjustment routing decisions, zero-difference controls, and transaction exports. GRAND still diverges inside F5 at locally accepted per-variant rules, exceptions, forms, and redacted replay.

## Immediate next delivery train

Unless field evidence changes the dependency order, begin with these reviewable slices. Each receives its own `codex/` branch and must satisfy the relevant parent-phase gate.

1. **F0.1 — Finance evidence register and interview kit**: repository-safe evidence/decision templates, authority labels, transaction catalog, role/signature matrix, actual-step worksheet, unresolved-decision log, and redacted replay checklist.
2. **F1.1 — Complete-cycle information architecture**: role and permission matrix, one finance landing page/My Work design, cross-cycle case/timeline/search contract, status vocabulary, and clickable synthetic UX prototype before adding dense models.
3. **F2.1 — Fiscal-year and classification foundation — implemented synthetic control**: typed fiscal year, finance calendar, PPAs/MFOs, projects/activities, funding sources, expanded account/office dimensions, readiness layers, setup migration path, and a shared office/fiscal-year transaction-store lock that serializes cross-store setup amendments with controlled voucher/check number issuance; see [Finance fiscal-year and classification foundation](FINANCE_FISCAL_FOUNDATION.md). Actual classifications, authority, readiness evidence, calendars, and named-owner acceptance remain parent-F2 gates.
4. **F2.2 — Opening balances and control totals — implemented synthetic control**: checksum-backed CSV staging, governed-code validation, reasoned pre-posting correction, maker–checker approval, per-fund opening JEVs, zero-difference reconciliation, immutable evidence, and scoped export; see [Finance opening balances and control-total intake](FINANCE_OPENING_BALANCES.md). Actual accepted opening schedules, balances, authority, and named-office reconciliation remain parent-F2 gates.
5. **F3.1 — Budget preparation workspace**: budget call, ceilings, department proposals, targets, revenue/resource estimates, consolidation, review comments, and version comparison.
6. **F3.2 — Authorization and operational appropriations**: executive/Sanggunian/final versions, ordinance and review evidence, effective appropriations, supplemental/reenacted handling, and signed control totals.
7. **F4.1 — Allotment Release Orders**: release/reserve/deferral/adjustment movements, approval, numbering, exact forms, balances, concurrency protection, and reports.
8. **F4.2 — ALOBS/ORS/OBR and RAAO**: requesting-office initiation, Budget certification, authoritative obligation registry, returns/adjustments/cancellations, remaining-balance drilldown, and controlled forms.
9. **F5.1 — Voucher budget-lineage integration — implemented synthetic control**: the current case entry consumes the requesting office's certified obligation UUID/checksum and payable evidence, preserves legacy audit/numbers, and uses a recoverable cross-database handoff. Parent F5 acceptance and variants remain open; see [Finance payable intake](FINANCE_PAYABLE_INTAKE.md).
10. **F5.2 — Transaction variants and documentary readiness — implemented synthetic control**: Finance Setup governs typed variants and conditional/waiver rules; the requesting office resolves pinned evidence and a separate Accounting reviewer accepts or returns the same case. Parent F5 local acceptance and replay remain open; see [Finance transaction variants and payable readiness](FINANCE_PAYABLE_VARIANTS.md).
11. **F5.3 — Payable relationships, recognition, reconciliation, and exports — implemented synthetic control**: versioned one-to-many/many-to-one/partial/progress/final/full allocations, recognition/adjustment decisions, exact control-total reconciliation, guided pre-DV corrections, and TraceSync-ready transaction exports; see [Finance payable relationships, recognition decisions, and transaction exports](FINANCE_PAYABLE_RELATIONSHIPS.md).
12. **F6.1 — Controlled print and finance custody — implemented synthetic control**: editable plain-language starter templates, print/version/reprint states, TraceSync-ready output manifests, TracePoint creation/linkage, configured wet-signature checkpoints, and returned-packet/accounting gates; see [Finance controlled DV printing and custody](FINANCE_CONTROLLED_PRINT_CUSTODY.md). Redacted output, printer/form-stock, and named-office procedure comparison remain parent-F6 acceptance inputs.
13. **F7.1 — Transaction posting rules and governed JEV handoff — implemented synthetic control**: plain-language event/recognition-point rules, editable starters with unresolved-authority submission blocks, checksum-pinned voucher and rule evidence, balanced snapshot-driven JEV materialization, earlier-accrual/existing-payable duplicate-recognition blocks, and TraceSync-ready ledger/trial-balance exports; see [Finance transaction posting rules and governed JEV handoff](FINANCE_TRANSACTION_POSTING_RULES.md). Payment/remittance/cancellation orchestration, broader subsidiary ledgers, period close, and locally accepted output comparison remain parent-F7 work.
14. **F7.2 — Payable and withholding subsidiary controls — implemented synthetic control**: immutable claimant/payee and deduction movements attached to governed JEV lines, exact reversal lineage, mapped GL-to-subsidiary comparison, checksum-backed reconciliation runs, role guidance, and TraceSync-ready schedules/evidence; see [Finance payable and withholding subsidiary controls](FINANCE_SUBSIDIARY_CONTROLS.md). Payment/remittance/cancellation orchestration, broader subsidiary ledgers, period close, accepted local schedules, and named-office replay remain parent-F7 work.
15. **F7.3 — Payment-event posting and portable register — implemented synthetic control**: payment-release payable-to-bank JEVs, explicit cancellation/replacement no-entry decisions, exact Treasury-stage resume, controlled discarded-draft successors, complete-event setup gates/starters, role guidance, and TraceSync-ready case payment registers; see [Finance payment-event posting and portable register](FINANCE_PAYMENT_EVENT_POSTING.md). Remittance execution, bank reconciliation, accepted local rules/registers, and named-office replay remain F8 and parent-acceptance work.
16. **F7.4 — Governed period close and controlled reopen — implemented synthetic control**: human-modifiable Observe/Enforce policies, ordered-period and ledger gates, pinned subsidiary/bank/statement/handoff/year-end evidence, checksum drift protection, independent close, immutable history, reason/authority-backed ordered reopen, floating guidance, and TraceSync-ready evidence; see [Finance period close and controlled reopen](FINANCE_PERIOD_CLOSE.md). Exact local calendars, accepted closing-entry procedures, signed outputs, consecutive redacted replay, and named-office acceptance remain parent-F7 work.
17. **F8.1 — Deduction and withholding remittance execution — implemented synthetic control**: cross-voucher selection of positive posted withholding balances, concurrent reservation, one-fund agency batches, retained pre-release allocation revisions/removals, independent Accounting review, actual-release evidence, controlled JEV recovery, liability-reducing subsidiary posting, department guides, and TraceSync-ready versioned registers; see [Finance deduction and withholding remittance execution](FINANCE_REMITTANCE_EXECUTION.md). Accepted local forms/rules, cash-position control, bank statement reconciliation, exceptions, and named-office replay remain parent-F8 work.
18. **F8.2 — Bank-statement intake and reconciliation — implemented synthetic control**: checksummed monthly source versions, posted-GL matching, adjusted-balance timing items, zero-difference independent review, starter CSV, department guides, and TraceSync-ready evidence; see [Finance bank-statement intake and reconciliation](FINANCE_BANK_RECONCILIATION.md). Exact official BRS acceptance and named-office replay remain parent-F8 work; F8.5 supplies carry-forward and later-clearance lineage.
19. **F8.3 — Cash position, issue reservation, and instrument ageing — implemented synthetic control**: locally reviewable Observe/Enforce policies, reconciliation-backed position snapshots, independent approval, issue-time reservations, configurable unclaimed/stale/returned exceptions, reasoned successor corrections, floating department guidance, planning starter, and TraceSync-ready evidence; see [Finance cash position and instrument ageing](FINANCE_CASH_POSITION.md). F8.4 now supplies advice acknowledgement and returned-item Accounting orchestration; official cash/check forms, exact thresholds, and named-office replay remain parent-F8 work.
20. **F8.4 — Bank advice acknowledgement and returned instruments — implemented synthetic control**: retained checksum-backed multi-case advice versions, independent Accounting review, actual Treasury bank submission, bank acknowledgement/return, acknowledgement-gated release, reasoned correction successors, governed returned-payment reversal/no-entry and reissue decisions, editable starter, floating guidance, and TraceSync-ready evidence; see [Finance bank advice and returned instruments](FINANCE_BANK_ADVICE.md). Exact official forms/channels/entries and named-office replay remain parent-F8 work.
21. **F8.5 — Prior-item carry-forward and later clearance — implemented synthetic control**: one-action carry of the latest unresolved item from a prior independently reconciled month, original evidence/checksum lineage, age/overdue visibility, later-bank clearance across the lineage, reasoned correction/reopening, role guidance, and TraceSync-ready evidence; see [Finance bank-statement intake and reconciliation](FINANCE_BANK_RECONCILIATION.md). Local ageing/escalation treatment, exact official BRS acceptance, and consecutive-month named-office replay remain parent-F8 gates.
22. **F9.1 — Finance accountability reporting and reproducibility — implemented synthetic control**: cumulative Budget accountability and posted-trial-balance starters, candidate/locally-confirmed applicability controls, immutable data/control/source snapshots, control-gated review, drill-through, deterministic reproduction receipts, role guidance, and TraceSync-ready evidence; see [Finance accountability reporting](FINANCE_ACCOUNTABILITY_REPORTING.md). The full report catalog, accepted official forms, signed-reference reproduction, statements/notes, and parent-F9 exit gate remain open.
23. **F9.2 — Finance operational report catalog — implemented synthetic control**: exact-key Budget-versus-posted-actual mapping, a line-level posted general ledger, GL-reconciled payable and withholding schedules, a Treasury instrument/disbursement register, incomplete-source exception handling, candidate starters, successor department guides, and the F9.1 evidence/export controls; see [Finance operational report catalog](FINANCE_OPERATIONAL_REPORT_CATALOG.md). Accepted tax outputs, statements/notes, dashboards, signed-reference reproduction, exact forms, and parent-F9 exit gate remain open.
24. **F9.3 — Governed statement composition and explained measures — implemented synthetic control**: versioned maker–checker account mappings, broad controlled starters, management financial position/performance datasets, exact non-zero account coverage, the visible unclosed-result equation, retained JEV drill-through, mapping snapshots, explained dashboard measures, floating help, and successor Accounting guidance; see [Finance statement controls](FINANCE_STATEMENT_CONTROLS.md). F9.4 supplies note and reference-comparison controls; accepted tax outputs, exact official forms/layouts, named-office acceptance, and the parent-F9 exit gate remain open.
25. **F9.4 — Statement notes and signed-reference comparison — implemented synthetic control**: editable candidate disclosure topics, exact-period statement pairing, pinned run/mapping/checksum evidence, independent working-versus-official note decisions, safe signed/redacted reference intake, exact control-total differences, file and comparison checksums, drift gates, role guidance, and TraceSync-ready evidence; see [Finance statement notes and signed-reference comparison](FINANCE_STATEMENT_NOTES.md). Current accepted tax/BIR outputs, exact official layouts, complete signed-package replay, named-office acceptance, and the parent-F9 exit gate remain open.
26. **F9.5 — Governed tax withholding capture and reporting — implemented synthetic control**: plain-language candidate/locally-confirmed tax rules, dynamic multi-line DV deductions, base/rate/rounding/TIN gates, immutable rule/payee/form/checksum evidence, Accounting posting and reversal lineage, reconciled tax detail and return/remittance-summary starters, floating guidance, and TraceSync-ready exports; see [Finance governed tax reporting](FINANCE_TAX_REPORTING.md). Actual local applicability, current official forms/ATCs/deadlines, filing/remittance evidence, TIN custody acceptance, exact layouts, named-office replay, and the parent-F9 gate remain open.
27. **F9.6 — Governed tax remittance and filing evidence — implemented synthetic control**: tax-aware remittance allocation/posting lineage, one-form evidence scope, actual external filing/payment references, guided linkage to an exact approved/reconciled GRAND summary with immutable report/template/control snapshots, a reasoned external-schedule SHA-256 fallback, maker-checker verification/return, immutable verified records, amended successors, floating guidance, and TraceSync-ready exports; see [Finance governed tax remittance and filing evidence](FINANCE_TAX_REMITTANCE_EVIDENCE.md). Actual filing, current deadlines/forms/channels, complete signed/acknowledged packets, TIN custody acceptance, named-office replay, and the parent-F9 gate remain open.
28. **F9.7 — Governed Finance accountability-package assembly — implemented synthetic control**: human-editable maker–checker package profiles, required/optional cross-office evidence slots, exact-period approved report/note/reference/tax selection, immutable source/profile/package checksums, reasoned draft replacements, approved profile/package successors, source-reversal boundaries, floating guidance, and TraceSync-ready manifests; see [Finance accountability-package profiles and assembly](FINANCE_ACCOUNTABILITY_PACKAGES.md) and the [F9 comprehensive review and handoff](FINANCE_F9_REVIEW_AND_HANDOFF.md). Actual accepted package recipes, signed/acknowledged source outputs, exact local layouts, complete field replay, and named-office acceptance remain parent-F9 gates.
29. **F10.1 — Governed visual template promotion and rollback — implemented synthetic control**: human-editable inactive templates, safe preview and golden-data/control comparison, readable form/print checks, independent promotion, deployment-free activation, reasoned rollback, guidance, and TraceSync-ready receipts; see [Finance visual template promotion and rollback](FINANCE_TEMPLATE_PROMOTION.md). Exact accepted local forms and physical printer/form-stock trials remain parent-F10 gates.
30. **F10.2 — Governed local-form inventory and acceptance — implemented synthetic control plus editable DBM candidates**: the in-app catalog covers all 31 source-anchored LBP/LBA/LBR/LBE/LBAc entries and creates only department-owned, source-unmapped, delivery-unconfirmed drafts; 77 candidate section groups expose fields, sources, controls, owners, and print behavior for explicit locally referenced match/not-applicable decisions. Dynamic section behavior, exact activated source locks, seven maker–witness practical tests, independent form acceptance, reasoned fully retested successors, schema-compatible immutable history, department guidance, and TraceSync-ready evidence remain enforced; see [Finance local-form inventory and acceptance](FINANCE_LOCAL_FORM_ACCEPTANCE.md). Actual LGU references, authority and acceptance decisions, accepted golden outputs, physical devices/stock, retained field samples, and named-office sign-off remain parent-F10 gates.
31. **F11.1 — Governed shadow operation and controlled cutover — implemented synthetic control**: limited cycles, exact comparisons, owned defects, independent reconciliation, seven named stakeholder categories, exact-scope/date authority, rollback, guidance, and portable evidence; see [Finance shadow operation, UAT acceptance, and controlled cutover](FINANCE_SHADOW_CUTOVER.md). Actual field cycles and signed acceptance remain open.
32. **F11.2 — Versioned redacted source staging and schema-drift review — implemented synthetic control**: guided redacted CSV staging, automatic file/layout locks, retained replacements, predecessor/prior-version drift detection, independent drift decisions, and metadata-only portable evidence; see [Finance shadow operation, UAT acceptance, and controlled cutover](FINANCE_SHADOW_CUTOVER.md). Production adapters, accepted local layouts, cadence, and parent-F11 field evidence remain open.
33. **F11.3 — Scheduled reconciliation and governed defect resolution — implemented synthetic control**: locally editable maker–checker cadence/severity/escalation plans, scheduled checksummed comparison/defect snapshots, independently reconciled or exception-reviewed outcomes, due/overdue triage, attributable escalation, independent correction acceptance, minimum-run gates, floating guidance, and TraceSync evidence; see [Finance shadow operation, UAT acceptance, and controlled cutover](FINANCE_SHADOW_CUTOVER.md). Accepted local values, support ownership, consecutive field execution, and parent-F11 sign-off remain open.
34. **F11.4 — Governed curricula, support, and witnessed readiness exercises — implemented synthetic control**: locally editable maker–checker curriculum/guide/supervisor/support plans, named owners and witnesses, one role exercise per stakeholder, security/privacy/accessibility/performance/printing/recovery/continuity/incident categories, checksum-backed pass/rerun decisions, private tutorial-progress separation, stricter cutover gates, floating guidance, and TraceSync evidence; see [Finance shadow operation, UAT acceptance, and controlled cutover](FINANCE_SHADOW_CUTOVER.md). Accepted local content, actual devices/volumes/forms/timings/pass conditions, complete field execution, consecutive cycles, and parent-F11 sign-off remain open.
35. **F11.5 — Consecutive field-cycle qualification and signed decision references — implemented synthetic control**: editable maker–checker qualification thresholds and parallel-run requirements, exact-scope predecessor chains, independently accepted field-execution/rules/forms references, retained stakeholder and cutover authority record checksums/custody, stricter cutover gates, updated floating guidance, and TraceSync schema-v5 evidence; see [Finance shadow operation, UAT acceptance, and controlled cutover](FINANCE_SHADOW_CUTOVER.md). Actual locally accepted rules/forms, field execution, attributable signatures/decisions, and optional production adapters remain open.
36. **F11.6 — Exact accepted-form lineage in field qualification — implemented synthetic control**: editable selection of current F10.2 accepted form versions, protected acceptance-packet validation, exact form/source/reference/submission checksum pinning in the approved plan and every field-cycle submission, immutable lineage, supersession/drift readiness failure, conservative governed UI guidance, and TraceSync schema-v6 evidence; see [Finance shadow operation, UAT acceptance, and controlled cutover](FINANCE_SHADOW_CUTOVER.md). Actual form inventory/acceptance, complete applicable-form selection, field use, and named-office acceptance remain open.
37. **F11.7 — Structured two-store recovery rehearsal and cutover binding — implemented synthetic control**: exact completed backup-set/hash lineage, verified off-host/preflight references, approved and calculated RPO/RTO, both stores/migrations, reconciled controls, representative cross-store/runtime-file/disposal checks, explicit exceptions, independent pass/rerun control, immutable same-cycle authority binding, guided UI/how-to, and TraceSync schema-v7 evidence; see [database backup and recovery](DATABASE_BACKUP.md) and [Finance shadow operation, UAT acceptance, and controlled cutover](FINANCE_SHADOW_CUTOVER.md). An actual production-compatible backup, isolated restore, locally approved targets/procedure, restricted evidence, and named witness remain open.

Delivery status: the repository-safe templates for **F0.1** are available in the [Finance evidence register and interview kit](finance-discovery/README.md). The **F1.1** design contract and clickable synthetic UX are available in the [complete-cycle Finance information architecture](finance-ia/README.md). The **F2.1** software foundation is documented in [Finance fiscal-year and classification foundation](FINANCE_FISCAL_FOUNDATION.md), the **F2.2** controls in [Finance opening balances and control-total intake](FINANCE_OPENING_BALANCES.md), **F3.1–F3.2** in [Finance annual budget preparation](FINANCE_ANNUAL_BUDGET.md), **F4.1** in [Finance allotment release control](FINANCE_ALLOTMENT_CONTROL.md), **F4.2** in [Finance obligation control](FINANCE_OBLIGATION_CONTROL.md), **F5.1** in [Finance payable intake](FINANCE_PAYABLE_INTAKE.md), **F5.2** in [Finance transaction variants and payable readiness](FINANCE_PAYABLE_VARIANTS.md), **F5.3** in [Finance payable relationships, recognition decisions, and transaction exports](FINANCE_PAYABLE_RELATIONSHIPS.md), **F6.1** in [Finance controlled DV printing and custody](FINANCE_CONTROLLED_PRINT_CUSTODY.md), **F7.1** in [Finance transaction posting rules and governed JEV handoff](FINANCE_TRANSACTION_POSTING_RULES.md), **F7.2** in [Finance payable and withholding subsidiary controls](FINANCE_SUBSIDIARY_CONTROLS.md), **F7.3** in [Finance payment-event posting and portable register](FINANCE_PAYMENT_EVENT_POSTING.md), **F7.4** in [Finance period close and controlled reopen](FINANCE_PERIOD_CLOSE.md), **F8.1** in [Finance deduction and withholding remittance execution](FINANCE_REMITTANCE_EXECUTION.md), **F8.2/F8.5** in [Finance bank-statement intake and reconciliation](FINANCE_BANK_RECONCILIATION.md), **F8.3** in [Finance cash position and instrument ageing](FINANCE_CASH_POSITION.md), **F8.4** in [Finance bank advice and returned instruments](FINANCE_BANK_ADVICE.md), **F9.1** in [Finance accountability reporting](FINANCE_ACCOUNTABILITY_REPORTING.md), **F9.2** in the [Finance operational report catalog](FINANCE_OPERATIONAL_REPORT_CATALOG.md), **F9.3** in [Finance statement controls](FINANCE_STATEMENT_CONTROLS.md), **F9.4** in [Finance statement notes and signed-reference comparison](FINANCE_STATEMENT_NOTES.md), **F9.5** in [Finance governed tax reporting](FINANCE_TAX_REPORTING.md), **F10.1** in [Finance visual template promotion and rollback](FINANCE_TEMPLATE_PROMOTION.md), **F10.2** in [Finance local-form inventory and acceptance](FINANCE_LOCAL_FORM_ACCEPTANCE.md), the editable [Finance field-acceptance starter pack](finance-field-acceptance/README.md), and **F11.1–F11.7** in [Finance shadow operation, UAT acceptance, and controlled cutover](FINANCE_SHADOW_CUTOVER.md). These deliver reviewable instruments and implemented synthetic controls, not the parent phase acceptance gates; actual recovery/field evidence, accepted local schedules/forms/tax rules, printer/paper tests, signed reference-output reproduction, complete consecutive-month instrument-to-bank replay, and named-office acceptance remain required.

F9.3 is documented in [Finance statement controls](FINANCE_STATEMENT_CONTROLS.md), F9.4 in [Finance statement notes and signed-reference comparison](FINANCE_STATEMENT_NOTES.md), F9.5 in [Finance governed tax reporting](FINANCE_TAX_REPORTING.md), F9.6 in [Finance governed tax remittance and filing evidence](FINANCE_TAX_REMITTANCE_EVIDENCE.md), and F9.7 in [Finance accountability-package profiles and assembly](FINANCE_ACCOUNTABILITY_PACKAGES.md). The [F9 comprehensive review and handoff](FINANCE_F9_REVIEW_AND_HANDOFF.md) records the combined software position and next acceptance train. All remain synthetic-control checkpoints within the same acceptance boundary described above.

Do not start historical migration, direct check printing, or official-use switching merely because those tasks are visible in later phases. The immediate train establishes the authority chain on which all of them depend.

## Release and acceptance discipline

Each roadmap slice must include:

- an evidence/decision record and updated process map;
- migrations, permissions, services, UI, help text, audit events, and rollback behavior;
- focused tests plus full-suite, migration-drift, concurrency, accessibility, and responsive checks appropriate to the slice;
- synthetic/redacted UAT scripts and expected control totals;
- reviewed forms/outputs and screenshots without production data;
- operator, administrator, recovery, and support documentation;
- a dedicated `codex/` branch, review, commit, CI, merge, and release note.

No phase may be called complete merely because its screens exist. Completion requires its exit gate and the named process-owner acceptance evidence.

## Out of scope unless separately authorized

- writing to or automating the eGAPS production client;
- importing production history merely because an adapter is technically possible;
- collecting signature images or representing wet signatures as digital signatures;
- bank credentials or unattended bank transactions;
- arbitrary SQL, formulas, macros, scripts, or user-authored posting logic;
- replacing procurement, payroll, HR, Records, or TracePoint with duplicate finance-owned copies;
- public disclosure of confidential financial, employee, supplier, claimant, or banking data.
