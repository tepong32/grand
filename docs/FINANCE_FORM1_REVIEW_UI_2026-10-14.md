# Whole Form 1 internal review screen

Accepted installed Version Manager v0.7.160 / `15b079c1d78a9bc63edbd8197242ba2f15d11644`, following the fully accepted v0.7.157 release. Independent Budget, Accounting
and Treasury officers can now review the retained whole package through its
existing detail page. Preparation intake and statutory issuance remain open.
Release, exact master/tag refs and both [candidate run 38442773424](https://github.com/tepong32/grand/actions/runs/38442773424) and [primary run 38447621668](https://github.com/tepong32/grand/actions/runs/38447621668) are verified.
All nineteen jobs passed on each run: security, verify, mysql and sixteen
workers. Native passed all 2,473 cases without skips; SQLite passed 2,278 with
the same 195 native-only skips. Full logs, exact identities, cleanup and
20 primary failure-level annotations mapped to passing permission-denial tests
were verified. See [CONTINUE.md](../CONTINUE.md) for the next bounded step.

## Change and control boundary

The screen replaces the need to invoke the existing decision service manually.
Each designated officer records an explicit Verified / Not verified choice and
evidence basis for every existing office check, plus designation authority and
an independent review/return reason. No check defaults to verified. Approval and
return use the existing immutable decision service and its proposal → Fund →
package lock order; source checks run again within that owning transaction.

The existing maker/checker separation, distinct actors, exact office responsibilities,
source viewing permissions, UAT mutation denial, currentness/completeness controls,
audits and immutable version/decision history remain authoritative. A return can
describe accessible stale sources; an approval requires the latest complete
package and current original sources. The route accepts POST with Django CSRF
protection. Viewing and complete export authority remain separate. The UI adds no
models, permissions, persistence recipe, ledger posting or financial authority.

Changed application files: `budget/form1_package_forms.py`,
`budget/form1_package_views.py`, `budget/urls.py`,
`templates/budget/form1_package_detail.html` and
`budget/test_form1_package_views.py`. All other released application/services,
workflow and dependency sources remain unchanged. The complete 1,138-source
fingerprint is retained in ignored `.tmp/form1-review-ui-source-fingerprint.json`.

## Actual validation

- PASS: initial five new HTTP regressions on isolated SQLite, 205.002s; both
  test stores destroyed. They cover three independent office decisions, explicit
  checks, invalid/missing/false inputs, return history, CSRF, HTTP methods,
  viewer/maker/wrong-role/UAT denial, revoked source access, stale sources and
  unknown coverage. No financial journal or statutory flag is created.
- PASS: same five cases on fresh native MySQL 8.4.11, 221.386s, zero skips,
  both test stores destroyed. Python 3.11 / Django 5.2.17 and the isolated patched
  dependency environment are retained. Initial tests preceded the final explicit
  error-display refinement; the dependent runs below recheck the final source.
- PASS: final affected/dependent SQLite run, 20 tests / 1503.432s, 19 passed /
  one expected native-only race skip, exit 0 and both stores destroyed. The same
  fresh native run PASS: 20 tests / 1716.625s, zero skips, actual exit 0 and both
  stores destroyed. Its final case executes three decision/return/successor races.
  Both logs and exact identity sets were verified against the unchanged final
  source fingerprint. Scope includes new
  HTTP cases, existing review/currentness/preparation/history/register,
  complete JSON/ZIP/PDF exports and native review races. SQLite race skips do not
  count as native passes. SQLite 83198 and native 90413 are completed; do not poll
  or restart them. Completion records retain exact log/source hashes.
- PASS: Django system checks and `makemigrations --check --dry-run`; no schema
  changes, and the guarded earlier synthetic stores are byte-for-byte unchanged.
- PASS: current dependency audit, no known vulnerabilities. Requirements are unchanged
  from the fully green v157 candidate and successful primary security job.
- PASS: real Chrome/Playwright browser submissions by all three distinct synthetic
  officers. Final state has three retained decisions, original package checksum
  and journal count unchanged, and all statutory approval/issuance/cash flags
  false. Desktop (1440 × 1000) and mobile (390 × 844) screenshots were visually
  inspected. Mobile fields wrap and the Treasury action remains usable.

Actual commands used canonical Python 3.11 with `.tmp/my_work_sqlite.py` and the
fresh two-store `.tmp/retrieval_native.py`, passing these Django labels:

```text
budget.test_form1_package_views
budget.test_form1_package_reviews
budget.test_form1_packages
budget.test_form1_package_register
budget.test_form1_package_exports
budget.test_form1_package_print
budget.test_form1_package_review_concurrency
```

Complete initial/dependent logs are retained as `.tmp/form1-review-ui-*.log`.
The source hash and complete local publication gates PASS and must remain true
at release execution. Discovery-only proof retains all 2,468 original IDs and
adds the five new HTTP cases: 2,473 total. This is not a full execution result. Browser records are cloned
from an earlier explicitly synthetic rehearsal into a new isolated directory;
operator databases and earlier artifacts are untouched. The Playwright CLI's
five-second navigation wait expired after actual successful clicks; the server
recorded POST 302 / GET 200 and independent source verification confirmed each
decision. Actions were not blindly replayed. CLI update/Windows exit notices do
not establish failed financial decisions and are retained in the browser logs.

[Desktop evidence](../output/playwright/form1-review-desktop-20261014.png) and
[mobile evidence](../output/playwright/form1-review-mobile-20261014.png) are
synthetic UI verification, not LGU acceptance.

## Remaining gates and next step

GO/NO-GO: local and exact-release candidate/primary acceptance **GO**; production **NO-GO**.
Both aggregate gates passed complete discovery before promotion; resulting
primary checks also passed. No broad
new framework or peripheral domain is introduced. Full 2,473-case local reruns
are NOT RUN — OUT OF SCOPE for five isolated UI/test sources with no changes to
shared financial services, models, settings or migrations; affected/dependent
20-case suites and native races pass, and the complete prior-source local and
candidate/primary suites passed. Candidate and primary CI executed and verified all 2,473 discovered cases. Whole-package preparation
intake is the next bounded part of the existing clerk route. Statutory certifiers,
Chief Executive approval, issuance, exact local outputs, representative varied
source performance and human/physical acceptance remain open. Manual local
decisions are deferred for tonight; missing evidence stays unknown.

The separate provider graph still lists older dependency versions despite the
patched released pins and clean actual audits; its 24 open alerts remain tracked
in the [gap register](FINANCE_GAP_REGISTER.md#fin-gap-038---security-and-native-regression-release-gate).
No alert was dismissed and this checkpoint does not authorize production use.

See [review/delivery contract](FINANCE_FORM1_PACKAGE_REVIEW_DESIGN.md),
[source contract](FINANCE_FORM1_SOURCE_CONTRACT.md),
[roadmap](FINANCE_ROADMAP.md) and [foundation gap register](FINANCE_FOUNDATION_GATE.md).
