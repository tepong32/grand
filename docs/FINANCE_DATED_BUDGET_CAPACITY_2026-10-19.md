> Historical source contract/evidence retained from 5ad07d0. It does not validate
> this reconciled candidate; see FINANCE_BUDGET_RECONCILIATION_2026-10-24.md.

# Dated Budget capacity — retained financial-control repair

## Confirmed defect and existing meaning

Local parent v0.7.202 is `b9b9cca4e1b3f90b121c3a98a0f10d16b1b779f3`.
The original Budget services checked allotment changes against latest balances;
obligations checked their effective date and latest balance. Neither checked every
intervening posted date. A later return/cancellation could hide an earlier breach.
This is a defect in existing released-allotment/obligation controls, not an
interpretation of the unconfirmed procurement earmark/certificate policy.

Actual direct-service regressions on unchanged202 reproduce four assertion
failures/zero errors: a backdated release exceeds appropriation before a later
return; a withholding uses a later release early; an obligation consumes capacity
restored only by a later cancellation; and certification misses that intervening
breach after other postings. Original two-store fixture/file hashes remain unchanged.

Example: released1000; obligation800 onJanuary15; cancellation800 onJanuary25.
A new obligation500 onJanuary10 fits both January10 and the latest balance, but
would make January15 obligations1300. The existing capacity definition requires
the new request to be rejected. The repair does not rewrite any original entry.

## Bounded implementation

`budget.services._validate_dated_budget_capacity` reads each line's immutable
allotment and obligation streams once, groups their signed effects by effective
date, then replays complete day-end balances. It applies the proposed combined
line effect from its effective date through every subsequent posted date. A date
without prior movements is included. Same-day source effects are grouped, matching
the existing date-only as_of contract; no intraday financial ordering is invented.

It preserves the existing constraints: releases within appropriation, nonnegative
reserve and deferral balances, nonnegative executable allotment, and obligations
between zero and executable allotment. The old current/effective-date checks and
messages stay in place. Allotment orders aggregate their proposed effects per
appropriation line; obligation requests use their existing signed aggregate.
The helper makes two movement-stream reads per line, not one query per date.
No benchmark or production-volume guarantee is claimed.

Both validators run at submission and again at posting/certification. Final
writers retain the existing shared AuthorizedAppropriationLine row lock and
transaction boundaries; no new lock, automatic retry or replay of financial
actions. A stale submitted document is rejected with the actual affected date.
Its status/version, assigned number, audit events and original movements roll
back unchanged. Valid backdating that fits every date remains allowed.

No models, migrations, database routing, permissions, financial recipe, source
matching or journal output changes. Separate stores, office/UAT denial, independent
approval, issuance boundaries and original correction lineage remain mandatory.
This does not adopt another LGU's earmark procedures or create certificate authority.

## Focused evidence and native gate

Nine added cases in the existing AnnualBudgetPreparationTests cover the four red
defects, backdated negative-obligation and early hold-release failures, posting-time
rechecks, valid backdating at the exact capacity boundary and same-day hold lifting.
The HTTP certification route also rejects the breach without posting. Corrected
synthetic proof passes9/9,3.986s,zero skips; no protected source bytes changed.
An initial positive fixture used a hold above the latest released amount; the old
current-balance guard correctly rejected it. The valid fixture now fits all dates;
no application check or failed assertion was weakened.

Two added native races extend the existing Budget authority concurrency class:
competing backdated releases, and a backdated withholding versus obligation
certification. Each alone fits, but both together would breach an intervening
date while the latest balance still fits. Only one may post; the losing action
must roll back. Existing class identities and every old CI shard owner stay intact
(3060→3071 tests). No CI gate or inherited scenario is migrated.

Fresh dependent SQLite discovers233 tests:221 pass /140.139s, with12 explicit
native-only skips. Scope includes Budget core/quarterly, central vouchers, and original,
cancelled and returned advance corrections. Fresh native MySQL8.4.11/strict-mode
execution of the same scope passes233/233,277.089s,zero skips, including all12
races. Both test aliases are destroyed, the owned server stopped and the original
system-only template hashes unchanged. Exact commands, local v0.7.203 checkpoint
and limits are recorded in [CONTINUE.md](../CONTINUE.md).

Actual synthetic browser certification is rejected with January15 identified;
the request stays pending with no stored number. All movements/audit events and
the entire intentionally seeded disposable Finance database hash are unchanged.
The original source pair/files also match. Screenshot inspected;390px viewport
and375px document width. Browser/server stopped; missing synthetic brand/avatar
files remain known404s. This is not real financial, paper or LGU acceptance.

Hosted exact-candidate/master CI and publication remain separately unauthorized.
Finance stays **NO-GO** pending functional, financial-control, operational/recovery
qualification and formal acceptance. No deployment or production operation.
