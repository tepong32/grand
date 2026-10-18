# Reviewed documentary asset-cost allocations

DECISION-FIN-002 authorizes development, not official valuation. This first bounded
workflow divides one accepted asset delivery line's documented amount among
explicitly described components. It retains the source quantity/unit/cost,
component quantities/units/amounts, the actual allocation basis and supporting file.
It does not allocate unrelated freight/taxes or create new asset identities.

Amounts must be supplied explicitly and total the known source amount exactly.
Do not select a pro-rata method or absorb a rounding residual automatically. If
source quantity multiplied by documented unit cost has a sub-cent remainder,
obtain a documented cost correction rather than guessing a monetary rounding rule.
Unknown source cost cannot become zero. A known zero amount remains explicit.
Component quantities describe their own units; one bundle can contain a processor
and monitor, so adding them is not a register quantity adjustment.

GSO proposes for its own accepted, non-void registered asset receipt line and
explicitly shares the proposal with the native department responsible for the
Accounting review. An independent reviewer needs both current ledger-read access
in that department and the new explicit review permission. No automatic grants or
department-name inference. Finance UAT membership denies mutation even with grants.

Lock receipt then asset then proposal. Pin source metadata, retained evidence,
approved predecessor and immutable proposal content. Append independent decision
events; stale or tampered sources/versions/history cannot acquire approval. A
successor replaces only the current documentary worksheet, preserving all original
receipt, asset, custody and decision records. Competing proposals cannot both
replace the same predecessor. Exact retries retain one proposal/file.

Approval is explicitly a documentary allocation review. No asset unit-cost,
quantity, custody, claim, journal, financial database or official valuation write
is permitted. Until applicable valuation policy is confirmed, retain this boundary
on staff screens and outputs. Cross-receipt charges, financial capacity, official
capitalization/tax/deduction treatment and journal generation are outside this
bounded workflow and remain unresolved, not silently inferred.

Retain private evidence with the two stores and proposal history. Validate path,
hash and size on the actual opened download handle. Per-file limit remains15MB;
retain at most20 proposal files/100MB per source line under the receipt lock.
Report interrupted-write orphans without deleting or rebaselining them. Require
service/HTTP scope, independent review, UAT, exact amounts, unknown/zero, source
drift, evidence integrity, native races, additive default-only migration,
desktop/mobile staff journeys and stopped synthetic recovery evidence before a
local checkpoint. Production storage/recovery and formal LGU acceptance remain
separate. Finance stays **NO-GO**; no deployment.
