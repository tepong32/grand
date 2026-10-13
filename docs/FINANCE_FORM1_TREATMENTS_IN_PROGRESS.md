# Form 1 treatment proposals and independent findings

Development from published v0.7.166 / `27b3f63`. The bounded implementation is locally validated and prepared for the installed
VM release; candidate/primary remote gates remain pending. It is not numerical
treatment approval or LGU acceptance. Continue the [existing treatment plan](FINANCE_FORM1_PHILHEALTH_SOURCE_AUDIT.md)
and [whole-package review contract](FINANCE_FORM1_PACKAGE_REVIEW_DESIGN.md).

## Current implementation

Three Finance-store models retain an immutable proposal, its original authority /
reconciliation bytes, and independent office decisions. Each proposal pins the
exact original whole package, its PhilHealth inventory and every original signed
part, including source columns and shared counterpart-capacity identities.
Findings cannot edit amounts or omit parts. Successors pin the immediate retained
predecessor; previous proposals, documents, decisions and package bytes remain.

The service uses existing package source read/export grants, the designated Budget
package preparer and Budget/Accounting/Treasury review grants. The proposer and
original package maker cannot review the proposal. One distinct actor per required
office/role, explicit responsibility checks, original designation and decision
reasons are mandatory. UAT membership denies mutation even with operational grants.
New factual approval requires current original sources and the latest proposal;
return remains an immutable closure, including accessible stale evidence.

BudgetVersion, Fund and retained identity locks follow the existing order on the
Finance store. New version, office/role, actor and attachment identities use
unconditional native constraints. Migration 0023 creates only new tables; it does
not backfill, rewrite historical financial evidence or merge database aliases.

A rejected overlap claim and a confirmed overlap claim remain distinct source-bound
findings. Completing factual review does not approve an offset, supply a numerical
recipe, issue Form 1 or establish available cash. Existing PH and whole-package
calculations remain unchanged. This is the proposal/history prerequisite; the
eventual supported presentation recipe and fresh successor integration remain
required, rather than being removed from the completion goal.

## Validation and next work

PASS: isolated Django system check and migration generation with Django 5.2.18 /
Python 3.11. FAIL - CAUSED BY CURRENT WORK: initial six tests each had setup errors
on SQLite (6.545s) and native (6.413s), actual exit 1; both stores destroyed. The
new generic `decide` helper shadowed the inherited actuals fixture helper before
`reviewers` existed. Treatment helpers now have dedicated names; no production
assertion or financial validation changed. Original failed logs are retained.
Launchers 21532/79460 are terminal; do not poll or restart them.

PASS: helper-corrected six-case SQLite (250.539s) and native (264.410s), zero
skips, actual exits 0, exact six identities and both-store cleanup verified.
Launchers 17203/64055 are terminal; do not poll or restart them. Original failed
logs and corrected completion receipts are retained under `.tmp/treatment-*`.
This is the initial service/model scope, not broad/concurrency/UI or release
acceptance. Subsequent hardening pins the retained department label and turns
malformed decision structures into controlled validation failures. Seven-case state/race validation completed: SQLite six passed / one native
skip, 299.815s; native seven passed / zero skips, 400.317s. Actual exits 0 and both
stores destroyed. Launchers 19538/21958 are terminal; logs
`.tmp/treatment-state-races-{sqlite,native}.log`.
The native case covers simultaneous version preparation, same-role decisions,
return/approval ordering and original-source successor races with explicit fixture
cleanup. These passes cover the state/office-label hardening and concurrency prerequisite.
 No numeric calculation, original package or ledger was changed.

The new tests exercise genuine retained packages, confirmation/rejection without
invented arithmetic, complete signed partitions, invalid documents, maker/role/UAT
boundaries, revoked source export access, returns, source successors, immutable
documents and rehashed corruption. Failed/final results must be recorded before
claiming a validated checkpoint.

Remaining: complete final dependent/local and remote release gates; supported explicit
presentation recipe with separate gross/deduction/adjustment/net controls; fresh
package preparation and independent decisions; dependent regression and VM/remote
gates. Preserve legacy schema-1 reproduction and every original output.

NOT RUN: operator migrations, production data, actual LGU participation/funding
authority, statutory signatures, physical custody/printer and operational acceptance.
These remain open/deferred tonight. The newer BLGF full text still returns HTTP 403
with TLS verification retained; its indexed first page supplies no verified recipe.
No local or national adjustment formula was inferred. Finance production remains
NO-GO; the complete foundation goal remains active.

## Clerk delivery and proportional validation

The ordinary package screen links to full findings history. Budget preparation
lists every original signed source part with fixed amounts, human-readable periods,
explicit findings, funding/lineage basis and original document uploads. Successor
forms reuse prior findings without implying approval. Detail/history paginate all
retained rows; JSON/ZIP export captures one original decision set under the existing
owning locks and retains exact original whole-package and treatment document bytes.
ZIP paths use server-defined keys, not original upload filenames. Existing source
export permissions, atomic export archive, manifests/audit and no-store/nosniff
responses are retained. No new role framework, draft cache or financial recipe.

FAIL - CAUSED BY CURRENT WORK (test expectation): initial four HTTP cases had one
failed assertion on SQLite 293.188s and native 305.880s, actual exits 1 and cleanup.
A source view grant had been removed while its separate export grant remained;
200 export was correct under the existing contract. Revised tests assert the view
403, independently authorized export 200 and explicit export-revocation 403.
Browser inspection also reproduced blank original amounts from a form-field/
context-name collision; explicit original context repairs display, and the test
now requires every signed amount and original identity to render.

PASS: real browser multipart preparation and three distinct office decisions;
all nine source parts, original package checksum and two journals unchanged,
no numerical approval. Four desktop/mobile screenshots inspected without page
overflow. A CLI click exceeded its navigation wait; actual successful POST and
readback were confirmed without replay. This is synthetic proof, not LGU acceptance.

Final affected/dependent scope: original packages, whole-package reviews/exports/
HTTP intake and review races, plus all new services/HTTP/races. Nine labels,
35 unique cases. SQLite completed PASS: 33 passed / two native skips, 1,436.823s,
exit 0 and both-store cleanup. Native completed PASS: all 35 passed / zero skips, 1,642.254s, exit 0 and
both-store cleanup. Exact identities/source freeze are verified by
`.tmp/verify_treatment_local.py`; 87927/36607 are terminal.
Full discovery is 2,544 unique IDs; candidate/primary full CI must cover them exactly
once, preserving all original native cases and zero native skips. No workflow,
timeout, test assertion or security finding is disabled for release.

## Original-goal checkpoint report

A/B: prior retrieval and Budget source/whole-package/intake routes are implemented;
the earlier CI incident is resolved in accepted releases. Current display defect
and test expectation were repaired within the bounded checkpoint.
C: source-bound findings, immutable review/return/successor history and usable
original-document delivery, with no ledger change.
D/F: supported numerical recipes, statutory designation/issuance, local earmark
rules, exact required output inventory and operational/LGU acceptance remain open.
E: unpurchased modules, unrelated refactors and speculative case breadth remain
out of scope.
G/H: Budget retains the exact source findings; Accounting and Treasury inspect the
same originals and record distinct findings, then authorized offices retrieve the
complete evidence. No manual JSON input or separate spreadsheet framework is needed.
I/J: original financial amounts, dated evidence, source/office/actor authority,
independence, UAT denial, native identities and both database aliases stay intact.
K: finish release acceptance, then only evidenced numerical successor/issued-output
work or an independent named output replay while local rules await confirmation.
See [remaining tasks and estimate basis](FINANCE_REMAINING_WORK_2026-10-14.md).

NOT RUN / ENVIRONMENTAL: normal browser file-save acceptance. Browser download
attempts reported `download.saveAs: canceled`, including a fresh context with
acceptDownloads enabled; server logs show generated ZIP 200 and client broken
pipes. The browser's authenticated JSON HTTP readback returned 200 with all nine
parts/three decisions, false numerical/issued flags, attachment disposition and
archive SHA header. Existing HTTP tests verify complete ZIP bytes/hashes and
revocation. This proves application delivery within that scope, not a completed
browser file save or a diagnosed browser cancellation cause. Do not change the
user's browser/download software to obtain a pass; manual acceptance is deferred.
The owned browser and rehearsal server are closed/stopped; original fixtures remain.
