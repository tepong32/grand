# Finance resumption: Budget integrity reconciliation — 2026-10-24

Status: **VERIFIED local bounded repair; not integrated or production accepted**.

## Accepted baseline and preservation

The user explicitly accepted security checkpoint
`f1711038e30c0e684e99b4fd5172eebacfe99436` and authorized Finance reconciliation/
resumption. That accepted checkpoint is the parent, not the stale canonical v112.
Its source/helper fingerprint `35c8b18b6584e6701249cc875d20d68453f7ac2789cf58da56038aaeb55a3c53`
was reverified across all 1,499 files before changes.

Current independent clone:
`C:/Users/Administrator/.codex/worktrees/grand-finance-budget-20261024-6d195553f3ea`.
Branch: `codex/finance-budget-integrity-20261024`.
The accepted security clone and original worktrees/archives/refs/stashes remain
recovery sources. Operator databases are not opened, copied into tests or changed.
No eGAPS, deployment, real Telegram, release/tag or primary-branch integration.
Finance remains NO-GO for production.

## History and unmatched-work reconciliation

VERIFIED: canonical `codex/finance-cheque-redemptions` is still
`ce0c7243fb6b2c189bd2356dba866261e8897508`, an ancestor of the accepted parent.
It contributes no local-only committed history against that parent. Its dirty
CONTINUE, changed SQLite store, untracked Accounting policy test and nine
Playwright PNG/PDF artifacts remain in place. The database is potentially unique;
only Git status/metadata was inspected, not its records. The four stash identities
remain 5547b689..., 937fa81d..., 8f96fe2f..., 1b70a1e8...; none was applied or dropped.

VERIFIED: the v188–v210 chain is linear from v187/a116691 to
`4f1f34ae0423f3bdca54b698a5743d7c40e024fb`. Remote
`codex/output-pdf-checkpoint` points at that exact tip; master remains
`04b25bf7b1c18a1d3932596597ba629e240ba252`. Individual v203/v204 branch refs are
not remote heads, but their exact commits are ancestors of that verified tip.
No fetch, merge, rebase or cherry-pick was used to adopt this scope.

| Source range/group | Reconciliation against accepted f1711038 |
| --- | --- |
| v188–v197, 9c90e1a8...–ba6bdc42... | Retrieval, maintenance, GSO working copies/drafts and source research remain unmatched; no automatic adoption or deletion. These are not prerequisites for the Budget repair. |
| v198–v202, 5206412d...–b9b9cca4... (G5/G6) | Their private-file/citizen/memo behaviors are already represented, with later P1/P2 hardening, in the accepted checkpoint. Do not replace its files with older source versions. |
| v203, 5ad07d052324b744332164cd894592fa597b64d5 (G7) | Dated-capacity control and its tests absent from accepted baseline; selected for reconciliation. |
| v204, f1b32ff7c95e0f60804ba3b6feec835788be8c05 (G8) | Final obligation-line validation absent; selected with G7. |
| v205–v206, 3317d450...–d67b9cae... | Inventory count/search work remains separate and unmatched. |
| v207–v208, 49af4e14...–ec5a640a... | Finance redemption-charge work remains unmatched; requires its own persistence/calculation/source/permission review. No acceptance inferred. |
| v209–v210, 7810ceb3...–4f1f34ae... | Draft/report/dependency/PDF work remains separate. No dependency or whole-file adoption here. |

VERIFIED: the three affected Budget implementation/test files match the G7 source
parent b9b9cca4 byte-for-byte after line-ending normalization. The path-specific
b9b9cca4→f1b32ff7 patch therefore applies without an application dependency on the
excluded feature groups. VERSION/CHANGELOG/global handoffs from that chain are not
copied. The two specialized source contracts are retained with historical labels.

The untracked `accounting/test_policy_concurrency.py` investigates concurrent
period-close policy activation. It is not represented by that path in the accepted
parent. Current `accounting.close_services` still locks separate candidates and an
optional active row, matching the unresolved first-activation question in
`FINANCE_NATIVE_INVARIANT_AUDIT_2026-09-09.md` / D-064. This is relevant unmatched
work, NOT VERIFIED as a current passing test and not automatically adopted or
classified obsolete. Reproduce it on current supported fixtures before dependent
numerical breadth; preserve the original test and all historical evidence.

## Why this control milestone precedes new numerical treatment

The current roadmap's supported Form 1 numerical treatment remains a functional
milestone, with explicit source/official-rule requirements. Reconciliation found
existing financial-control failures first: current/effective-date checks can use
capacity restored only later, and final obligation services can omit existing
line validation. Repair these known controls before introducing more arithmetic.
This does not invent earmark, certificate, local authority or numerical recipes.

## Implemented scope

- `budget/services.py`: aggregate proposed effects and replay each appropriation
  line's immutable dated release/reserve/deferral/obligation streams. Enforce the
  existing nonnegative/appropriation/executable bounds at every affected day-end.
  Retain same-day grouping and exact Decimal effects. Final writers retain their
  existing shared appropriation locks, transactions, independent review and default
  case/issuance-before-Finance lock ordering.
- The shared obligation validator calls each loaded line's existing `full_clean`
  at submission and certification. Malformed source/office/amount/type/direction
  is rejected before any posted movement, number, checksum or audit commits.
- `budget/views.py`: eight allotment/obligation header/line draft mutation paths
  acquire the scoped owning header write lock before reading current status or
  binding/saving forms. A no-op state-version UPDATE gives SQLite a writer and
  InnoDB a row lock; current state is then rechecked. Submission/posting uses the
  same header. GETs do not acquire that write lock. Office/role/UAT predicates
  remain unchanged. Inner savepoints roll back caught validation/audit failures
  without leaving the transaction broken while the form error renders.
- Tests retain original Budget classes/identities, add the G7/G8 cases in their
  existing classes, and add focused draft access/rollback plus eight native
  posting-versus-draft cases. Native tests synchronize with events and observed
  `performance_schema.data_lock_waits` on the exact owning header table, then
  assert HTTP outcomes, header, lines, movements and audit state.

No schema, migration, routing, permission, dependency, journal recipe, dashboard
card, private-file helper, reporting renderer or other feature group changed.
The separately approved CI owner-pin compatibility repair preserves every required
job, worker count, coverage assertion and native acceptance gate.
Only existing rules and transaction boundaries are enforced; rejected historical
malformed rows are not silently repaired or removed.

## Current evidence

Risk: Finance calculations/writes, source attribution, authorization, audit and
transaction/concurrency boundaries, plus a separately approved CI compatibility
repair. Focused checks expanded to Budget/quarterly/payable/office/voucher/advance
correction dependencies. No indiscriminate whole-project local rerun.

| Local check | Actual result | Source identity |
| --- | --- | --- |
| Focused SQLite02 | PASS 22 /12 native-only skips,34 discovered;4.931s test /279.735s total;exit0 | `106f90cb3eb66a6cf4eadb129abcbcd4d63edfd3f7e7742ca17756aa4c868c7b` |
| CI partition/coverage unit01 | PASS 11/11, zero skips;0.008s test /2.515s total;exit0 | final `82cac93e93ad2cfcbf7d4742d6e59719405576128f0104b19d946c6ca182b1fd` |
| Native affected02 | PASS 297/297, zero skips;357.957s test /622.688s total;exit0 | same final 1,506-file fingerprint |
| Complete discovery/partition | PASS 3,061 distinct application IDs /374 classes;all 8 workers cover each exactly once | final source; **not 3,061 executed passes** |
| Syntax/whitespace | PASS;1, 126 Python files, with later CI edits separately parsed | unchanged source hashes verified |

All20 native concurrency cases execute:12 in the existing Quarterly class
(four quarterly/dated-capacity cases plus eight new draft/post cases), and eight
advance-recognition-correction cases. The eight new draft cases observe actual
`performance_schema.data_lock_waits` on the exact owning header before asserting
rejection and unchanged header/lines/movements/audit. No duplicate test identities.
Both aliases were destroyed, the owned native server stopped and port closed;
the stopped system-only source template remained unchanged. Real Telegram HTTP
transport is forbidden by both runners; mail is local-memory only.

The focused SQLite fingerprint differs from final only in the two subsequently
approved CI files. [Exact reuse proof](evidence/finance-budget-2026-10-24/focused-reuse-proof.json)
verifies every application/test/helper byte unchanged, with identical runtime,
settings, schema, fixtures and assertions. CI checks are fresh on final source;
native02 shares that final identity. This is narrow SQLite evidence reuse, not a
complete final-source SQLite suite claim.

[Portable evidence and restoration limits](evidence/finance-budget-2026-10-24/README.md)
retains literal executable/argument arrays, full IDs/skips, raw logs, manifests,
runtime versions and exact helper bytes. Exact commands are in the
[focused SQLite receipt](evidence/finance-budget-2026-10-24/focused-sqlite-02.receipt.json),
[native receipt](evidence/finance-budget-2026-10-24/affected-native-02.receipt.json) and
[CI receipt](evidence/finance-budget-2026-10-24/ci-unit-01.receipt.json).
The pinned interpreter is
`C:/xxx/_INSTALLS/_HERE/_xxx/grand-checkpoint209-pdf-venv/Scripts/python.exe`.
Native command:

```text
<pinned-python> -B .tmp/finance-reconcile/record_run.py affected-native-02 -- <pinned-python> -B .tmp/finance-reconcile/native_gate.py expanded
```

The gate expands retained `expanded-labels.json` into the unchanged native runner:
Budget core/quarterly/concurrency, payable handoff, schedule/forecast office identity,
central vouchers and original/cancelled/returned advance corrections. Historical
forecast cases imported by the selected modules are included in the 297 actual IDs.

Raw SHA-256:

- SQLite02: `07f23e44a35bc16bfab97ddec85fa3bb6019230a954d98566cf9bd6891128bbd`;
- native02: `44ef7b3b81163114b4d1d3fb6740c226d042b82a1abd96ccab7d2b094d297694`;
- CI unit01: `d63ba90c31bce03ef04ae1dcd2c726f185d0267d1c3e39b5952dbeb816d203fd`.

## Historical results and the approved CI repair

Run01 receipts/logs/manifests remain unchanged: focused SQLite22 passed /12 skips
and native297/297 passed on fingerprint `26eb418a...`, before the test-owner review.
Those passes do not validate final test layout. The new draft scenarios were moved
from two added classes into existing AnnualBudgetPreparationTests /QuarterlyPlanningConcurrencyTests
via plain support mixins; no assertions or old IDs were removed. This justified
the fresh focused02 and native02 runs.

**FAIL — PRE-EXISTING, locally reproduced:** complete discovery with exact accepted
f171 Budget test-module bytes had the same 374-class set and an intake original
owner 0, while the retained CI pin required3. All8 partitions failed before tests
executed. This is not a hosted failure or a full baseline test pass. The owner
explicitly approved a separate repair: pin the reviewed original owner 0, retain
intake worker 6, all 8 workers, required jobs and complete/native coverage gates.
All nine original CI test function bodies/IDs, the workflow and coverage aggregator
are unchanged; two added tests cover the actual pin 0 and wrong-owner rejection.
[Diagnosis, approval, proof and current result](FINANCE_CI_OWNERSHIP_BLOCKER_2026-10-24.md).

Historical v203/v204 reports retain their original red/green evidence and limits;
they do not validate this reconciliation. Read-only Actions queries returned zero
retained runs for exact source SHAs 5ad07d05...,f1b32ff7...,tip4f1f34ae... and accepted
f1711038.... This is an evidence gap, not proof of failure. No earlier green run
validates these later sources. Current hosted candidate/primary CI is NOT RUN.

## Sensitive review, preservation and checkpoint boundary

The user added a universal pre-VM-commit sensitive-information review, saved in
`C:/Users/Administrator/.codex/AGENTS.md` and this repository's testing protocol.
Extended quick local scan:1,978 text files including two large tracked JSON
artifacts;133 flags reviewed as124 synthetic test/showcase assignments, eight vendor
source-map properties and one documented Firebase placeholder. No real credential
was identified or removed; no values are retained in scan reports. Private ignored
operator data, databases, binary contents and full Git history were not inspected.
This is not an exhaustive “secret-free” claim. Final staged content is reviewed
before committing, with an index-bound local receipt; curated raw logs and decoded
helpers are also checked for the private native fixture credential.

VERIFIED preservation: all 1,499 accepted-source hashes, accepted refs/stashes/status,
canonical HEAD/branch/status/four stash identities, and ten untracked sizes match
the initial inventory. No operator database was opened or hashed. Original
worktrees/recovery sources and archive were not altered.

The installed VM release CLI would bump VERSION/CHANGELOG and tag, prohibited here.
Its read-only preview is retained. Only the existing `GitService.commit` helper is
used for a tag-free local checkpoint of reviewed paths, parentf1711038, message
`Checkpoint: reconcile Budget integrity and reviewed CI ownership`.
No VERSION/CHANGELOG, release/tag, primary integration, remote push or deployment.
This local checkpoint does not establish release or Finance acceptance.

## Remaining checks and next work

- NOT RUN — OUT OF SCOPE: expanded/full local SQLite and whole-project native suites.
  The22 affected/direct SQLite checks,297 native dependencies and CI11/static full
  partition cover this bounded slice. Full exact-candidate/resulting-primary CI,
  review and all existing integration/release gates remain mandatory.
- NOT CHECKED: all-class native concurrency guarantees, browser/printer/form/LGU,
  actual local rules, production storage/proxy/logging and operational/recovery
  acceptance. The unchanged security code retains its accepted scoped evidence;
  its328 native tests do not establish Budget or whole-Finance acceptance.
- Next bounded control investigation: preserved close-policy first activation
  (D-064) with supported current native fixtures and actual independent outcomes.
  The untracked test is relevant but not automatically adopted or a verified
  production defect. Stop dependent progression if a critical defect is reproduced;
  any necessary migration must refuse duplicates and preserve immutable history.
- The next functional Form1 numerical milestone requires applicable reviewed
  official/source rules. Do not invent a recipe, infer local acceptance or repeat
  completed browser branches to avoid that evidence dependency.

Finance remains **NO-GO for production**. No eGAPS or production system access.
