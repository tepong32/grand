# Form 1 PhilHealth source and overlap audit - 2026-10-12

Development checkpoint, local/unpublished; no runtime or financial mutation.
Continue the [assembly design](FINANCE_FORM1_ASSEMBLY_DESIGN.md) and
[source contract](FINANCE_FORM1_SOURCE_CONTRACT.md). FG-03/FG-06 and Finance
production remain incomplete. This audit does not establish local SHF participation,
contractual arrangements, mandatory form acceptance or an approved deduction.

## Public evidence inspected

The current retained DBM LBM 94 Annex D has a separate PhilHealth deduction beneath
ending balance, before net ending balance, in Form 1. Its instructions require net
beginning cash after specific-purpose restrictions. Its main text permits relevant
LBP forms to be adjusted for PhilHealth payment and SHF-funded PS expenditures;
this does not specify the LGU's exact overlap adjustment. The official PDF was
reconfirmed by web search and retained bytes were hash-verified:
`14C63DAA682E695DDE09E0BA68A9E844D029959111A50028318ED23C8720AAAD`.
[Official LBM 94](https://www.dbm.gov.ph/wp-content/uploads/Issuances/2026/Local-Budget-Memorandum/LOCAL-BUDGET-MEMORANDUM-NO.-94.pdf).

The official DBM download of DOH-DBM-DOF-DILG-PhilHealth JMC 2021-0001,
January 13, 2021, was obtained and pages 2-8 were rendered and visually inspected.
Its SHF definitions/classification/coverage, management, funding, allowable expenses,
counterpart funding, creation and budgeting sections distinguish:

- Participating province/city-wide health systems and their responsible health
  boards, rather than inferring an SHF from a department or receipt label.
- PhilHealth income and other funding sources, with their respective contractual
  or transfer evidence, rather than treating every health receipt as the same source.
- SHF allowable expenses and ordinary LGU mandatory counterpart funding not pooled
  to the SHF. A health purpose does not by itself establish an SHF charge.
- Separate SHF accounts/books and subsidiary source evidence, including transfers
  from SHF to component LGUs' Trust Funds. A General Fund source cannot be silently
  substituted for those different original fund/transfer routes.
- Health-board budget resolutions and the required planning/budget documents.
  Automatic appropriation does not invent an issued form, officer signature,
  transfer, available cash or an approved local allocation.

Source hash: `5FB57D6D8BA0A0E2BDA2CE3EC1D07F2D3FF74C99AC03C56724C0AFA11F054289`.
[Official JMC download](https://www.dbm.gov.ph/wp-content/uploads/Issuances/2021/Joint-Memorandum-Circular/JMC-2021-0001_Guidelines-on-SHF.pdf).
The Supreme Court's RA 11223 sections 20-21 and the official 2023 Budget Operations
Manual SHF chapter corroborate the separate health funding/PhilHealth income
boundary. This audit does not claim all later amendments were checked.
[RA 11223](https://elibrary.judiciary.gov.ph/thebookshelf/showdocs/2/86448),
[official 2023 manual](https://www.dbm.gov.ph/wp-content/uploads/Issuances/2023/Local-Budget-Circular/Budget%20Operations%20Manual%20for%20LGUs%2C%202023%20Edition.pdf).

## Executed original-source audit

`python .tmp/audit_philhealth_sources.py` PASS/exit 0 on the existing isolated
account/SPA clerk rehearsal, with no migration, seeding, new review or posting.
The public SPA service checks actual source/model/attachment visibility before
matching its whole snapshot to the original download. Original review
`cc8d4253-d9d6-46a5-9080-6aded18f7f06`, checksum
`6a957a96ab5072a105044bed014da43ee333c4f1c7c353a93a3801a7120414ee`.
Scope: Accounting 2, Budget 1, Treasury 6, Fund 1, `general`, budget year 2027.

All four original PhilHealth receipt controls are covered zero, with no monetary
PhilHealth components: prior actual, H1 actual, H2 estimate and proposed. Detached
component/output reproduction uses zero default/Finance queries. Three original
expense components remain; their ledger/office/allocation/source evidence does not
itself supply a reviewed combined SHF funding/overlap schedule. The original review
payload, downloaded snapshot and two source journals remain unchanged. The existing
output still declares PhilHealth deduction incomplete. It is neither changed into
an issued zero deduction nor augmented with cash records from other rehearsal stores.

Evidence: `.tmp/form1-philhealth-source-audit.log` and
`.tmp/form1-philhealth-source-audit.json`. These are synthetic source-reproduction
facts, not municipal figures, non-zero/signed PhilHealth coverage or LGU acceptance.

## Implementation boundary following this audit

Reuse the original component inventory and selected stock calendar; do not add an
SHF module or change Accounting posting rules for this Form 1 work. Retain actual
policy/authority and overlap worksheet bytes for the whole proposal/entity scope.

1. Partition every original signed PhilHealth receipt component explicitly, retaining
   original receipt/forecast identity and source column. Opposite receipts/corrections
   remain separate even when their net is zero. Complete category zero differs from
   missing source coverage or absent reviewed deduction evidence.
2. Identify each relevant opening restriction by its exact original/forecast identity,
   date, scope and amount. Keep carried restrictions separate from new period income.
   An earlier opening restriction cannot automatically offset a later receipt;
   matching names/amounts are not shared source lineage or overlap evidence.
3. Any alleged already-accounted expense must identify its exact original signed
   expenditure component and actual SHF funding/authority evidence. Ordinary LGU
   health counterpart expenditure is not classified as SHF by its account/title.
4. Source caps apply across all parts and related columns. No chained/duplicated
   overlap or invented credit may reduce the deduction. If overlap treatment is
   unresolved, keep the affected deduction/net-ending control unknown. Do not rewrite
   original receipt, stock, office or journal history to force a reconciliation.
5. Retain source gross ending, explicit proposed deduction, any separately authorized
   presentation adjustment and net ending as distinct controls. National guidance
   above does not establish a local adjustment recipe for every overlapping expense;
   do not silently net SHF expenses against PhilHealth receipts.
6. Derive current-total period deductions from the exact H1/H2 treatment once; reuse
   annual opening stock as its boundary reference. Governed whole-package review
   must pin original sources, authority bytes, independent decisions and approved
   treatment before clerk/printable issuance. Source approvals are not final signatures.

Next implement and exercise this source/overlap schedule within full Form 1 assembly,
including genuine positive/negative PhilHealth, explicit zero, missing evidence,
carryover-versus-period identity, duplicate caps, wrong-fund transfers, counterpart
expenses, role/export revocation and retained successors. Cash timing/planning-source
reconciliation, shared-entity allocation, whole-package reviews/signatories, clerk
delivery and LGU acceptance remain required. Missing local documentation does not
block ordinary development: unresolved cases remain explicit for later independent
resolution, while no unproved deduction or capacity is granted.

Validation: PASS source-authorized read-only audit and official-source visual review.
Runtime code unchanged; new SQLite/MySQL regression, native races, browser/printing,
whole-Finance and operational/LGU acceptance NOT RUN - OUT OF SCOPE for this audit.
PASS: both source hashes, 543 local documentation links/16 files, new-document
whitespace and diff check. Canonical default/Finance database hashes are unchanged;
no live runner or test/browser listener remains. Work remains local/unpublished.

## Subsequent draft implementation - locally validated, unpublished

`budget/form1_philhealth.py` now builds a complete original source catalogue and
signed partitions over PH receipts, opening restrictions and expenses. Explicit
classifications preserve ordinary counterpart versus SHF expense and carryover
restriction identities. Claims use exact counterparts and shared classified source
caps, including forecast columns retaining the same original restriction. No claim
or non-zero SHF expense silently supplies an approved offset; these keep affected
deduction/net ending pending. Complete sources, coverage and attached original
policy/worksheet metadata are required for known draft controls. Current server
capture and historical reproduction separately enforce actual source/byte authority.
Detached verification is arithmetic only, with no independent review/capacity/issuance.

Four own genuine-source tests PASS on SQLite and native MySQL, no skips, exit 0,
both stores cleaned up (290.820s/260.972s). Initial dependent runs each executed
12 cases and failed one current-work fixture error: overwritten stock dictionaries
were passed to a helper expecting original reconciliation models. Preserve original
inputs before replacement; corrected final runs exercise the signed +17/-7 sources.
The fixture import avoids duplicate stock tests; canonical part ordering now precedes
derived member output. CONTINUE.md retains commands, failed/final logs and scope.
This implementation adds
no persistence, migration, role, posting or reviewed policy adjustment. Full governed
retention/review, cash timing/planning links, shared entities, clerk delivery,
signatories/issuance and broad operational/LGU acceptance remain open.

## Treatment evidence checkpoint - 2026-10-12

The retained LBM 94 hash above was rechecked. PDF page 21 was rendered anew
with Poppler and visually inspected (`.tmp/lbm94-form1-page21.png`): gross
ending balance precedes the PhilHealth automatic-appropriation deduction and net
ending balance. The five amount columns and four certifiers plus Chief Executive
approval remain distinct. Extracted text order alone does not prove that layout.
No overlap formula is stated by the inspected row. JMC 2021-0001 retained bytes
also reproduce the hash above; no new arithmetic is inferred from its SHF scope.

New primary-source evidence: BLGF MC 012.2025, dated March 24, 2025, describes
SHF utilization reporting for FY2023 and succeeding years and cites DOH Memorandum
2023-0168, Item IV.B (planning and budgeting). Its indexed first-page text explicitly
distinguishes pooled SHF receipts/disbursements from LGU mandatory counterpart
funding not pooled into SHF. This corroborates separate source classifications;
it does not establish this LGU's participation or a Form 1 overlap deduction.
[Official BLGF circular](https://blgf.gov.ph/wp-content/uploads/2025/12/MC-No.-012.2025-Guidelines-on-the-Submission-of-Reports-on-SHF-Utilization-of-LGUs-24-Mar-2025-1.pdf).
Direct web and PowerShell retrieval returned HTTP 403; Python retrieval failed
certificate-chain verification. Verification was not disabled. Only the indexed
primary-source text was inspected; the full circular, annexes and DOH memorandum
are not verified. Do not treat them as inspected retained authority attachments.
A DOH regional report dated July 14, 2026 confirms SHF manual workshops; it is an
implementation report, not an applicable signed presentation recipe.
[DOH regional report](https://ro12.doh.gov.ph/%F0%9D%90%83%F0%9D%90%8E%F0%9D%90%87-%F0%9D%90%82%F0%9D%90%87%F0%9D%90%83-%F0%9D%90%92%F0%9D%90%8E%F0%9D%90%97-%F0%9D%90%9B%F0%9D%90%A8%F0%9D%90%A8%F0%9D%90%AC%F0%9D%90%AD%F0%9D%90%AC-%F0%9D%90%94/).
No exhaustive amendment search or local adoption is claimed. A DBM forum's mention
of several circular numbers is insufficient to identify an SHF amendment; the
actual instruments and applicability must be inspected before using their rules.

### Required proof before treatment changes a control

| Question | Required retained evidence | Current implementation consequence |
| --- | --- | --- |
| Does SHF apply to this entity/Fund/period? | Actual participation, fund/transfer route, authority dates and original documents | A health label or another LGU's resolution cannot establish applicability |
| Is an expense funded by SHF or ordinary counterpart? | Exact original expense part and funding authority, with full signed amount | Keep `shf` and `counterpart` separate; non-zero SHF treatment remains pending |
| Is the alleged overlap the same underlying money? | Exact receipt/restriction/expense identities, dates, component lineage and worksheet | Equal amounts and labels are insufficient; retain the claim without an offset |
| What changes the presented deduction? | Explicit applicable recipe, source-bound contributions, original authority/worksheet bytes and independent decisions | Do not enter a free-form expression or guessed final deduction |
| Is capacity reused? | One complete proposal over all entities, source parts and columns, with original capacity identities | Check shared caps globally before review; H1/H2 derive current totals once |
| Does a correction alter history? | Fresh successor bound to its original treatment/package and fresh independent review | Reproduce original outputs and decisions unchanged; no invented JEV |

Implementation must distinguish an independently reviewed **rejection of an overlap
claim** from approval of an offset. Rejection can establish that specified receipts
remain fully deducted only when the complete expense/funding reconciliation supports
that result; it cannot silently resolve other non-zero SHF parts. An approved overlap
claim alone still does not determine a numeric deduction. The applicable presentation
recipe must separately say which exact signed contributions affect deduction and any
separately authorized adjustment. Source sign, original cap, source column and full
coverage must reproduce that recipe, not merely match a user-supplied net amount.

Next implement versioned treatment proposals and independent return/rejection history
against the exact original stock/PhilHealth inventory, preserving unknown arithmetic
until a supported recipe is approved. Bind retained documents and all part identities;
keep source read/export authorization and proposal-before-Fund lock order. Integrate
only through a new whole-package preparation with fresh independent package decisions,
never by changing an existing assembly's completeness flag. This proposal/review route
and eventual evidenced adjustment remain required functionality, not a waived gate.

Validation: PASS retained hashes and original Form 1 visual inspection. New official
indexed evidence changes the applicability/source checklist but proves no formula.
Runtime/model/migration/roles are unchanged. SQLite/native tests and browser/physical/
LGU acceptance NOT RUN - OUT OF SCOPE for this evidence checkpoint; no new runtime
behavior is claimed. Missing local evidence does not block ordinary non-overlap clerk
delivery, retrieval and outputs; unsupported adjustments remain explicit pending cases.

## Official COA lead resolved by scope inspection — 2026-10-17

The [UP Law Center ONAR record](https://naro.law.upd.edu.ph/issuances/8092)
provides the filed [COA Circular 2025-002 PDF](https://naro.law.upd.edu.ph/storage/01K96TA5EB4D41Z2KZ5PNQTT8Y.pdf).
The scan identifies the January 28, 2025 circular and April 23, 2025 ONAR filing.
Section 2, PDF page 3, addresses PhilHealth head/regional-office accounting for
provider payments. Section 4 and the opening of Section 5, page 7, concern those
offices' budget registries and separate subsidiary accounts in Corporate Fund books.
**Inference for GRAND:** this instrument alone does not establish a municipal
Form 1 overlap-offset recipe. Do not transpose insurer-side entries into LGU
books or treat a matching circular number as municipal presentation authority.

Retrieval PASS with TLS verification: retained
`.tmp/coa-circular-2025-002-onar-20261017.pdf`, 22,139,522 bytes, 35 pages, SHA-256
`1104d2a10348ac419d7a2e9aee2c8eb370d3db4d8add73898875b659819cf497`.
The scan has no extractable text; Poppler renders
`.tmp/coa2025-002-page-01.png` through `-07.png` were visually inspected.
**Only pages 1–7 were inspected; pages 8–35 and annexes are not claimed reviewed.**
No numerical, posting or configuration change follows this scoped finding.
The numerical gate remains open; the already-implemented factual-review route is
documented in [the treatment checkpoint](FINANCE_FORM1_TREATMENTS_IN_PROGRESS.md).
