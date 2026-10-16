# Form 1 signed-return verification and final issue — local work

Started 2026-10-17, following the validated local
[unsigned-copy checkpoint](FINANCE_FORM1_UNSIGNED_COPIES_IN_PROGRESS.md).
The original Finance gate remains open; [CONTINUE.md](../CONTINUE.md) owns current
test handles, actual results and publication status. This is an implementation
checkpoint, not evidence of actual LGU appointments, handwriting or acceptance.

## Local release review follow-up — 2026-10-17

The bounded local review is complete for the 19 intended production Python files,
three migrations and six templates. Seventeen production hashes exactly match the
retained prior review; reversing the single later role-action sentence reproduces
the eighteenth prior reviewed file's exact bytes. The remaining form delta is four
label lines. Migrations retain Finance-local protected relations and unconditional
version/one-to-one identities; no default/Finance merge or conditional uniqueness
assumption was added. POST/CSRF, escaped template output, permission-guarded actions
and the six existing changed button assertions were inspected. Ten test-file hashes
are retained as execution evidence, not a claim of every assertion being reviewed
line by line. All 36 intended synthetic PNG/PDF artifacts match their intent hashes.

**LOW, introduced in unpublished local work:** designation history still said
signing-copy delivery/acceptance were unfinished after those routes were added.
One unconditional paragraph now directs staff to open a retained preparation for
unsigned-copy release, signed returns and final issuance. It retains the warning
that designation evidence itself supplies no signature, approval, issued copy or
cash authority. No model, query, permission, validation or state transition changed.
No additional code defect was confirmed within this review's scope.

PASS: existing actual HTTP/source-isolation case
`budget.test_form1_signing.Form1SigningTests.test_retains_exact_roles_documents_review_and_finance_isolation_without_issuance`,
Python 3.11 `-B -X utf8 .tmp/intake_primary_sqlite.py --verbosity 2 <that label>`;
session **73025**, 1/1, zero skips, 49.591s, exit 0, both aliases destroyed.
Log `.tmp/form1-release-review-history-sqlite-20261017.log`.
No native/full/browser rerun for this one unconditional sentence: persistence,
auth, financial behavior and layout rules are unchanged. The earlier full baseline,
later prior-payable 8/8 per backend and this separate HTTP case retain their own
source chronology; do not combine them into a fictitious current full run.

Proof `.tmp/finance-release-code-review-20261017.json` pins exact reviewed hashes,
scope/limits, the corrected finding, test log and unchanged operator stores.
Current source `.tmp/finance-release-review-current-source-freeze-20261017.json`
differs from the broad full baseline in five presentation/test files: the four
prior-payable wording files plus this history template. No new test method.
This is local review, not independent PR/human approval, a pentest, hosted CI or
LGU acceptance. Candidate CI/actual publication remain pending under CONTINUE.md;
production and whole Finance completion remain NO-GO.

## Predecessor row and archive binding repair — 2026-10-17

**Combined full-regression checkpoint, 05:22 Asia/Singapore: PASS on both backends.**
Native MySQL 8.4.11 session 62511 exited 0: **all 2,572 passed / zero skips**,
8,533.055s. Command: Python 3.11 `-B -X utf8 .tmp/intake_primary_native.py --verbosity 2`.
Together with SQLite below, each full run matches all 2,572 discovery identities
exactly once, cleaned both test aliases and retains unchanged 1,193 frozen source
hashes and operator database hashes. Native evidence:
`.tmp/finance-full-identity-repair-native-evidence-20261017.json`; raw log
`.tmp/finance-full-identity-repair-native-20261017.log`, SHA-256
`9a7eafc8f20fbaaa79cccec108e74d4b42328bc869ca4d03db8a388ca8feb86d`.
Both full sessions are terminal; owned MySQL is stopped and ports 33308/8771 were
checked closed. Do not restart passed suites without a relevant change/failure.
No new runtime finding arose. **GO for continued local foundation development;
NO-GO for release/production** pending independent review, current-tree hosted CI,
publication and the original functional/operational/LGU gates. No new release or
Finance-completion claim; earlier partial-run observations are historical.

**Full SQLite follow-up, 04:43 Asia/Singapore:** terminal session 48251 PASS,
exit 0; 2,572 discovered, **2,370 passed / 202 native-only skips**, 6,227.809s.
Command: Python 3.11 `-B -X utf8 .tmp/intake_primary_sqlite.py --verbosity 2`.
All 2,572 unique identities exactly match discovery; both aliases were destroyed.
All 1,193 frozen source hashes and both operator database hashes match. Raw log:
`.tmp/finance-full-identity-repair-sqlite-20261017.log`; verified proof:
`.tmp/finance-full-identity-repair-sqlite-evidence-20261017.json`.
Native full session 62511 subsequently passed all 2,572 with zero skips above;
the earlier SQLite skips alone were not native execution.
No current-tree hosted CI, independent release review, publication or LGU/form
acceptance is established. The frozen-source two-backend run is now complete.

**MEDIUM, introduced in unpublished local work; repaired and focused validation PASS.**
The helper checked the predecessor's family, payload checksum and archive checksum,
but did not bind its advertised row public ID/version or payload to the original
issued envelope. A read-only probe against retained genuine synthetic issue bytes
confirmed changed row identity/version was accepted. This is conditional on DB
corruption/out-of-band writes; normal model saves prohibit it, and the feature is
not published v172 behavior. Do not claim a normal-UI exploit or production incident.

`budget/form1_signed_copies.py` now binds public ID/version/family to the retained
payload and reads exactly one bounded, unencrypted original `issuance.json` member,
requiring its size/bytes to match the canonical issuance envelope. It performs no
recursive source/history traversal, metadata rewrite, new posting, permission or
schema change. The two test files add row-identity/version and equal-length rehashed
payload regressions plus a genuine successor-operation test. The latter requires
controlled rejection, no extra receipt/review/issue/journal, and original-byte
reproduction after the disposable row is restored.

| Scope / chronology | Actual result | Seconds / `.tmp/` log |
| --- | --- | --- |
| Before production fix, six pure methods | FAIL — CAUSED BY CURRENT WORK: three assertion failures; exit 1 | 0.005; `form1-predecessor-identity-baseline-20261017.log` |
| Initial fixed pure tests, before equal-length assertion refinement | PASS 6/6, no databases | 0.005; `form1-predecessor-identity-pure-fixed-20261017.log` |
| Final six pure + new corrupt-row operation + existing successor/atomic-issue operation, SQLite | PASS 8/8, zero skips, exit 0, both aliases destroyed | 274.681; `form1-predecessor-identity-fixed-sqlite-20261017.log` |
| Same final scope, MySQL 8.4.11 | PASS 8/8, zero skips, exit 0, both aliases destroyed | 280.546; `form1-predecessor-identity-fixed-native-20261017.log` |

Use the existing Python 3.11/isolated backend wrappers with `--verbosity 2` and:

```text
budget.test_form1_signed_copies.Form1SignedCopyTests.test_corrupt_predecessor_row_cannot_seed_a_successor
budget.test_form1_signed_copies.Form1SignedCopyTests.test_successor_scan_issuance_lineage_and_atomic_combined_action
budget.test_form1_signed_validation
```

Proof `.tmp/form1-predecessor-identity-evidence-20261017.json` verifies exact IDs,
logs/source hashes, precisely three changed application/test files and both
unchanged operator stores. Original-artifact probes before/after are
`.tmp/form1-predecessor-identity-probe-{before,after}-20261017.json`; the latter
accepts the retained prior-checkpoint archive and rejects all three contradictions,
without database access. Local read-only review of entry points, grants, maker/UAT
checks, immutable lineage/locks, PDF escaping and original downloads is retained in
`.tmp/form1-local-source-review-20261017.json`. No other finding was confirmed in
that bounded scope; this is not an independent PR review or comprehensive pentest.

The previous full baseline (2,569 discovered each) was deliberately interrupted
for this real finding, not elapsed observation. Sessions 20024/38719 exited -1,
without terminal suite/cleanup summaries. Preserve partial logs and original freeze
as **INTERRUPTED / NOT PASS**. Their fixed native schemas were recreated by the
fresh focused runner and then destroyed. No test, assertion or timeout was removed,
weakened, skipped or increased to get green. New full source/log identities retain
the repaired baseline; current handles and actual state belong to CONTINUE.md.
Discovery/partition PASS: **2,572** distinct identities, exactly once across eight
workers. It does not prove full execution or hosted timing acceptance.

| Checkpoint item | Evidence / remaining limit |
| --- | --- |
| A. Already implemented | Local designation, unsigned-copy and signed/final clerk lifecycle. |
| B. Repaired | Predecessor advertised identity/payload now binds to original issuance bytes. |
| C. New | Three regression methods; no new Finance feature, schema or grant. |
| D. Partial | Full repaired-source regression, release/hosted CI and original foundation gates. |
| E. Out of scope | New modules/frameworks and unsupported financial recipes. |
| F. Unknown | Earmark basis, applicable numerical recipe and actual local paper/form acceptance. |
| G. Connection | Successor correction stays pinned to the exact original issued predecessor. |
| H. Friction | Valid existing archives remain usable; no new clerk step. |
| I. Controls | Same independent authority, source/export grants and parent locks; failed action rolls back. |
| J. Parity | Original numerical, certificate, output, ordinary-office and operational/LGU gates remain open. |
| K. Next | Complete the new full fresh two-backend runs before any release claim. |

**GO for this focused local repair; NO-GO for unvalidated publication, full Finance
completion or production.** No commit, integration or push. The older combined
lifecycle evidence below predates this repair; do not relabel it current coverage.

## Combined current-tree lifecycle validation — 2026-10-17

The complete local designation → unsigned copy → signed return/final issue suites
now pass together, covering their shared fixtures/services and consecutive native
transaction-test cleanup. No application, test, schema or dependency edit was
needed. This replaces the earlier separated-source limitation for these eight
modules; it is not full-project execution or official/LGU acceptance.

Commands use Python 3.11 at
`C:/Users/Administrator/Desktop/GH/grand/.venv/Scripts/python.exe`, `-B -X utf8`,
then `.tmp/intake_primary_sqlite.py` or `.tmp/intake_primary_native.py`, these labels
and `--verbosity 2`:

```text
budget.test_form1_signing budget.test_form1_unsigned_copies
budget.test_form1_signed_copies budget.test_form1_signed_views
budget.test_form1_signed_validation budget.test_form1_signing_concurrency
budget.test_form1_unsigned_concurrency budget.test_form1_signed_concurrency
```

| Fresh two-store run | Actual result | Suite seconds / log under `.tmp/` |
| --- | --- | --- |
| SQLite, session 91281 terminal | PASS: 22 selected, 19 passed, three native-only skips; exit 0 | 1,518.685; `form1-lifecycle-combined-sqlite-20261017.log` |
| MySQL 8.4.11, session 32351 terminal | PASS: all 22, zero skips; exit 0; thirteen paired race scenarios in three methods | 1,952.135; `form1-lifecycle-combined-native-20261017.log` |

Both aliases were destroyed in both runs. Durations exclude fresh setup and are
observed suite times, not implementation-hour estimates. The backends ran in
separate processes/stores with overlapping wall time; only one native suite ran.
The combined evidence JSON verifies exact identities, unchanged 1,193 source
hashes and both unchanged operator stores. Files:
`.tmp/form1-lifecycle-{source-freeze,combined-evidence}-20261017.json`.
Owned MySQL is stopped; 33308/8771 are closed. Earlier browser layouts remain
separate evidence; no new visual or physical-acceptance claim.

Local equivalents of the workflow security commands also PASS: Django check,
migration drift, nine CI-runner unit tests (0.012s), five Telegram tests (0.564s),
`pip check`, and `pip_audit -r requirements.txt` (no known vulnerabilities).
All 51 production pins match installed metadata and imported Django is 5.2.18.
Retained logs are `.tmp/form1-lifecycle-{ci-runner-unit,telegram,pip-check,pip-audit}-20261017.log`;
versions are in `.tmp/form1-lifecycle-runtime-pins-20261017.json`.
The audit's Windows short-path/long-path virtual-environment warning was nonfatal;
no package was installed into the application runtime or requirement changed.
Full current discovery/partition also PASS: 2,569 distinct tests assigned exactly
once to eight workers (`.tmp/form1-lifecycle-discovery-20261017.json`). No full
execution, successful worker coverage or hosted timing is inferred from discovery.

| Required checkpoint item | Current evidence / limit |
| --- | --- |
| A. Already implemented | All three local signing stages, original downloads, opt-in roles and correction lineage. |
| B. Repaired | Stale FG-03/06 descriptions now distinguish implemented software from actual signatures/acceptance; no additional application defect found in this scope. |
| C. Newly implemented | No new application feature; combined current-source validation and official COA scope evidence. |
| D. Missing/partial | Full current-tree regression/release review/hosted CI, supported numerical treatment and remaining original foundation/acceptance gates. |
| E. Out of scope | New modules, generic frameworks and unrelated workflow breadth. |
| F. Unknown | Local earmark semantics, actual appointments/signatures/forms and applicable municipal offset recipe. |
| G. Workflow connection | Retained Budget sources → reviewed designation → unsigned copy → declared return → independent verification → immutable final archive/successor. |
| H. Friction | Existing no-rekeying, exact reprints and honest unknown-date capture are validated; no new UI change. |
| I. Controls | Separate stores, original-source permissions, maker/UAT/office denial, immutable original bytes, currentness and owning locks. |
| J. Remaining parity | Numerical/certificate/required-output/ordinary-office coverage plus operational, restore, printer and LGU acceptance remain open. |
| K. Next checkpoint | Full current-tree automated regression, preserving local-only publication boundary and deferred manual interventions. |

Severity: no new application defect established by this scope. The unresolved
numerical route remains unsupported; the [official COA source inspection](FINANCE_FORM1_PHILHEALTH_SOURCE_AUDIT.md#official-coa-lead-resolved-by-scope-inspection--2026-10-17)
does not authorize a municipal adjustment. **GO for this local combined checkpoint
and further bounded work; NO-GO for unvalidated publication, full Finance completion
or production.** No VM commit/tag, integration or push occurred.

## Clerk delivery extension — locally validated, unpublished

Local forms/controllers/templates now connect receipt/history, independent
verification/return, combined or separate issuance and original PDF/ZIP download
through the existing services. Downloads archive/audit their original bytes and
return attachment/no-store/nosniff responses. New opt-in presets separate Budget
recorder, Budget verifier/issuer and Accounting/Treasury final viewers; no operator
grants. A source-authorized common-parent history operation re-fetches and verifies
actual rows without caching permissions or trusting submitted model attributes.
Three HTTP cases verify actual minimal-role capture, incomplete return, separate
and combined verification/issuance, predecessor-required scan corrections, exact
audited downloads, both Accounting/Treasury viewers, foreign-office operational
grants, UAT denial, source-export revocation and corruption refusal. Earlier
service evidence below remains a distinct tested source; this section owns
current clerk delivery.

| Scope | Actual result | Seconds / `.tmp/` log |
| --- | --- | --- |
| Initial SQLite clerk cases | PASS 3/3, zero skips, exit 0 | 486.847; `form1-signed-ui-first-sqlite-20261017.log` |
| Extended viewer case + original designation/unsigned HTTP, role-config UAT consumer, four pure validators; SQLite | PASS 8/8, zero skips, exit 0 | 357.533; `form1-signed-ui-final-sqlite-20261017.log` |
| All three clerk cases + same dependents/validators; native | PASS 10/10, zero skips, exit 0 | 753.567; `form1-signed-ui-native-20261017.log` |
| Final source-context ordinary clerk flow; SQLite | PASS 1/1, zero skips, exit 0 | 165.791; `form1-signed-ui-context-sqlite-20261017.log` |
| Same final-source flow; native | PASS 1/1, zero skips, exit 0 | 188.480; `form1-signed-ui-context-native-20261017.log` |

All five runs destroyed both aliases. Scopes overlap. The initial SQLite viewer
case predates its Treasury/foreign-office extension; app source was unchanged.
Actual mobile QA then found a **LOW, introduced local context omission**: the
new pages did not show source LGU/fund/budget year together. The before observation
is `.tmp/form1-signed-ui-context-before-20261017.log`. Two templates now use the
pinned original designation/financial scope, not current site, clock or mutable
master labels. Only these templates and the normal clerk test changed afterward.
Fresh one-case runs verify those fields through entry, pending review, issued and
correction entry. Earlier passes are not relabelled full-current-tree passes.
Source freezes: `.tmp/form1-signed-ui-{first,extended,final}-source-freeze-20261017.json`.

Four actual authorized SQLite responses were frozen after the final clerk case.
All eight 390/1440px captures were inspected: complete file/date/findings/issue
controls, source context and long labels fit, with no horizontal overflow.
Images: `output/playwright/form1-signed-{entry,review,issued,correction}-{mobile,desktop}-final-20261017.png`.
Before image: `output/playwright/form1-signed-entry-mobile-before-20261017.png`.
Inputs/assets: `.tmp/form1-signed-ui-qa-final-20261017`; DOM proof
`.tmp/form1-signed-ui-layout-final-20261017.json`; raw browser log
`.tmp/form1-signed-ui-browser-final-20261017.log`. An initial DOM helper extracted
too much adjacent text; its bounded header extraction was corrected and all eight
observations rerun. This was a QA-helper issue, not a financial or application defect.
These captures prove synthetic layout; actual browser submission/physical signatures,
printer use and LGU acceptance are not inferred from them. HTTP submission is
separately covered by the test cases above.

Combined verifier `.tmp/verify_form1_signed_ui_20261017.py` PASS / exit 0:
`.tmp/form1-signed-ui-local-evidence-20261017.json` retains exact identities,
source/log/image hashes, unchanged operator hashes, role-dependent button states,
source-header parity with the issued bundle, all five bundle members and both
original PDFs. System/migration-drift/diff checks PASS. All test/capture runners
are terminal; owned browser, MySQL and previews are stopped, ports 33308/8771 closed.
No operator migration/grant, dependency installation, eGAPS access or publication.

The four presets are opt-in: Budget Recorder **26**, Budget Verifier/Issuer **27**,
Accounting Viewer **24**, Treasury Viewer **24** permissions. Existing roles and
the default UAT tuple are unchanged. See the [permission-matrix addendum](finance-ia/ROLE_PERMISSION_MATRIX.md).

Reproduction (canonical Python 3.11, active worktree; wrappers isolate both stores):

```powershell
$grandPython = 'C:/Users/Administrator/Desktop/GH/grand/.venv/Scripts/python.exe'
& $grandPython -B -X utf8 .tmp/intake_primary_sqlite.py budget.test_form1_signed_views --verbosity 2 --failfast
& $grandPython -B -X utf8 .tmp/form1_signed_ui_probe.py native budget.test_form1_signed_views budget.test_form1_unsigned_copies.Form1UnsignedCopyTests.test_release_retains_complete_unsigned_bytes_and_original_sources_without_posting budget.test_form1_signing.Form1SigningTests.test_retains_exact_roles_documents_review_and_finance_isolation_without_issuance vouchers.tests.VoucherWorkflowTests.test_read_only_uat_viewer_can_preview_offices_without_action_authority budget.test_form1_signed_validation --verbosity 2 --failfast
& $grandPython -B -X utf8 .tmp/form1_signed_ui_probe.py sqlite budget.test_form1_signed_views.Form1SignedViewTests.test_minimal_officers_capture_verify_issue_and_download_exact_audited_originals --verbosity 2
& $grandPython -B -X utf8 .tmp/form1_signed_ui_probe.py native budget.test_form1_signed_views.Form1SignedViewTests.test_minimal_officers_capture_verify_issue_and_download_exact_audited_originals --verbosity 2
```

The eight-case SQLite follow-up selects the extended viewer case plus the same
two original HTTP cases, role-config consumer and four validators listed in the
native command. Native runners were sequential, never concurrent. These commands
describe the recorded scopes; rerunning the whole current clerk module also
includes the later source-context assertions.

### Current checkpoint report

| Item | Actual state |
| --- | --- |
| A. Already implemented | Complete source package, designation review, unsigned copy and signed/final services with immutable correction lineage. |
| B. Repaired | New clerk pages omitted source LGU/fund/year; pinned source context is now visible and tested. |
| C. Newly implemented | Receipt/history/review/issue screens, six routes, four opt-in presets and exact archived/audited downloads. |
| D. Missing | Evidenced numerical treatment, other original required-output/scenario work and full release/operational/LGU gates. |
| E. Out of scope | Generic signing/collaboration platform, fictional signatory accounts and unpurchased modules. |
| F. Unknown | Actual local appointments/signatures, accepted forms/printers and earmark basis. |
| G. Workflow connection | Source Budget package → unsigned copy → declared paper return → independent findings/issue → original evidence reprint; Accounting/Treasury retain source-scoped read/export. |
| H. Friction | No financial re-entry; honest missing dates; one combined action when both permissions apply, with separate duties still supported. |
| I. Controls | Original-source permissions, department/maker/UAT denial, CSRF/POST-only mutations, owning locks, immutable originals and explicit predecessors. |
| J. Remaining parity | Other original foundation requirements and manual/operational acceptance; no blanket Finance parity from this checkpoint. |
| K. Next checkpoint | Inspect supported source-treatment evidence/official instructions for the remaining numerical route; retain fail-closed behavior if authority remains unproven. |

**GO:** scoped local clerk checkpoint and next bounded development. **NO-GO:**
full release without its required review/current-tree CI, full Finance completion
or production. Published v172 CI covers its own commit only. Severity **LOW
RESOLVED** for this local context omission; the earlier software-delivery gap is
locally implemented, while full original-gate completion remains unproven.

## Implemented local service boundary

The service validation/checkpoint report below retains its earlier tested source.
Its then-open clerk-delivery markers are superseded by the current section above;
its numerical controls, immutable-history rules and scope limitations still apply.

`budget/0026_form1_signed_evidence.py` adds Finance-store receipt, independent
review and final issue tables. The service modules are
`budget/form1_signed_copies.py` and `budget/form1_final_issues.py`.

- A receipt pins the exact released unsigned copy, original returned PDF bytes,
  actual or explicitly unknown signing dates for each entity's four certification functions and separate
  Chief Executive approval, declared recipient/custody facts and recording actor.
  The uploader need not be the physical recipient. All receipt approval/issuance/
  cash flags remain false. No signature is inferred from a file upload.
- The returned document must be a bounded, readable, unencrypted PDF with at least
  the original page count. These technical checks cannot recognize handwriting or
  establish matching financial content. An independent Budget officer must inspect
  the original pages/copy identity, financial fields, physical custody and each
  entity's five signing functions, retaining explicit findings and their basis.
  Known dates must follow release, precede receipt, have retained designation
  authority and place Chief Executive approval no earlier than the four certifications.
  Missing/unreadable dates can be recorded as unknown and independently returned;
  approval still requires every actual date, even if every finding is marked verified.
- Verification/issuance require the latest preparation, current original sources,
  latest receipt and exact current final-issue predecessor. Historical downloads
  retain original authority checks but do not require current source heads.
  Source makers and receipt recorders cannot verify/issue their own evidence.
  A verifier with separate issuance authority may issue; no third officer is
  invented merely to add another web step. UAT and foreign-office mutation deny.
- A final issue retains an immutable five-member ZIP: `issuance.json`,
  `unsigned-copy.json`, `signed-evidence.json`, `unsigned-form1.pdf` and
  `signed-form1.pdf`. Metadata and every original member are verified against
  retained records. Downloads return original archive bytes without rerendering or
  repacking. New independently recorded verification/issue states do not rewrite
  original unsigned-copy or receipt flags. No journal or cash capacity is created.
- A corrected scan pins the previous final issue explicitly. It does not replace
  that issue. Financial changes still require the proper source/new-unsigned-copy
  route. Versions and predecessor one-to-one identities prevent competing issue
  branches. The existing BudgetVersion → Fund → package → preparation lock order
  extends through copy and receipt; no new workflow framework is added.
- `verify_and_issue` offers one atomic clerk action with both permissions. A
  failed issuance rolls back its new verification; the separate service actions
  remain available when offices use separate review and issue duties.

Read/export and record/verify/issue permissions are distinct. Every action that
packages or inspects original data also requires its underlying source/copy
authority. All new records preserve original department identity and actor scalars
across the separate default and Finance databases. No operator migration, grants,
environment change, vm-commit or publication is included.

## Validation scope

`budget.test_form1_signed_copies` covers receipt/verification/issuance separation,
original bundle membership/bytes, routing, immutable history, PDF/date/authority
rejection, per-entity findings, maker/foreign-office/UAT denial, stale sources,
successor lineage, combined-action rollback, revoked original-source export and
rehashed receipt/archive corruption. Synthetic PDF metadata explicitly states
there are no real signatures; fixture findings are not external acceptance.

`budget.test_form1_signed_concurrency` exercises native duplicate receipt,
duplicate decision, duplicate issuance, competing successor capture, issuance
versus a new receipt, and source successor versus verification. Each manually
owned fixture registers cleanup before setup. Native tests use fresh disposable
`test_grand_ci_default` and `test_grand_ci_finance` only.

Commands (Python 3.11; active worktree; isolated wrappers):

```powershell
$grandPython = 'C:/Users/Administrator/Desktop/GH/grand/.venv/Scripts/python.exe'
& $grandPython -B -X utf8 .tmp/intake_primary_manage.py check
& $grandPython -B -X utf8 .tmp/intake_primary_manage.py makemigrations --check --dry-run
& $grandPython -B -X utf8 .tmp/intake_primary_sqlite.py budget.test_form1_signed_copies --verbosity 2
& $grandPython -B -X utf8 .tmp/intake_primary_native.py budget.test_form1_signed_copies budget.test_form1_signed_concurrency --verbosity 2
& $grandPython -B -X utf8 .tmp/intake_primary_sqlite.py budget.test_form1_signed_copies.Form1SignedCopyTests.test_dates_complete_pages_designations_and_independence_fail_closed budget.test_form1_signed_copies.Form1SignedCopyTests.test_source_permissions_and_rehashed_corruption_cannot_fabricate_approval_or_archive budget.test_form1_signed_validation --verbosity 2
& $grandPython -B -X utf8 .tmp/intake_primary_native.py budget.test_form1_signed_copies.Form1SignedCopyTests.test_dates_complete_pages_designations_and_independence_fail_closed budget.test_form1_signed_copies.Form1SignedCopyTests.test_source_permissions_and_rehashed_corruption_cannot_fabricate_approval_or_archive budget.test_form1_signed_validation --verbosity 2
```

Run native commands sequentially against the owned disposable server, never the
operator stores. These are development checks, not an authorized release command.
System and migration-drift checks PASS. Initial SQLite service scope PASS:
**4/4, zero skips, 491.078s, exit 0**. Initial native scope PASS: **5/5, zero
skips, 690.842s, exit 0**, including six races. Both aliases were destroyed in
each run. Logs: `.tmp/form1-signed-core-{sqlite,native}-20261017.log`.
Initial source hashes: `.tmp/form1-signed-core-source-freeze-20261017.json`.

The initial scopes were launched before one subsequent local integrity guard:
predecessor linkage checked the retained metadata checksum without comparing the
actual predecessor archive bytes. A database-free pre-fix probe reproduced
acceptance of altered predecessor bytes
(`.tmp/form1-signed-predecessor-probe-before-20261017.log`). `_previous` now checks
the original archive's SHA-256 as well. Severity **MEDIUM, introduced in this
unpublished work**; no production financial record was affected. The source
freeze extension is `.tmp/form1-signed-predecessor-fix-source-freeze-20261017.json`;
only this guard and the corruption-test extension differ from the initial scope.
Do not describe the initial suites as covering that later guard.

Three separate database-free validation tests PASS / 0.004s, exit 0, without
creating either schema (`.tmp/form1-signed-validation-20261017.log`). They cover
two distinct entities' signing functions/dates and original predecessor byte
identity. They do not replace native persistence/race evidence. The SQLite
guard follow-up PASS: **4/4, zero skips, 98.738s, exit 0**, both aliases destroyed
(`.tmp/form1-signed-predecessor-sqlite-20261017.log`).

Further current-work correction: receipt capture originally demanded every date,
preventing honest retention/return of incomplete signing evidence. Unknown dates
are now explicit nulls, while both review integrity and approval submission deny
an incomplete set. The dates integration case covers that distinction, with an
additional two-entity pure validator. Final fresh SQLite/native follow-ups each
selected the two extended integration cases plus four pure validators (six tests).
Their logs are `.tmp/form1-signed-final-{sqlite,native}-20261017.log`; source freeze
`.tmp/form1-signed-final-source-freeze-20261017.json`.

| Final source scope | Actual result | Seconds |
| --- | --- | --- |
| Extended date/corruption integration + four pure validators, SQLite | PASS 6/6, zero skips, exit 0 | 268.588 |
| Same scope, native MySQL | PASS 6/6, zero skips, exit 0 | 272.186 |

Both aliases were destroyed in both final runs. The separate four-test service
scope and native five-test/six-race scope above remain earlier-source evidence.
Initial scopes predate both extensions; the four-case guard follow-up predates
the missing-date capture correction. Do not relabel them full-current-source passes.
The final selected cases cover the changed validation behavior; owning locks,
schema and the issue renderer were unchanged after initial validation. Scopes
overlap and must not be summed as distinct full-project coverage.

Evidence verifier `.tmp/verify_form1_signed_core_20261017.py` PASS, exit 0:
`.tmp/form1-signed-core-local-evidence-20261017.json` retains exact identities,
log/source hashes, chronology and unchanged operator DB hashes. All runners
47332/59416/83768/62175/15387 are terminal; no matching Python test process remains.
Owned MySQL is stopped, loopback 33308 closed. No browser/server was needed for
these service-only changes; this is not visual or physical form acceptance.
System/migration-drift and whitespace checks PASS.

Severity: **MEDIUM RESOLVED** unpublished predecessor archive-byte validation
gap; **LOW RESOLVED** inability to record/return explicitly missing dates.
**HIGH OPEN** unfinished complete clerk signing/issuance workflow. Full project
and dependent completion suites, security/release review and remote CI are **NOT
RUN — OUT OF SCOPE for this local service checkpoint**, required before release.
No public route, role assignment or numerical recipe was changed in this phase.

## Service-only checkpoint report (historical)

| Item | Actual state |
| --- | --- |
| A. Already implemented | Complete reviewed source package, designation review and immutable unsigned signing copy. |
| B. Repaired | Predecessor metadata needed actual archive-byte verification; missing signing dates needed truthful capture/return without approval. |
| C. Newly implemented | Finance receipt/review/final-issue persistence, source-scoped services, immutable original ZIP and explicit correction lineage. |
| D. Missing | Clerk receipt/history/review/issue controls, operational presets, audited original download controllers and their HTTP/layout/dependent validation. |
| E. Out of scope | Generic signing/collaboration platform, new paper-signatory accounts and unpurchased modules. |
| F. Unknown | Actual appointments/signatures, local printer/form acceptance and unresolved numerical/earmark semantics. |
| G. Workflow connection | Original Budget financial sources and unsigned copy → declared paper return → independent findings → retained issue evidence. No new ledger/cash authority. |
| H. Friction | No financial re-entry, honest unknown dates, exact-byte reprints and an atomic verify/issue option with both permissions. |
| I. Controls | Separate stores, original-source access, maker/UAT/office denial, parent-first locks, immutable evidence, version and predecessor uniqueness. |
| J. Remaining parity | Full clerk lifecycle, remaining original required outputs/scenarios and operational/restore/LGU acceptance. |
| K. Next checkpoint | Connect the existing services to scoped clerk controls, opt-in roles and audited downloads; validate minimal roles, HTTP/CSRF and layouts. |

## Remaining work after the clerk checkpoint

The clerk controls, original downloads, operational presets and scoped HTTP/
minimal-role/layout checks are now locally implemented/validated as recorded at
the top. They are no longer a missing software lifecycle to rebuild. Broader
current-tree security/release review, full CI and actual paper/form/LGU acceptance
remain unperformed. No published v172 CI result covers this local extension.

Keep unsupported numerical treatments, earmark semantics, required-output and
ordinary-scenario coverage, operational/restore validation and LGU acceptance in
the original remaining inventory. **GO for bounded local implementation and
validation; NO-GO for publishing this unfinished workflow, full Finance
completion or production.**
