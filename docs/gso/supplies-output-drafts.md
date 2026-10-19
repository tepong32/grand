# RPCI and RSMI working preparation

Development 2026-10-19 adds Supplies → Prepare RPCI / Prepare RSMI → editable
five-line preview → browser Print / Save as PDF. These are supplied, unsigned
preparation sheets under the owner's existing placeholder direction, not accepted
municipal forms, issued archives or complete certified reports. Actual validation
and local checkpoint/publication state belong to [CONTINUE](../../CONTINUE.md).

## Access and data boundary

Require the existing explicit stock-read grant and current GSO scope on GET and
POST. UAT read remains allowed; ordinary-office stock readers, ungranted implicit
superusers and asset/export-only grants cannot prepare these drafts. No asset-read
or export grant is necessary because no stored asset/count/movement data is copied.
The Supplies entry and new pages link to GRAND home without asset-dashboard access.
Existing scoped movement/count copies and CSV exports retain their separate grants.

Entries are nonpersistent, private/no-store and protected by the existing login/
CSRF/method boundaries. No inventory, count, evidence, custody, HR or Finance source
is changed. No new model, migration, permission, financial recipe or archive is
introduced. A saved browser PDF belongs only in approved office storage.

## Supplied facts and arithmetic

RPCI accepts inventory type/as-of and officer placeholders, stock references,
descriptions/units, supplied unit values, card/count quantities, signed difference
values and remarks. Count minus stock card is calculated only when both quantities
are present. Zero is explicit; blank physical quantity stays unknown. Do not infer
counted zero from a missing finding or take today's ledger balance as a past count.
The existing RPCPPE line validation is reused with stock terminology; its default
property-card behavior remains unchanged and has dependent regression coverage.

RSMI accepts supplied report/control number, period, source dates/RIS references,
stock descriptions/numbers/units, receiving office/recipient, issue quantities,
unit costs, line amounts and remarks. A stated period cannot end before it starts.
Source dates are entered facts, not inferred GRAND recording dates; no source
cohort is automatically selected or declared complete. Returns/adjustments are not
silently netted into original issues.

Amounts remain supplied rather than calculated. When all corresponding quantities
and monetary inputs are known, check exact Decimal arithmetic, including explicit
zero, without inferring a rounding rule. Leave unresolved values blank for review.
No unlike-item/unit total, approved valuation, classification/account mapping,
official stock/report number, signature, journal or certification is generated.

## Source and acceptance limits

The previously retained [QC examples](coa-requirements.md#count-output-example-reviewed--2026-10-18)
and [SSMI/procedure review](coa-requirements.md#supplies-output-example-reviewed--2026-10-18)
were rechecked byte-for-byte and visually inspected. Their fields inform a bounded
working preparation, not target-LGU adoption. The QC SSMI grid, printed names,
approval roles and annex label were not copied as municipal policy or represented
as an accepted RSMI layout. No new applicable issuance/effectivity claim is made.

Larger complete reports, automatic reviewed-source population, archival issuance,
exact local fields/layout/revision/numbering/signatories, rounding/valuation and
formal acceptance remain separate requirements. Five supplied lines do not prove
a complete inventory or monthly issuance report. The browser example fits one
A4 landscape page; longer supplied content may need additional pages. Synthetic
layout evidence does not qualify a local printer, production storage or recovery.
Finance remains NO-GO; no deployment or production operation is authorized.
