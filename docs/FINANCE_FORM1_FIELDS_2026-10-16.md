# Form 1 fields, retained LGU identity and remaining certification

Subsequent October 17 continuation: designation, unsigned-copy and
[signed/final clerk software](FINANCE_FORM1_SIGNED_COPIES_IN_PROGRESS.md) now have
local implementation/scoped validation. The missing-software/next-action findings
below describe this audit's earlier state; do not recreate completed stages.
Actual appointments, signatures, accepted forms and full Finance gates remain
separate. CONTINUE.md owns current state and the next numerical-treatment milestone.

Local checkpoint, 2026-10-16, Asia/Singapore. Branch
`codex/finance-form1-print-evidence`, base v172 / `32ab046`. No release, operator
configuration, statutory signature, approval or migration is performed here.
This extends the [print repair](FINANCE_FORM1_PRINT_EVIDENCE_2026-10-16.md), not
the authority to certify or issue a form. **Production NO-GO.**

## Official source and field comparison

The official [LBM 94 page](https://www.dbm.gov.ph/index.php?catid=453&id=4049%3Alocal-budget-memorandum-no-94&view=article)
identifies the June 10, 2026 FY2027 budget-preparation memorandum. Its
[official PDF](https://www.dbm.gov.ph/wp-content/uploads/Issuances/2026/Local-Budget-Memorandum/LOCAL-BUDGET-MEMORANDUM-NO.-94.pdf)
was downloaded again over HTTPS: 19,442,172 bytes, SHA256
`14c63daa682e695dde09e0ba68a9e844d029959111a50028318ed23c8720aaad`, identical
to the earlier retained source. Annex D pages 20–22 were rendered and inspected.
The web fetcher's size limit did not block the direct download. Retained source:
`.tmp/dbm-lbm94-form1-20261016.pdf`; images
`.tmp/dbm-lbm94-form1-source-{20,21,22}.png`.

The 2023 manual was also reopened from DBM as a separate historical reference.
This compares the cited Annex D; it is not a complete audit of later issuances or
local applicability. Bundled `pdftotext` was unavailable, so source inspection used
the successful Poppler renders. No missing source is inferred from that tool error.

| Field / reference | Actual current state |
| --- | --- |
| LGU identification, p. 20 | **REPRODUCED OMISSION, repaired locally:** the explicit retained office-source LGU name was absent from the whole PDF. It now appears with its source qualified. Missing/conflicting identification remains Unknown; this does not certify jurisdiction or final designation. |
| Fund, entity and comparison years, pp. 20/22 | Explicit member/Fund/year scopes and entity inventory support working drafts. Actual local inventory and accepted layout remain unconfirmed; do not invent enterprise modules. |
| Particulars, account identification and five financial columns, pp. 20–22 | Existing complete controls and appended original account/SPA itemization retain the sources. Exact local-form fidelity remains open. |
| Beginning cash after restrictions, period flows, ending, PhilHealth deduction and net ending, pp. 20–22 | Existing separate controls and unknown states remain. Internal findings cannot supply a numerical overlap recipe, actual cash or statutory certification. |
| Historical/H1 joint certification and H2 preparation, p. 22 | Source certifications and separate estimates are prerequisites. They do not certify the final whole form; preserve Treasurer/Accountant actuals responsibilities and Budget preparation. |
| Four whole-form certifying functions, p. 21 | **KNOWN NATIONAL ROLE SET; SOFTWARE NOT IMPLEMENTED:** Local Treasurer, Local Budget Officer, Local Planning and Development Coordinator and Local Accountant. Three-office internal review is different. Do not infer Planning designation from Budget membership. |
| Chief Executive approval, p. 21 | **SOFTWARE NOT IMPLEMENTED** for the whole form; separate from the four certifications. Actual local designation/signature evidence remains unconfirmed. |
| Final signed/issued copy and corrections | Immutable draft/source/export evidence exists. A final whole-form certification/approval/issued-copy lifecycle remains an implementation gap, not only a printer/manual-acceptance task. |
| Local names, appointments, signatures, printer and office acceptance | **UNKNOWN / MANUAL ACCEPTANCE:** require actual evidence. Do not fabricate it or defer all configurable software work indefinitely because names are unavailable. |

## Implemented source reuse

Retained Form 2 office payloads already include an explicit `lgu` field. Whole-flow
verification binds their original forms, entity, proposal and Fund. The renderer
now reads that field from verified retained evidence, never from current department
labels or a user profile. All recorded office names must agree exactly across the
package; the displayed member must have its own office source. Missing, blank,
foreign-entity-only or differing names remain Unknown. Case folding cannot resolve
conflicting identity evidence. Original names remain available for resolution.

This is draft context only. Form 2's Department Head/Budget/Chief Executive tuple
is not reused as Form 1's certification tuple. No original payload, attachment,
decision, source checksum, amount or permission changes.

Before repair: `.tmp/form1-lgu-before.log` retains the actual exit-1 assertion that
`SYNTHETIC TEST MUNICIPALITY - Peña` exists in the original source but is absent
from the PDF. Classification: **FAIL — PRE-EXISTING OUTPUT OMISSION**, not a fixture
failure. Scope/severity: **LOW draft identification/readability gap**.

Pure reproduction: `.tmp/form1-print-lgu-final-20261016/`, deterministic and
zero-query, unchanged input, eleven pages per variant. Eight changed images
(pages 1–4 each) were inspected; fourteen others match the prior inspected output
byte-for-byte. No clipping, overlap or new missing glyphs observed.

The existing genuine print/HTTP test checks source reuse plus missing, blank,
foreign-entity, duplicate and conflicting names, including conflicts across members.
No test identity or skip was added.

```powershell
& 'C:/Users/Administrator/Desktop/GH/grand/.venv/Scripts/python.exe' -B -X utf8 .tmp/intake_primary_sqlite.py budget.test_form1_package_print --verbosity 2
& 'C:/Users/Administrator/Desktop/GH/grand/.venv/Scripts/python.exe' -B -X utf8 .tmp/intake_primary_native.py budget.test_form1_package_print --verbosity 2
```

**PASS:** focused genuine print/HTTP case on SQLite / **59.580s** and native /
**59.325s**, zero skips, actual exit 0; both stores destroyed. Logs:
`.tmp/form1-lgu-final-{sqlite,native}.log`; two-file source freeze:
`.tmp/form1-lgu-source-freeze-20261016.json`. The preceding eleven-case dependent
passes are historical evidence before this header change. Standalone flow/SPA and
export code is unchanged since those passes; do not claim those suites were rerun.
Strict proof `.tmp/form1-lgu-local-acceptance-20261016.json` verifies current four
source/test hashes, matching case identity, cleanup, unchanged operator databases,
official-source hash, monetary/source preservation and page-image comparison.
Django check and diff check PASS; owned MySQL stopped after native exit 0.
New synthetic samples: [reviewed](../output/pdf/form1-synthetic-reviewed-lgu-draft-20261016.pdf)
and [unknown treatment](../output/pdf/form1-synthetic-unknown-lgu-draft-20261016.pdf).
Previous samples/proofs are preserved. All changes remain local/uncommitted;
no new VM release, CI publication, deployment or source policy approval.

**NOT RUN — OUT OF SCOPE:** another full/remote suite for this unpublished narrow
header addition; only whole PDF rendering/test changed after the preceding
eleven-case dependent passes. Native focused proof is included because these
outputs cross both stores. Required release gates still apply before publication.
Actual normal-browser saving, printer, signatory and LGU acceptance remain unperformed.

## Next functional milestone

Build a separate immutable final preparation/certification/issued-copy lifecycle
over the exact reviewed whole package. The published role set is known enough to
scope software; actual operator appointments/signatures remain manual gates.

1. Pin complete calculations, exact package/version, current original-source
   evidence, explicit LGU identity and actual designation/authority records.
   Pending treatments or identity conflicts block signing-copy issuance.
2. Preserve independent preparation/review and an unsigned signing copy with all
   four certification functions and separate Chief Executive approval. A directory
   entry, typed name or internal approval is not a signature. Reuse governed
   patterns without copying Form 2 signers or broadening raw-source access.
3. Retain actual physical signed-copy/approval evidence and independent verification
   before final issued status; signing officials need not be fabricated web users.
   A file upload or checkbox alone does not automatically establish certification.
4. Preserve issued bytes, source/export authority and successor/correction history.
   Form issuance creates no journal, available cash or earmark.
5. Establish owning lock/cross-store behavior from current services, then prove
   native competing preparation/decision/currentness and ordinary clerk delivery.
   Do not build a generic signature/collaboration framework for this workflow.

No final certification/issued workflow is claimed here. Required local/physical
acceptance, numerical treatment and the complete Finance goal remain open.
