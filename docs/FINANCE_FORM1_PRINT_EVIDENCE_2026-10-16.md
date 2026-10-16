# Whole Form 1 draft evidence presentation

Subsequent [official-field/LGU source follow-up](FINANCE_FORM1_FIELDS_2026-10-16.md)
adds the omitted retained LGU name, with a new focused SQLite/native pass and
new `-lgu-draft-` samples. The source freezes and eleven-case passes below retain
their pre-header checkpoint scope; use CONTINUE.md for current source/proof.

Local checkpoint, 2026-10-16, Asia/Singapore. Branch
`codex/finance-form1-print-evidence`, based on accepted v172 /
`32ab04669da05b868f6c8b8ff37e0f71b3805555`. Source and documentation changes are
uncommitted and unpublished. This does not change statutory authority or close
the complete Finance gate. **Production NO-GO.**

## Demonstrated gap and repair

The [whole-package delivery design](FINANCE_FORM1_PACKAGE_REVIEW_DESIGN.md)
recorded raw dictionary/field notation and separate appendix numbering as clerk
presentation gaps. A fresh genuine-source SQLite fixture reproduced them in the
current output: scope/restriction/forecast/coverage/decision/document sections used
Python-style dictionary notation; whole controls and appended flow/SPA pages
numbered themselves separately. This is a **LOW pre-existing output-usability
defect**, not evidence of altered financial calculations or unauthorized access.

`budget/form1_package_print.py` now labels retained evidence fields and opening
columns, displays explicit Yes/No and Unknown states, and retains every displayed
source value. Empty collections say “No retained entries”; they do not certify zero
money or complete coverage. Source codes, reference text and original free-text
bases remain evidence rather than being guessed or rewritten.

The complete generated PDF is numbered once, **Page 1 of N → Page N of N**.
The existing flow/SPA renderers accept a presentation-only `number_pages` option;
its default preserves their standalone numbering. The whole-package renderer
suppresses only their generated page numbers and stamps the complete sequence
after composition. Original draft/source footers remain visible. No white overlay
conceals source text, and no original authority attachment is edited.

No schema, posting, source calculation, role, permission, review, signature,
issuance or persistence contract changed. Rendering still validates the complete
original envelope; internal review supplies no statutory or Chief Executive
approval, form issuance or cash availability. Existing unknown deduction/net
controls remain unknown. Historical files and retained source envelopes are not
rewritten. The unsigned output remains explicitly incomplete and not ready to sign.

## Same-source artifact checks

Baseline genuine-source test: one SQLite case PASS / 56.287s, zero skips, exit 0,
both stores destroyed. Original reviewed/unknown envelopes and PDFs are retained
under `.tmp/form1-print-before-20261016/`. Detached baseline reproduction is in
`.tmp/form1-print-original-pure-20261016/`; repaired reproduction is in
`.tmp/form1-print-after-first-20261016/`. Both versions use the exact same captured
envelopes, without database reads or source mutation.

| Retained variant | Pages before / after | Monetary occurrences preserved | Original printed unique SHA256 / UUID values preserved |
| --- | --- | --- | --- |
| Internally reviewed synthetic draft | 11 / 11 | 441 / 441 | 29 / 11 |
| Unknown-treatment synthetic draft | 11 / 11 | 431 / 431 | 24 / 8 |

Both new PDFs render deterministically with zero default/Finance queries. Input
envelopes remain identical, and PDF subject metadata retains the original complete
evidence checksum. Artifact checks verify every page number, draft marker, original
printed source hash/UUID and the complete multiset of monetary occurrences. They
also verify that raw dictionary notation is absent from these fixtures; original
free-text source contents are not sanitized into different financial evidence.

All twenty-two pages were rendered through Poppler at 1,600 pixels. All sixteen
distinct page images were inspected; unknown pages 6–11 are byte-identical rendered
PNGs to the inspected reviewed appendix pages. Financial tables, unknown controls,
source IDs/hashes, review/document sections and footers show no clipping, overlap
or missing glyphs. The existing Poppler Symbol/ArialUnicode lookup warnings also
occur before the change; no font replacement was made to suppress them.

Verification: `.tmp/form1_print_render.py`,
`.tmp/verify_form1_print_artifacts.py` and
`.tmp/form1-print-after-first-20261016/artifact-verification.json`.
Four changed source/test files are frozen in
`.tmp/form1-print-source-freeze-20261016.json`. Synthetic review samples:
[reviewed draft](../output/pdf/form1-synthetic-reviewed-draft-20261016.pdf) and
[unknown-treatment draft](../output/pdf/form1-synthetic-unknown-draft-20261016.pdf).
These are engineering fixtures, not real LGU documents or signing copies.

## Dependent regression and release boundary

The existing print regression now asserts continuous numbering in reviewed and
unknown PDFs, readable evidence labels, absence of serialized fixture dictionaries,
and unchanged input envelopes. Existing checks retain original parts/checksums,
determinism, zero queries, actual authorized HTTP PDF bytes and rejection of
rehashed derived financial corruption. No new test identity or skip was introduced.

Dependent scope: whole-package print and JSON/ZIP export, standalone SPA output and
flow output. This covers both modified renderers' default behavior, signed/opposing
sources, unknown/stale/returned history, three-office export and permission loss,
UAT boundaries, rehashed source corruption and unsupported glyph rejection.

```powershell
& 'C:/Users/Administrator/Desktop/GH/grand/.venv/Scripts/python.exe' -B -X utf8 .tmp/intake_primary_sqlite.py budget.test_form1_package_print budget.test_form1_package_exports budget.test_form1_spa_output budget.test_form1_flow_output --verbosity 2
& 'C:/Users/Administrator/Desktop/GH/grand/.venv/Scripts/python.exe' -B -X utf8 .tmp/intake_primary_native.py budget.test_form1_package_print budget.test_form1_package_exports budget.test_form1_spa_output budget.test_form1_flow_output --verbosity 2
```

Set `GRAND_PRINT_VERIFICATION_ROOT` to a fresh directory under `.tmp` to retain the
test-generated PDFs; each backend used a different directory. Raw logs:
`.tmp/form1-print-dependent-sqlite.log`, `.tmp/form1-print-dependent-native.log`.
**PASS:** eleven exact cases on SQLite / **277.890s** and native MySQL /
**293.580s**, zero skips, actual exit 0 and both test stores destroyed. Both
processes are terminal. `.tmp/verify_form1_print_final.py` verified matching exact
case identities, frozen source, original/repaired artifacts and all page-image
hashes, and unchanged operator database hashes. Final proof:
`.tmp/form1-print-local-acceptance-20261016.json`. Owned MySQL fixture shutdown
requested after the native process returned exit 0; final port-33308 closed check
PASS. Django system check and diff
check PASS. Suite durations exclude migration/setup and are not delivery estimates.

**NOT RUN — OUT OF SCOPE:** full new project/remote CI and Version Manager
publication; no new release/push is authorized by the latest retained handoff.
Accepted v172 primary [38618885804](https://github.com/tepong32/grand/actions/runs/38618885804)
proves its own earlier source only, not this changed renderer. Required release
gates remain applicable before any future publication.

**NOT RUN — OUT OF SCOPE:** new browser file-save, printer, physical signature,
statutory/LGU output acceptance and deployed operational checks. The existing
native browser file-save limitation is neither retested nor declared resolved.
Full supported-source/volume and local formatting acceptance are still required.

GO for the demonstrated local presentation repair, artifact comparison and
eleven-case dependent validation on both backends. Numerical overlap recipes, actual
designations/signatures/issuance, local earmark semantics and other foundation
requirements remain open. Continue the [finite original task list](FINANCE_REMAINING_WORK_2026-10-14.md);
do not describe this output refinement as full Form 1 or Finance completion.
