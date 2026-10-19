# Finance earmark source review — 2026-10-18

DECISION-FIN-001 authorizes research, not Accounting approval. This is a local
source/interpretation checkpoint; it changes no financial rule or transaction.

## Sources actually inspected

1. [DBM BOM for LGUs, 2023](https://www.dbm.gov.ph/wp-content/uploads/Issuances/2023/Local-Budget-Circular/Budget%20Operations%20Manual%20for%20LGUs%2C%202023%20Edition.pdf),
   LBC152, 2 August 2023. Full official PDF retrieved: 327 pages, 7,524,425 bytes,
   SHA-256 `16f23003c2ed3e5f5957cece4a3512418912991782a1c3582414644f6dae0575`.
   Inspected printed pp.165–173 and193; locally rendered pp.170/193 visually checked.
   This supersedes the earlier retrieval-timeout limitation, not the historical log.
2. [RA7160, sections344/360](https://lawphil.net/statutes/repacts/ra1991/ra_7160_1991.html):
   the statute distinguishes Budget appropriation certification, Accounting
   obligation and Treasury funds certification. These are not interchangeable.
3. [GPPB Public Advisory09-2026, 31 July 2026](https://www.gppb.gov.ph/public-advisory-no-09-2026/):
   the March2026 first-edition IRR was withdrawn. Use the approved February2025
   IRR, not the withdrawn PDF still returned by search. No withdrawn text is adopted.
4. [Approved RA12009 IRR, official GPPB copy](https://www.gppb.gov.ph/wp-content/uploads/2025/02/IRR-of-RA-No.-12009.pdf),
   section5(a): the LGU contract budget refers to the appropriation ordinance.
   This does not itself define a municipal earmark's hold/consumption rules.

## Supported interpretation and software boundary

The DBM execution chapter distinguishes ordinance authority, allotment authority
to incur obligations, commitments within allotment, and payment. It describes ARO
releases and explains amounts retained for later release. LBE5A has separate
quarterly financial allocations and physical targets; it is not an earmark
certificate or cash balance. Its form has no generic reserved-amount column.
The manual's procurement references predate RA12009: do not apply them as a
complete current procurement ruleset. A barangay manual is not a municipal substitute.

Engineering inference: retain GRAND's separate appropriation, ARO, obligation and
cash contracts. Do not convert existing withholding into procurement certification
or infer an earmark balance from quarterly-plan leftovers. A local reserved column
cannot acquire a meaning merely because its caption resembles an ARO field.

No inspected source resolves this LGU's exact pre-procurement earmark capacity,
partial consumption, cancellation dates, signatures or numbering. Do not manufacture
those rules. Obtain a representative certificate/registry transaction and reconcile
its source, held amount, later obligation and cancellation before enabling that
specific financial action. Independent development and accepted allocation/
maintenance workflows continue; this is not a blanket Finance development blocker.

## Evidence limits and next action

The alternate 2024-reprint URL and a legacy GPPB IRR landing URL returned404.
Web PDF search/screenshot retrieval was unreliable; local official-PDF extraction
and rendering succeeded. One initial console extraction hit Windows encoding;
UTF-8 output repaired observation without changing source bytes. No direct COA
earmark-circular review, full amendment audit, local procedure acceptance or formal legal
determination is claimed. Retain original source URLs and revisit applicability
before official use. Finance remains **NO-GO**.

Next: obtain representative municipal certificate examples and trace an actual local
transaction against these separate authorities; keep unresolved financial actions
disabled while implementing independently established workflows. No eGAPS or
production data was opened or changed.

## Other-LGU process evidence — inspected2026-10-19

The [General Santos City service index](https://gensantos.gov.ph/?slug=citizen-s-charter)
links separate PR earmarking, adjustment and appropriation-certification services.
The official-hosted [PR service](https://hrmdo.gensantos.gov.ph/uploads/services/511_50c335ad81b4f6dfb18127b4ea2e3ca8.pdf)
describes one department/fund source, approved PR/APP support, RAAO registration,
an assigned reference and distinct review/approval/release stages. The separate
[adjustment service](https://hrmdo.gensantos.gov.ph/uploads/services/508_7712f21ef84ae18e860d30ddd112f325.pdf)
requires an adjustment request and supporting original/cancellation evidence,
with registry recording, validation and approval. These are that city's published
processes, not this LGU's approved capacity formula, form or officials.

Both two-page PDFs were downloaded intact and all four rendered pages inspected:
PR166100bytes/SHA256 `276d6b2ebbb616fc4e67b43a9da07eebd2d1f7c5b985b7fe24ea71f83d6f8db9`;
adjustment174434bytes/SHA256 `8670b4eab4bbd31c8b88fab826d7f001731a4b3409186a8311a873169f6394a7`.
Web screenshots timed out; direct official retrieval/local rendering succeeded.
The PR title says Simple while its classification says Complex; no local time,
classification, copy count, numbering scheme or job title is adopted. The index's
2026 heading does not establish an issuance/effectivity date on each PDF.

Engineering inference: retain the distinction between procurement reservation,
obligation and an appropriation certification. The sources still do not establish
our LGU's exact hold basis, consumption, cancellation dates or issuance authority.
No financial operation is enabled by this research. Reviewing the existing Budget
guards separately exposed an intervening-date control defect; its repair follows
already implemented allotment/obligation invariants, not an inferred earmark rule.
See [the separate control repair](FINANCE_DATED_BUDGET_CAPACITY_2026-10-19.md).
