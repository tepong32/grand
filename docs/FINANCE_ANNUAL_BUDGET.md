# GRAND Finance annual budget preparation and authorization (F3.1–F3.2)

This slice introduces GRAND's first Budget-domain workspace while deliberately stopping before operational appropriation authorization. It implements annual calls, department ceilings, classified proposal and consolidation versions, performance targets, resource estimates, review evidence, comparison, and portable export.

## Authority boundary

- A ceiling limits proposal preparation; it is not an appropriation, allotment, obligation, accounting entry, or cash balance.
- Draft, submitted, returned, and approved proposal versions are not spendable authority.
- Only the F3.2 authorization workflow may mark a final, supplemental, or reenacted version as operational appropriation authority after ordinance, review, conditions, effectivity, and signed control totals are accepted.
- This structure is informed by the Finance evidence register and DBM/COA reference baseline. It does not claim that a synthetic schedule or CSV is an official local form.

## Controlled workflow

1. A Budget preparer creates an annual call against an approved or active typed fiscal year and records the applicable local authority, instructions, dates, and office/fund/expense-class ceilings.
2. A different Budget reviewer publishes the call or returns it with a specific correction reason. Published call content and ceilings are immutable.
3. Proposal preparers create explicit versions and classify every amount by fiscal year, fund, responsibility center, PPA/project/activity, funding source where applicable, posting account, expense class, and appropriation type. Targets and change explanations stay with the line.
4. Submission checks that the call is published, at least one line exists, and no classified proposal total exceeds its published ceiling.
5. A different reviewer approves the proposal or returns it. Approval remains visibly non-spendable.
6. Reviewers can consolidate approved department proposals into a new executive draft. GRAND copies lines and resource estimates, retains source-version lineage, and leaves every source unchanged.
7. Comparison groups changes by governed classification instead of comparing presentation rows only.

## Corrections and modification allowance

Draft and returned calls and proposals can be edited through guided forms. After call publication or proposal approval, governed content is immutable: the operator creates a successor version with a change explanation. This is stricter than the later voucher modification allowance because budget-version authority must remain reconstructible.

## Guided proposal and authority queue

The Annual Budget workspace keeps calls and ceilings in their existing register and adds filters only to the proposal/appropriation-version list. Budget staff can narrow that list by fiscal year, version kind, exact proposal status, or the next governed action:

- preparation or returned correction;
- independent proposal review;
- approved proposal that remains nonspendable;
- final/supplemental/reenacted version needing authority evidence;
- authority evidence awaiting independent authorization; or
- independently authorized operational appropriation authority ready for F4 allotment control.

The visible next action is derived from the existing proposal and authorization records; it is not another workflow state. Contradictory filters correctly produce an empty list instead of silently broadening scope.

`Export visible register` uses those exact filters and creates one oversight row per visible version. It includes proposal and resource totals, authorization/review references, signed control and difference, checksum, maker/reviewer lineage, and state version. Classified proposal lines remain in the existing per-version export, while immutable authorized lines remain in the authorized-appropriation export.

## Export and TraceSync

Every proposal CSV downloaded through GRAND is also archived under `GRAND_EXPORT_ROOT`:

`department / user / finance-budget-proposals / year / month / timestamp_checksum_filename`

The sibling manifest records SHA-256, actor, department, proposal version/status, and the fact that the export is controlled data interchange—not automatically a DBM/COA form. Copy or synchronize the entire root so artifacts and manifests remain together.

The filtered oversight register is archived separately under `finance-annual-budget-register` using the same department/user/year/month structure. Its manifest retains the selected filters, result count, authority boundary, and SHA-256, and an append-only Budget event retains the archive receipt. All Budget workspace viewers can export the same department-bounded evidence they can inspect; export never changes proposal or appropriation authority.

## Roles and acceptance

- `Budget Voucher Officer` includes call and proposal preparation alongside the shadow voucher permissions.
- `Budget Review and Consolidation Officer` independently publishes calls, reviews proposals, consolidates versions, and sees Budget audit evidence.
- `Finance UAT Viewer` receives view-only access.

Run `python manage.py configure_finance_roles` after applying migrations. The command also seeds the role-aware Annual Budget Internal How-To for matching Budget departments.

## F3.2 operational appropriation authorization

An approved final, supplemental, or reenacted version becomes operational authority only after a separate maker-checker evidence record supplies:

- authority type, ordinance/reference number and date, and effectivity;
- dated review result/reference and complete conditions when conditional;
- accepted ordinance, review, and signed schedule evidence references;
- a signed control total equal to the exact approved version total; and
- an independent authorizer who is not the evidence submitter.

Authorization creates immutable classification snapshots and a canonical SHA-256 checksum. Only then does `is_spendable_authority` become true. Authorized schedules export into the `finance-authorized-appropriations` category of the same portable archive tree. Corrections require the applicable approved successor version; the authorized source and snapshot are never rewritten.

Before production use, Budget process owners must accept the call, ceiling, proposal, target, resource-estimate, comparison, ordinance/review evidence, authorized schedule, and exports against applicable current issuances and local practice. F4 remains required before authority can be released as allotment or consumed as an obligation.
