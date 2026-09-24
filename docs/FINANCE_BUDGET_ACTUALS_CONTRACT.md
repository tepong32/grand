# Authoritative actuals for Budget proposal context — 2026-09-25

Design checkpoint on `codex/finance-budget-actuals-contract`, based on v0.7.149
`aeb15e55af7e5429ed13f82a4732f4587db0399e`, [draft PR #110](https://github.com/tepong32/grand/pull/110).
This is an implementation contract, not an LGU-approved form. The first
[external-adoption implementation](FINANCE_BUDGET_ACTUAL_ADOPTION.md) has a separate
scope and validation record; native preparation and joint summary certification
remain open. FG-03 remains partial. See the [source audit](FINANCE_BUDGET_ACTUALS_SOURCE_AUDIT.md),
[planning context](FINANCE_BUDGET_PLANNING_CONTEXT.md) and [foundation gate](FINANCE_FOUNDATION_GATE.md).

## Requirement and verified reference

The attached goal, section 7, requires dated historical context that staff can use
to defend a proposal, with missing evidence explicit. It does not authorize guessing
actuals from current values or recreating every eGAPS report. Reuse existing proposal
preparation, submission snapshots and controlled exports.

DBM's [LBM 94 for FY2027](https://www.dbm.gov.ph/wp-content/uploads/Issuances/2026/Local-Budget-Memorandum/LOCAL-BUDGET-MEMORANDUM-NO.-94.pdf),
section 2.2.20 and Annexes D/E, retain the 2023 manual reference. Annex E, PDF pages
23–24, separates historical actuals, first-semester actuals, second-semester estimates
and proposals; it includes capital outlays. The first-semester certification belongs
to the Local Accountant, distinct from proposal preparation/review/approval. Annex D,
PDF page 22, requires joint Local Treasurer–Local Accountant certification for its
historical/current actuals. Annex E also requires office totals to reconcile to the
summary. This establishes these requirements, not every applicable amendment or
local acceptance. Reference retrieval/hash/render evidence is in the source audit.

## What existing code can and cannot establish

| Existing source | Reuse | Boundary |
|---|---|---|
| `budget/planning_context.py` | Exact owner/fund/office/account groups, dated evidence, estimates and frozen submission context | Expense accounts only; no expenditure certification or complete capital-outlay coverage |
| `reporting/datasets.py` Budget actuals | Explicit authorized owner/year scopes, closing/reversal treatment, retained source/output evidence | Reconciled expense totals are not certified expenditure |
| `vouchers/posting.py` and `JournalEntry.source_snapshot` | Original request, event, rule checksum, trigger and recognition decision | A payment or an asset debit alone does not identify new expenditure |
| `accounting/cash_classifications.py` | Immutable source snapshots, independent versions, current-head pattern | Cash-flow purpose is a different classification and cannot certify Budget expenditure |
| `reporting/services.py` / local form acceptance | Retained output bytes, checksums, approval/export and layout controls | Generic report approval/signatory text does not establish the required officer certification |

Keep all new financial evidence in the Finance database (`accounting`/`budget`);
default-store users, offices, attachments and Reporting runs retain their existing
boundaries. No second ledger, financial posting, generic formula engine or new
organization-wide collaboration framework is needed.

## Chosen behavior

Accounting supplies an independently reviewed, versioned actuals statement for an
explicit ledger, fund, office and covered period. The Budget preparer selects or
sees that exact authoritative version next to the existing posted-expense comparison.
For proposed year Y, the comparison periods remain Y−2 and January–June Y−1. Missing
certification is visible; zero requires an explicit certified zero with coverage.

Two evidence routes serve the same result:

1. **Retained external certification.** Adopt an existing dated source document with
   immutable bytes/hash, issuer and actual signatories, source period, scope, row
   references, classifications and control totals. Independent adoption verifies what
   the document actually certifies. The adopting user is not retroactively its signer;
   distinguish original certification date from GRAND's adoption/review date.
2. **GRAND source preparation.** Capture the exact posted source cohort and reviewed
   expenditure classifications, then obtain the required independent certification.
   Suggest amounts from retained recognition/liquidation links; show unresolved
   sources for review rather than requiring staff to reconstruct totals elsewhere.

Do not add external and native totals for overlapping scope. An adopted complete
external statement can be the authoritative actual with native activity shown as
a separate reconciliation comparison. Combining sources requires proven disjoint
coverage or explicit retained reconciliation; unresolved overlap prevents certification.
This restriction prevents duplication and does not erase either source.

The first delivery must be usable end to end: Accounting capture/review, complete
scoped retrieval, Budget selection/missing states, frozen proposal submission and
controlled export. Persistence alone is not a completed checkpoint. External adoption
is the first supported source route because historical data may predate GRAND; native
classification/preparation remains required subsequent work, not silently out of scope.

## Data, authority and version contract

Use a Finance-store scope parent with ordinary database uniqueness over owner, fund,
office, covered dates and statement purpose. Versions and current-certified pointer
share that parent's lock; use ordinary unique constraints supported by MySQL, not an
unsupported conditional uniqueness assumption. Submitted evidence is immutable;
correction creates a new version linked to its predecessor, retaining all decisions.
An older submitted version cannot displace a later certification.

Retain exact decimal row amounts, fiscal/object classifications, explicit coverage
and omissions, source identities/hashes, authority reference, original signatories,
preparer, independent reviewer and decision timestamps. Distinguish full-year and
semester scope, native preparation and external adoption, office expenditure and
joint summary certification. A single generic Approved state must not imply all roles.

Use specific preparation/certification/read/export permissions, explicit office/ledger
scope and current assigned-office checks. Existing posting permission, a department
name, superuser status alone or Budget proposal approval does not confer certification
authority. Record the applicable designation/delegation evidence. Preserve UAT
mutation denial even when operational permissions coexist. Source documents and
financial rows require current scoped read/export access; links cannot grant it.

Budget context pins the certified version, coverage, rows and checksum at submission.
Do not re-read a changing current pointer between totals and source evidence. New
drafts may use a successor; earlier submitted/approved proposals and issued outputs
retain their originals. Old proposals without such evidence are never backfilled.

## Native source preparation and completeness

The [source audit and executable observation](FINANCE_BUDGET_NATIVE_SOURCE_AUDIT.md)
demonstrate unattributed liquidation expenses and invalid asset-debit inclusion.
Use that evidence when implementing the requirements below; do not repair historical
coverage by rewriting posted sources or inferring an office.

Account type is a candidate filter, not an expenditure rule. Capital purchases,
advance releases, deposits/transfers, liability settlements and non-cash movements
can share account classes. Recognition and subsequent payment must not be counted
twice. Reuse exact retained source relationships and reviewed classification evidence;
unresolved historical purpose remains unresolved rather than inferred from descriptions.
Financial-expense, capital and special-purpose coverage needs explicit treatment.
Do not add a tagged/subtotal amount a second time as a separate expenditure row.

Capture one immutable source cohort with its financial lines, source links, dated
reversals, classification versions and capture time. Record included, excluded and
unresolved amounts with a reproducible reconciliation. Blank office attribution,
ambiguous object mapping and incomplete coverage must remain visible. No completeness
claim follows merely from a balanced journal or zero mapping difference.

Certification concerns that frozen evidence, not all future ledger knowledge.
Later/backdated postings or superseding classifications must show that the source
set has changed when selecting it for new work; they cannot rewrite earlier proof.
Current `_post_entry` locks a journal, not a universal period capture gate. Do not
claim that a certificate-parent lock serializes every financial posting. Prove coherent
cohort capture and stale-source detection with native races before native certification
is enabled; preserve default-case-before-Finance order wherever source services require it.

The office statement does not automatically certify LBP Form 1. Joint summary
certification needs its own required actors, matched periods/scope and reconciled
office totals. Preparation estimates and original/adjusted appropriation remain
separate financial states throughout.

## Required acceptance cases

| Scenario | Evidence required |
|---|---|
| Historical external actual, including capital | Exact document/row/hash and scope retained; independent adoption; usable Budget comparison |
| Known zero versus missing document/row | Zero appears only with explicit covered evidence; missing remains unavailable |
| External and GRAND sources overlap | No automatic addition; complete reconciliation or disjoint coverage required |
| One recognition followed by payment/remittance | Original expenditure counted once; settlements retain separate source purpose |
| Capital purchase, advance and cash transfer | Reviewed treatment distinguishes them; no blanket asset-debit inclusion |
| Actual correction versus nominal closing/reopening | Actual correction follows its date; closing lineage does not erase expenditure |
| Foreign office, UAT, unauthorized certifier or self-review | Mutation denied; read/export grants remain separately checked |
| Competing versions or proposal selection during review | One coherent certified version; stale approvals rejected; no mixed totals/evidence |
| New/backdated source after capture | Earlier certificate/output stays immutable; changed-source warning for new selection |
| Form 2 versus Form 1 summary | Office totals reconcile; distinct required officer roles and output evidence |

Implementation checkpoints must run affected SQLite and fresh native MySQL tests,
including persistence identities and relevant races, followed by Budget/Accounting/
Reporting regressions and ordinary browser/source-to-output proof. Exact printer and
LGU acceptance remain separate gates. The local earmark capacity rule is unrelated
and still unconfirmed.

## Validation of this design checkpoint

PASS — current official PDF retrieval, SHA256, text inspection and visual review of
Annex D instructions and Annex E form/instructions; repository source/ownership and
posting-lock inspection; goal section 7 trace. NOT RUN — OUT OF SCOPE: application,
native and browser tests for this documentation-only checkpoint. No application,
schema, source financial data or certification state was changed. No implementation
or officer/form acceptance is claimed by this contract.
PASS — 427 local documentation links across eight changed documents and whitespace
diff check. Canonical operator database hash remains unchanged; no owned MySQL
listener or research download process remains running.
