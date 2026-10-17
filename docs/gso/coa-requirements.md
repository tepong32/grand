# COA sources and GSO workflow coverage

Research checkpoint: 2026-10-16. This is a traceable implementation backlog, not a
certification of compliance or an exhaustive legal opinion. Issuance numbers alone
are ambiguous: distinguish COA circulars, COA memoranda, joint circulars and other
agencies' similarly numbered documents. Before official outputs, inspect the actual
annex, effectivity and amendments with the LGU Accountant and relevant process owner.

## Verified sources and limits

Supplies follow-up2026-10-17: [the request/issue design](stock-request-design.md)
records reviewed historical GAFMIS2003-006 text and COA's indexed2021-007 deferment
listing. Current municipal form/version, complete deferment text and later changes
remain to be verified. Neither a2020 GAM reference nor an NGA/barangay form alone
establishes the applicable municipal output. No executable accounting rule changed.

| Source | What was verified | Application and remaining verification |
| --- | --- | --- |
| [COA Circular 92-386, 20 October 1992](https://www.coa.gov.ph/wpfd_file/coa-circular-no-92-386-october-20-1992/) | COA's indexed listing identifies LGU supply/property management rules. Direct page retrieval failed in this session. | Baseline source for custody, receipt, inspection and accountability. Full text and later amendments still need section-level review; do not invent mandatory fields from its title. |
| [COA Circular 2002-003, 20 June 2002](https://www.coa.gov.ph/wpfd_file/coa-circular-no-2002-003-june-20-2002/) | COA's indexed listing identifies the NGAS manual for LGUs. | Start official LGU form/accounting mapping here; do not assume national-agency or barangay annex numbers apply unchanged to a municipality. Exact applicable editions/annexes remain to be compared. |
| [COA Circular 2023-004, 14 June 2023](https://www.coa.gov.ph/wpfd_file/coa-circular-no-2023-004-june-14-2023/) | COA's indexed issuance listing identifies updated documentary requirements amending 2012-001. | Align GSO evidence with GRAND's existing versioned Finance document rules. Do not build a competing hardcoded checklist. Obtain and review the relevant procurement/receipt annex before declaring completeness. COA's FAQ has a date typo (2003); use the issuance listing's 2023 date. |
| [COA Circular 2024-006, 14 March 2024 — UP Law ONAR record](https://naro.law.upd.edu.ph/issuances/3842) | Official registry metadata specifically identifies supplemental **LGU** implementation of Circular 2022-004 and the increase from PHP15,000 to PHP50,000. | Important LGU-specific companion to 2022-004. The browser limit was overcome by downloading the official copy on 2026-10-17. All 21 pages were visually inspected, including annexes; see findings and remaining limits below. See the source receipt below. |
| [DBM-COA Joint Circular 2024-1, 30 January 2024](https://www.dbm.gov.ph/index.php/joint-circulars?catid=342&id=2627%3Ajoint-circular-no-2024-01-dbm-coa&view=article) and [government-hosted circular](https://www.prc.gov.ph/sites/default/files/COA-DBM%20JOINT%20CIRCULAR%20NO.%202024-1%20DATED%20JANUARY%2030%2C%202024.pdf) | DBM identifies the revised disposal manual; the government-hosted text addresses LGUs among covered entities. | Existing disposal case retains request, authority and completion evidence. This does not yet validate every mode, committee, valuation, document or approval requirement in the manual. |
| [COA PPE inventory-report FAQ](https://www.coa.gov.ph/FAQS/when-should-the-inventory-report-of-property-plant-and-equipment-be-submitted/) | Annual count, December 31 reporting date and January 31 submission are stated in the FAQ. | Existing dated verification and working reconciliation support this work. Confirm the municipal form and signatories before generating an official RPCPPE; a FAQ alone is not an approved local template. |

No claim is made that this search found every superseding issuance as of the research
date. No commercial document summaries are used as the authority for executable rules.

## Product coverage derived from those sources and the user's scope

The workflow choices below are engineering recommendations; they are not quoted
statutory requirements. Build one complete workflow at a time and preserve GRAND's
governed Accounting/Budget decisions.

| Workflow | Current implementation | Next work / authority boundary |
| --- | --- | --- |
| Asset and supply registers | Scoped registers/audit, guided receiving/inspection, inventory materialization and supplied property-determination/useful-life evidence | Native Accounting classification/dimension approval, accepted official forms and historical corrections remain gaps. |
| Receipt evidence | Header/lines, accepted/rejected quantities, private evidence, independent acceptance, documentary cost amendments and linked follow-up inspection of unresolved delivered quantities | Quantity reversal, physical cost-component allocation and accepted official outputs remain separate. |
| Custody and accountability | Department/named GRAND handoffs, witnessed returns and qualified HR-request custody reviews | Accepted PAR/ICS outputs and HR clearance authority remain separate. Never infer signatures or universal clearance. |
| Stock cards / requisition and issue | Quantity/FIFO ledger, reviewed counts, supplied requisitions, partial issues and [reviewed original-issue returns](supply-returns.md) | Legacy return reconciliation and accepted RSMI/RPCI outputs remain gaps; semi-expendable property needs its own authority/form treatment. |
| Physical counts and Accounting reconciliation | Dated counts, unregistered findings, private Accounting snapshot, working CSV | Signed committee/source evidence and accepted official output; preserve missing/duplicate/unreconciled states. |
| Disposal / loss | Disposal evidence and decisions; no dedicated loss case | Compare revised disposal manual; distinguish loss investigation/relief from authorized disposal. No automatic retirement or Finance derecognition from a missing-item finding. |
| Maintenance and other GSO records | Published maintenance cases, private repair evidence and closure history | Vehicle use/fuel/service records and accountable office requests where confirmed in scope. Avoid inventing procurement or HR authority. |
| Financial attribution | Optional reviewed GRAND receipt-to-claim amount attribution, source preview and recognition amount mappings | Physical quantity/cost-component allocation, accepted valuation and official outputs using [GRAND's actual models](grand-integration-design.md); no GSO journal posting. |

The source matrix must be updated with exact sections and tested fields as each
official workflow is implemented. Pending legal/form validation does not block
ordinary receipt and custody development using explicitly non-official working records.

## Primary-text follow-up — 2026-10-17

Downloaded the [official ONAR copy](https://naro.law.upd.edu.ph/storage/01JT2JXVWNE95WHFN0FE53KQC9.pdf):
21 scanned pages, 17,796,221 bytes, SHA-256
`1b00c4e1359868972a84a732dda442619eed040877fb6460acc502250fe15c53`.
Local research copy: `C:/Users/Administrator/.codex/worktrees/gsov2-source-research/coa-2024-006.pdf`.
Text extraction yielded no text; rendered main pages 1–4 were inspected directly.

Verified section-level findings (paraphrased): section 2 covers all LGUs. Sections
3.1–3.4 distinguish qualifying PPE at PHP50,000 and above from below-threshold
semi-expendable property, require PAR/ICS accountability, and distinguish acquisition
from issuance accounting. Sections 3.5–3.8 prescribe retrospective treatment and
separate transitions for prior acquisitions still held versus previously issued.
Sections 4–5 refer to account and entry annexes. Section 8 ties effectivity to
publication; the publication date was not established here.

Design consequence: retain separate receipt, issuance, acquisition date and custody
facts; do not treat semi-expendable equipment as disposable consumables. GRAND
Accounting must apply reviewed treatment and correction lineage. No automatic
historical reclassification is authorized.

Additional visual review: pages 5–8 of the same retained official PDF cover Annex
A.1 (PAR form/instructions) and A.2 (Semi-expendable Property Card form/instructions).
PAR is maintained by fund, renewed every three years or on a custody/user change,
and uses year-month-annual-series numbering. It records quantity/unit/description,
property number, acquisition date/cost, and dated issuer/recipient signatures, names
and offices. Two copies go to the property unit and recipient.

The SPC records class, fund, property number, estimated useful life, acquisition/
issue/transfer/disposal references, quantities, receipt unit/total cost, recipient
office/officer and balance. Its instructions require source-document posting and
annual reconciliation with RPCSPC, including investigation of discrepancies.
Engineering consequence: preserve semi-expendable custody after expense recognition;
do not substitute the consumables ledger or delivery record for an SPC/PAR.
These forms are not yet generated by the app.

Pages 9–10 (Annex A.3) were also visually checked: the Semi-expendable Property
Ledger Card belongs to Accounting, separately from the property unit's SPC. Its
fields include source/JEV reference, receipt quantities/cost, issues/transfers/
adjustments, adjusted cost, and repair nature/amount. Instructions require
reconciliation against physical count, SPC and control accounts. GSO may provide
custody/repair facts but must not create a competing financial ledger.

Pages 11–12 begin Annex B. Verified listed account families cover semi-expendable
machinery/equipment and furniture/fixtures/books inventories, related supplies
expenses and repair expenses. Page 12 describes initial acquisition debits and
credits on issuance, impairment, transfer, loss or disposal for its first four
inventory accounts. This supports keeping receipt, issuance and financial adjustment
as separate events; it does not authorize automatically posting a new account map.
Pages 13–17 complete Annex B: further equipment categories, furniture/fixtures/books,
issuance expenses and day-to-day repair expenses are separately described. Pages
18–21 (Annex C) illustrate four distinct transitions: pre-2024 acquisitions still
held by the property unit; pre-2024 acquisitions already issued; pre-2024 acquisitions
issued in 2024; and acquisitions and issuance both in 2024. The examples distinguish
reclassification, closing accumulated depreciation/impairment, prior-period
adjustment and issuance expense. These are illustrative cases, not permission to
reclassify every historical item based on its present price alone.

All 21 pages of this retained copy have now been visually reviewed. Publication date,
later amendments, local adoption and related issuances remain to be established.
Implementation consequence: retain acquisition and issuance dates, original cost,
custody state and Finance correction references separately. Accounting must review
the applicable transition and amounts; no journal recipes or automatic account
mapping were introduced by this research.
