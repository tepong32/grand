# Reviewed maintenance corrections — development contract

Owner direction2026-10-18, DECISION-GSO-003. Implement a proposed documentary
successor beside a completed/cancelled maintenance case. Original case fields,
closure, asset status/custody, original evidence/events and Accounting stay intact.

Managers with the existing explicit maintenance-management grant may propose a
complete corrected set of descriptive work/date/cost/reference facts, with reason
and protected evidence. Changes to asset outcome, status, custodian or financial
postings are outside this workflow. Unknown cost and explicit zero stay distinct.
A distinct explicit review permission plus existing scoped maintenance read access
authorizes a different person to approve/reject; install no automatic grant.
UAT mutation denial applies even with both permissions.
Maintenance navigation returns these reviewers to their authorized case history.
Separate asset-register access remains independently checked; a maintenance review
grant does not make asset-register or general GSO dashboard routes available.

Keep immutable proposal content, actor/time, original case basis, predecessor
approval, exact request UUID and retained evidence metadata. Decision events are
append-only. Approvals serialize asset → original case → correction, compare the
expected version and current approved predecessor, and reject self/stale/tampered
decisions. A competing proposal cannot overwrite an intervening approval. Rejected
or mistaken proposals require a fresh proposal; never backfill approvals or edit
the original. Existing correction notices remain statements.

Show the original record alongside the latest approved documentary correction,
with pending/rejected history clearly labelled. Approval is an internal record
decision, not official Accounting valuation, payment, custody restoration or a
retrospective change to actual events. No automatic JEV or Finance-store write.

Retain protected correction files with the database pair/private root. Share the
existing original-case/notice 20-file and100MB budget under the same locks; every
file is at most15MB. Downloads check scope, record/history integrity and hash/size
on the actual streaming handle. Read-only recovery checks must cover records,
files, unknown/stale sources and orphans without repair/deletion.

Required checkpoint evidence: direct service and authenticated HTTP authorization,
independence/UAT/scope, changed/missing/unsafe files, exact retries, immutable
originals, stale predecessors/versions, zero/unknown costs, native competing
decisions and shared-budget races, additive default-only migration and ordinary
desktop/mobile staff journey. Implemented state and actual results belong to
CONTINUE.md. Finance remains NO-GO; no production migration/deployment authorized.

## Finding proposed corrections

The local employee-home entry uses existing maintenance read authority and current
GSO office scope, including reviewers without asset-register access. Its counts
describe cases and distinct cases containing proposed corrections; they do not
establish current source integrity, approval eligibility or corrected facts.

Maintenance history retains its original open-case default. The explicit Proposed
corrections link selects all case statuses and narrows to cases with pending
proposals. Each case appears once even with multiple proposals, and pagination
retains the chosen case/review filters. Open the original case to compare retained
proposals, then use its existing independent review route. A pending proposal can
be stale or otherwise ineligible; detail/service checks remain authoritative.
UAT reads do not acquire mutation rights. Actual validation is in CONTINUE.md.
