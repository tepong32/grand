# Form 1 designation preparation and independent review

Local development, 2026-10-16, branch `codex/finance-form1-print-evidence`, base
accepted v0.7.172 / `32ab046`. Uncommitted/unpublished. This is the first functional
part of the [known final Form 1 lifecycle](FINANCE_FORM1_FIELDS_2026-10-16.md#next-functional-milestone),
within FG-03/06, not a generic signature system. **Production NO-GO.**

## Scope and controls

`budget/form1_signing.py` retains an immutable preparation over the exact complete,
internally reviewed original package. It records the intended form date, explicit
original-source LGU, designated officer/position and authority dates/reference for
the Local Treasurer, Local Budget Officer, Local Planning and Development
Coordinator, Local Accountant and separate Local Chief Executive. Each function
retains original PDF/PNG/JPEG designation evidence, its name, length and SHA-256.
Typed names and attachments are claims requiring independent review, not signatures.

The independent Budget reviewer must differ from both preparation makers. All
four source/designation checks require explicit findings and evidence bases;
approval requires all verified, latest preparation and current complete sources.
Returns preserve originals and permit a successor. Later source changes never
rewrite an earlier review or confer continued currentness. Historical reads
verify original evidence rather than requiring that it still be the latest.

The new preparation, role evidence and one-time review tables route to Finance;
actor and department IDs remain scalar across stores. Migration `budget/0024`
creates empty tables with unconditional version/role uniqueness and a one-to-one
decision constraint. No retained financial history is rewritten. The owning lock
order is BudgetVersion → Fund → original package → preparation. Source-update
and competing actions use these same owners. No journal or cash capacity is created.

Explicit preparation/review/view/export grants remain separate. Original package
and original-source authority is rechecked for every read/export. UAT membership
denies mutation even with added grants. Accounting/Treasury viewers cannot prepare
or decide a Budget-owned preparation. Four opt-in role presets describe these
permissions without assigning them to operator users or claiming statutory office.

Clerks reach preparation history from the original whole-package detail, enter
the five designation functions, inspect original documents and independently
review/return. CSRF and POST-only review apply. Original document downloads require
separate export authority, retain archive/audit evidence and use attachment/no-store/
nosniff responses. No signing-copy or final-issued action is offered.

Every certification, Chief Executive approval, unsigned-copy issuance, final
issuance and cash-availability flag remains false. Final signing-copy generation,
physical signed-copy receipt, independent verification and immutable final issuance
are **still missing**. Actual appointments/signatures and local acceptance are
unknown/manual; they are not manufactured by synthetic tests or web role presets.

## Validation record

The first local suite failed during setup because a new `decide` helper overrode
the inherited native-actuals decision helper: five errors / 5.718s. After renaming
it, SQLite still failed five cases / 150.386s and native failed six / 197.046s:
the inherited factory already owns a `documents` dictionary. The upload helper
is now `designation_documents`; signing review uses `decide_signing`. Both were
**FAIL — CAUSED BY CURRENT WORK**, not evidence against the accepted v172 source
and not successful behavioral coverage. Logs are preserved:
`.tmp/form1-signing-focused-sqlite.log`,
`.tmp/form1-signing-focused-sqlite-r2.log`,
`.tmp/form1-signing-focused-native.log`. Both failed native stores were destroyed;
no native run was started over a still-live predecessor.

The next focused SQLite run PASS: five signing cases plus one native-only skip,
221.949s, actual exit 0, both aliases destroyed
(`.tmp/form1-signing-web-sqlite.log`). It precedes the final presentation changes.
Native then found a further test cleanup defect: six cases / 244.499s, two errors,
exit 1 (`.tmp/form1-signing-web-native.log`). The fully consumed test-client
stream already closes its response with Django's connection-signal guard;
explicitly closing it again fires unguarded request-finished cleanup inside the
MySQL TestCase transaction. The next login and next setup consequently failed.
The duplicate close is removed; byte/hash assertions remain. Native source shows
this guard in Django's `closing_iterator_wrapper`; the passing reruns below prove the repair.
The race case completed, but the failed suite is not a pass. Both stores destroyed.

Browser inspection reproduced a new LOW entry-layout defect: at 390px, the five
unstyled file inputs extended the document to 408px. Bootstrap field classes
now constrain the widgets; final reproduction passes below. Explicit role ordering,
readable status labels and expandable verification details also replace native
JSON order/raw status codes without changing retained payloads or permissions.
Before-image: `output/playwright/form1-designation-entry-mobile-before-20261016.png`.
The history screen had no horizontal overflow; static preview missing fonts/default
images were copied from the existing runtime/source, with no application change.

Current source freeze: `.tmp/form1-signing-final-source-freeze-20261016.json`.
The earlier `form1-signing-web-source-freeze-20261016.json` predates these UI/test
corrections. Final validation is recorded below; use actual terminal logs rather than
assuming a historical running suite passed. Relevant suite labels:

```powershell
& 'C:/Users/Administrator/Desktop/GH/grand/.venv/Scripts/python.exe' -B -X utf8 .tmp/intake_primary_sqlite.py budget.test_form1_signing budget.test_form1_signing_concurrency --verbosity 2
& 'C:/Users/Administrator/Desktop/GH/grand/.venv/Scripts/python.exe' -B -X utf8 .tmp/form1_signing_preview_native.py budget.test_form1_signing budget.test_form1_signing_concurrency --verbosity 2
```

The latter delegates to the existing fresh two-store native runner and captures
synthetic HTML from real Django responses for separate browser layout inspection.
It does not replace native execution or exercise operator databases. Native races
cover competing preparations, competing decisions, preparation successors during
review and source forecast successors during review, retaining original history.
SQLite skips this native race; a skip is never counted as a pass.

Django system and migration-drift checks PASS during implementation. Terminal
results (each actual exit 0, zero skips, both aliases destroyed):

| Scope | Result | Suite time / log |
| --- | --- | --- |
| SQLite signing + original package/review/export/print + two voucher role cases + CI runner regressions | 29/29 PASS | 833.003s; `.tmp/form1-designations-dependent-sqlite.log` |
| Final-source SQLite clerk flow + five original package HTTP cases | 6/6 PASS | 320.061s; `.tmp/form1-designations-final-http-sqlite.log` |
| Native signing, four races within one case, five original package HTTP cases, two voucher role cases and nine CI runner cases | 22/22 PASS | 589.144s; `.tmp/form1-designations-final-native.log` |
| Added pending-reviewer GET screen and ordinary clerk flow, SQLite | 1/1 PASS | 66.492s; `.tmp/form1-designations-review-screen-sqlite.log` |
| Same added GET-screen assertion and clerk flow, native | 1/1 PASS | 57.343s; `.tmp/form1-designations-review-screen-native.log` |

Counts overlap; do not sum them as distinct project coverage. The later GET
assertion extends the existing clerk case; its source freeze is
`.tmp/form1-signing-review-screen-source-freeze-20261016.json`. Application source
is unchanged since the final-source freeze. The early 29-case run began before
the final presentation iteration; the six-case HTTP and subsequent screen probes
cover those changes. Native verifies the persistence and competing-action boundary;
SQLite alone would not prove it.

Actual complete discovery now finds **2,553 identities**, exactly six additions.
All eight existing CI partitions cover those identities once with whole classes;
proof `.tmp/form1-designations-discovery-20261016.json`. This is discovery only,
not execution or hosted runtime acceptance. Full post-change project/remote CI,
dependency audit and release review are NOT RUN for this unpublished checkpoint;
required release gates remain. No checks, assertions, skip rules, partition code
or timeouts were weakened/disabled. Accepted remote v172's 19 green jobs do not
cover this local source. No new VM release, integration, push, operator
migration/grant or deployment occurred.

Browser reproduction of the corrected actual entry and independent-review pages
now gives document width **390 at viewport 390**, with no overflowing controls.
All four independent findings are visible. Final entry, pending-review and
reviewed captures at **390px and 1440px** all have matching document/viewport
widths, no overflowing controls and the official role order. All six final images
were inspected: `output/playwright/form1-designation-*-final-20261016.png`.
Raw HTML: `.tmp/form1-signing-preview-20261016`; browser log:
`.tmp/form1-designations-browser-final.log`. Combined proof:
`.tmp/form1-designations-local-acceptance-20261016.json`, generated by
`.tmp/verify_form1_designations_final.py`, validates exact case identities,
zero skips, source hashes, both-store cleanup, discovery coverage, artifact hashes
and unchanged operator database hashes. All runners are terminal; owned MySQL,
static preview and Playwright are stopped. Ports 33308/8769 are closed. Final
Django system/migration-drift/diff checks PASS.
These static synthetic view captures establish layout only; HTTP tests establish
service calls, permissions, downloads, CSRF and mutation behavior. Neither supplies
physical signatures, printer acceptance or LGU acceptance.

## Required checkpoint report

| Item | Actual state |
| --- | --- |
| A. Already implemented | Whole source assembly, immutable retention, three-office internal review and draft exports. |
| B. Repaired | New helper collisions, native test-response cleanup and mobile file-control overflow; passing reruns retained. Earlier print/LGU repairs retain separate evidence. |
| C. Newly implemented | Locally validated named designation preparation, retained role evidence, independent review/return, source-scoped clerk screens and download controls. |
| D. Missing | Unsigned signing-copy release, actual signed-copy receipt/verification, final immutable issuance and governed successors. |
| E. Out of scope | Generic signing framework, accounts for physical signatories, unpurchased modules and unrelated UI redesign. |
| F. Unknown | Actual local appointments, signatures, accepted local form/printer behavior, unresolved numerical/earmark authority. |
| G. Workflow connection | Reuses Budget's complete package and Accounting/Treasury original-source visibility; creates no ledger posting or payment authorization. |
| H. Friction | One source-linked entry/history/review path; no recopying financial amounts or guessing Planning/Chief Executive authority from other roles. |
| I. Controls | Separate stores, owning locks, independent maker/checker, explicit original-source access/export, UAT denial, immutable evidence and audit trail. |
| J. Remaining parity | Final lifecycle above, evidenced numerical treatments, required office outputs and remaining ordinary/operational/LGU acceptance. |
| K. Next checkpoint | Actual immutable unsigned signing-copy release over complete reviewed sources and approved designations, followed by signed-copy verification and final issuance. |

Severity: **MEDIUM resolved** local test/release validation defects; **LOW resolved**
mobile entry overflow; **HIGH OPEN** final certification/approval/issued-copy
functional completion gap. No claim that all project defects were audited here.

**GO:** this validated local prerequisite and next bounded development.
**NO-GO:** release without required review/CI, claiming actual statutory approval,
final Finance completion or deployment readiness. See [continuation](../CONTINUE.md) and
[remaining work](FINANCE_REMAINING_WORK_2026-10-14.md).
