# Whole Form 1 unsigned signing-copy release

Local development, 2026-10-16, verified through 2026-10-17 (Asia/Singapore), branch `codex/finance-form1-print-evidence`, base
accepted v172 / `32ab046`. Extends the [validated designation prerequisite](FINANCE_FORM1_DESIGNATIONS_IN_PROGRESS.md)
within FG-03/06. Uncommitted/unpublished; **production NO-GO**.

## Required behavior and actual implementation

The retained official DBM LBM 94 Annex D, pages 20–22, was inspected again.
Its five financial columns, account itemization, receipt hierarchy, SPA detail,
four certifying functions and separate Chief Executive approval guide this copy.
The [official source and SHA-256](FINANCE_FORM1_FIELDS_2026-10-16.md) remain retained.
No new national/local numerical rule or actual signing authority is inferred.

New `Form1UnsignedCopy` / migration `budget/0025` retain one original PDF per
designation preparation, the complete source/decision envelope, content and
envelope checksums, independent release actor and timestamp. All fields and bytes
are immutable through model/service actions. Reprints return the original bytes,
including after source changes or renderer updates. Source authorization and
integrity still apply to historical access; current heads do not replace history.

`form1_unsigned_copies.release` uses BudgetVersion → Fund → package → preparation
locks and unconditional one-to-one uniqueness. Require the latest independently
approved preparation and current complete original sources. The releaser must
differ from both makers; the preparation reviewer may release with the separate
grant. Original view/export authority is mandatory. UAT denies release even with
grants. Accounting/Treasury viewers cannot release a Budget-owned copy. No third
approval actor is invented, and no operator permissions are assigned here.

The complete signing PDF uses a separate renderer. It retains original beginning
net cash, receipts/accounts/subtotals, expenditures/accounts/SPA subdivisions,
ending balance, explicit PhilHealth deduction and net ending across all five
columns. Unknown controls cannot print as zero. Each entity has its own scope
and signing page, all pages carry the copy identity and continuous numbering.
Signatures and actual certification/approval dates remain blank. Source/category/
account/subdivision controls are identified as the same money, not added twice.

Only `unsigned_copy_issued` becomes true in the new copy envelope. Original
preparation/source snapshots remain unchanged; statutory certification, Chief
Executive approval, final `form_issued` and cash authority stay false. No journal,
physical handover, signature, acknowledgement or final issuance is fabricated.

Clerks release from the existing designation detail and download the original
unsigned PDF. POST/CSRF, source-scoped read/export, archive/audit evidence and
attachment/no-store/nosniff responses apply. A separate opt-in copy releaser role
does not confer preparation/review or general Budget editing. Existing designation
roles gain source-scoped copy viewing/export presets, with no automatic operator
assignment. The detail view reuses only pure evidence validation within its outer
operation; actual permissions, models and currentness are never cached.

The old draft renderer/export remain available. Their original evidence assembly
is extracted into private `form1_package_exports._retained`, called only after
actual original-source authorization. The original export endpoint keeps its
export checks and owning locks. The new copy verifies that its retained original
evidence matches this projection; no unauthenticated source route was added.

## Validation in progress

First SQLite one-case probe: **FAIL — CAUSED BY CURRENT WORK**, 45.951s,
exit 1, both stores destroyed; `.tmp/form1-unsigned-first-sqlite.log`.
The generated five-page PDF included the complete Planning Coordinator name,
wrapped across two lines. The new verifier incorrectly required a contiguous
extracted line. It now normalizes extraction whitespace while retaining the full
name/role, page, financial row and code checks. This did not establish a missing
name in the application; visual inspection is still required.

Current focused SQLite command:

```powershell
& 'C:/Users/Administrator/Desktop/GH/grand/.venv/Scripts/python.exe' -B -X utf8 .tmp/form1_unsigned_probe.py sqlite budget.test_form1_unsigned_copies budget.test_form1_unsigned_concurrency --verbosity 2
```

Focused result: **FAIL — CAUSED BY LOCAL WORK**, four discovered / two direct
passes / one direct error / one native-only skip, 149.144s, exit 1, both stores
destroyed; `.tmp/form1-unsigned-focused-sqlite.log`. The minimal Budget designation
preset lacked `budget.view_budget_audit`, the existing read-only bridge used by
`accounting.budget_cash.visible` for Budget-owned adopted historical cash. Broader
fixture grants had hidden that gap in the previous checkpoint. Both Budget
designation presets and the new copy releaser now include that existing read
permission; no proposal editing or source-visibility bypass was added.

The probe captures synthetic PDFs/envelopes and actual clerk HTML under
`.tmp/form1-unsigned-preview-20261016/sqlite` without consuming/closing the tested
response twice. The later native probe uses the same wrapper with `native`.

New tests cover ordinary release/download, minimal role presets, exact original
sources and flags, deterministic zero-query PDF reproduction, retained original
bytes after source/renderer changes, source/view/export revocation, corruption,
pending/stale/superseded sources, maker/UAT/foreign-office denial and immutability.
Native races cover duplicate release, a designation successor during release and
a source forecast successor during release, preserving earlier bytes. Final
broader suites completed with the same single fixture error: SQLite 21 discovered,
20 passed / one error / zero skips, 504.305s; native 22 discovered, 21 passed /
one error / zero skips, 617.825s. Both exit 1, both aliases destroyed; logs
`.tmp/form1-unsigned-final-{sqlite,native}.log`. The now-minimal designation maker
correctly lacked unrelated forecast-preparation permission when the stale-source
test tried to create a forecast successor. The test now explicitly asserts that
denial, grants the separate source-changing action only in the fixture, and then
checks that the signing copy refuses the stale source. Production permissions and
all assertions are unchanged/strengthened. **These broader runs are not passes.**

Only that test body changed afterward; all application source matches
`.tmp/form1-unsigned-final-source-freeze-20261016.json`. Extended freeze:
`.tmp/form1-unsigned-fixture-fix-source-freeze-20261016.json`. Clean reruns of the
affected module **PASS: SQLite 3/3 / 175.490s; native 4/4 / 238.186s**, zero skips,
actual exits 0 and both aliases destroyed. Logs
`.tmp/form1-unsigned-fixture-final-{sqlite,native}.log`. The latter includes all
three release races. Proportional scope: untouched legacy cases already passed;
the repair changes only this isolated fixture's source permission setup, not the
application. A full post-change/remote release gate remains separate and NOT RUN.
The final layout repeats original Fund/entity scope on continued financial tables.
No gate or assertion was disabled to obtain a pass.

Independent `pdfplumber` grid extraction of the first actual captured sample
matches **51 financial rows × five columns = 255 cells**, as a complete labelled
row multiset against the retained source envelope, including account codes,
subtotal multiplicity and SPA controls. No totals are inferred by summing nested
control rows. The verifier uses `pypdf` text-object order for names because line
order interleaves the four signature columns; the initial extraction failure is
retained in `.tmp/form1-unsigned-table-first.log`. This tool-only correction does
not weaken the financial-cell comparison. Baseline proof is beside the captured
PDF as `.table-proof.json`. Final native output also passes the exact **255-cell**
comparison and all five rendered pages were inspected: no clipped/missing amounts,
names, codes or glyphs observed; all physical signing dates remain blank. Raw
native copy `9e403f1c-d53f-4cfa-b412-475c98db3f21.pdf` and its source/proof are in
`.tmp/form1-unsigned-preview-20261016/native`; page images are under
`.tmp/form1-unsigned-pdf-final-20261016`. Poppler emits the same environment
Symbol/ArialUnicode display-font warnings seen in earlier drafts; the retained
Noto text renders correctly and field extraction matches. Actual release/released
HTML was inspected at 390/1440px, with no overflow and the correct release-button/
download-link transition. Four captures: `output/playwright/form1-unsigned-*-20261016.png`;
raw DOM observations `.tmp/form1-unsigned-browser-final.log`.
Bundled PDF analysis tools are used without changing application dependencies or
the Python 3.11 runtime.

Combined verification PASS: `.tmp/form1-unsigned-local-acceptance-20261016.json`,
produced by `.tmp/verify_form1_unsigned_final.py`. It preserves failed broader
statuses, confirms the failed identity is covered by clean repaired runs, verifies
unchanged application source after the fixture-only repair, source/output/image
hashes, exact table cells, layout state transitions and unchanged operator database
hashes. It does not mislabel those earlier 21/22-case runs as green or full CI.
The broader selections were not rerun after this isolated test-only fix; all their
unchanged cases passed and every selected identity now has passing local evidence.

Final synthetic sample:
[unsigned signing copy](../output/pdf/form1-synthetic-unsigned-signing-copy-20261016.pdf).
This is the exact native retained/downloaded PDF, not a later rerender. SHA-256:
`dc6cdb81152066425f28b319a4516ed8e6520c5d082ccec4d6fb89aaae2d0bc5`.
All five pages and four clerk-layout images are inspected. Django system,
migration-drift and diff checks PASS. All runners are terminal; owned MySQL,
static preview and Playwright are stopped; ports 33308/8770 closed. No operator
database, grants or production migrations changed.

Full discovery now has **2,557 identities**, exactly four added by this checkpoint;
all previous 2,553 identities remain and eight shards cover each once by whole
class. `.tmp/form1-unsigned-discovery-20261016.json` is discovery evidence only,
not a 2,557-case pass or hosted runtime acceptance. Full post-change/remote CI and
release review remain NOT RUN for the unpublished work. Published v172 remains
the separately accepted master/tag; no new VM commit, integration or push occurred.

Severity: **MEDIUM resolved** Budget source-read preset defect introduced in
local work; **LOW resolved** verifier/fixture defects. **HIGH OPEN** actual
signed-copy verification and final-issuance software gap. No whole-project
security audit or deployment readiness is inferred from these scoped passes.

## Required checkpoint report

| Item | Actual state |
| --- | --- |
| A. Already implemented | Reviewed whole financial package, original source/export controls and named designation preparation/review. |
| B. Repaired | Minimal Budget designation roles lacked the existing historical-cash read bridge; text/fixture checks mishandled wrapping and unrelated source creation. |
| C. Newly implemented | Independent immutable unsigned-copy release/download, complete source-linked five-column PDF and clerk release/released state. |
| D. Missing | Actual signed-copy receipt, independent verification, final immutable issued evidence and governed successors. |
| E. Out of scope | Generic digital-signature/collaboration framework, new accounts for paper signatories and unpurchased modules. |
| F. Unknown | Actual appointments, signatures, accepted printer/local form behavior and unresolved earmark/numerical rules. |
| G. Workflow connection | Budget releases a source-derived signing copy; Accounting/Treasury retain scoped source/copy visibility. No new journal, payment or cash authority. |
| H. Friction | Release/download from the existing reviewed designation page, with original bytes reused for reprints and no financial re-entry. |
| I. Controls | Separate stores, source/actor/version pins, owning locks, independent release, UAT/maker/foreign-office denial, immutable originals and audited export. |
| J. Remaining parity | Signed/final lifecycle, other required outputs/ordinary scenarios and operational/LGU acceptance from the original gate. |
| K. Next checkpoint | Source-bound actual signed-copy receipt and independent verification, followed by immutable final issuance; preserve the original unsigned bytes. |

## Completion limits and next work

Unsigned-copy release is only one step of the final lifecycle. Actual signed-copy
receipt, independent verification, final immutable issued output and governed
successors remain missing. Actual appointments, physical signatures, printer and
LGU acceptance remain manual/unknown. Unsupported numerical treatments, earmark
semantics and the other original Finance gates remain open.

**GO:** validated local unsigned-copy checkpoint and next bounded development. **NO-GO:** publication without
required review/CI, claims of statutory approval or final Finance/production
completion. [CONTINUE.md](../CONTINUE.md) owns immediate handles and next actions.
