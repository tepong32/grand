# Recognition journal inspection

The optional GRAND adapter exposes a read-only recognition-source page from receipt
claim support. It uses GRAND's existing `VoucherPostingRequest` and `JournalEntry`
identities. No tables, migrations, ledger writes, allocation reservations or new
permissions are introduced. The standalone shell does not install this adapter.

Access requires existing attribution/case visibility plus the Finance owner's
assigned department and explicit `accounting.view_general_ledger` grant. GSO claim
access alone does not grant access to the Accounting ledger. Superuser status does
not substitute for this grant. The route accepts GET only and disables caching.

The page lists recognition requests, with twenty requests per page. Posted debit
lines appear only when a request has a bound journal UUID and GRAND's own
`accounting.posted_evidence.verify_source_link` reproduces the source identity,
payload/rule checksums, journal reference/date and voucher case. Posting actor,
stored audit totals, exact balanced line totals and same-owner dimensions are
checked separately: GRAND's posting-handoff helper requires posting authority and
must not be invoked with fabricated authority merely to permit a read.

Draft, unbound, inconsistent and actively reversed sources show an explanation
without debit details. A draft or submitted reversal also requires Accounting
review; only voided reversals are excluded from that check, matching GRAND's
register treatment. Credit lines and private source payloads are not rendered.
All observed debit types remain labelled; a debit is not automatically an asset
cost. Payment requests are not represented as recognition allocations.

This is a live observation across two databases. It does not retain an approval,
certify cross-store consistency, establish cost or allocate any journal amount to
a receipt. The separate [reviewed mapping workflow](receipt-journal-mappings.md)
selects the journal UUID and line sequence, retains and revalidates evidence,
tracks debit and claim capacities and preserves correction history. Do not
infer that mapping from account codes, matching amounts or descriptive text.

Source baseline: GRAND `32ab04669da05b868f6c8b8ff37e0f71b3805555`, including
`vouchers/posting.py`, `accounting/posted_evidence.py`, `accounting/access.py`,
`accounting/journal_exports.py` and the actual models. Review this boundary against
parallel Finance changes before integration. No Finance production acceptance or
operator grants are implied. See [data design](grand-integration-design.md),
[claim support](claim-attribution.md) and [validation](validation-2026-10-16.md).
