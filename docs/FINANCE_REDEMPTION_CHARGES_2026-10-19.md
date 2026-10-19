# Assessed charges with ordinary returned-cheque redemption

Development contract, 2026-10-19; implements the ordinary-collection component
extension of D-096/D-099. Validation/checkpoint evidence belongs to CONTINUE.md.
Finance remains **NO-GO**. This is neither Accounting approval nor prescribed
receipt/form, production, recovery or LGU operational acceptance.

## Source and interpretation

[BLGF LTOM Book II, section85.5(a–c)](https://blgf.gov.ph/wp-content/uploads/2022/10/LTOM-Book-2-E-Copy.pdf)
describes redemption by cash or manager's/cashier's cheque, a new receipt, and
applicable delayed-payment penalties in addition to principal under an approved
LGU ordinance. Official indexed section text was retrieved on October19; direct
paginated PDF retrieval subsequently returned403. This is research evidence,
not proof of this LGU's applicable ordinance, rates or Accounting treatment.

Implementation inference: combine explicitly assessed components in one source
receipt using existing approved collection recipes, retaining principal separately.
Never derive a charge from an unexplained balance, select a statutory rate, install
an ordinance, invent an account or treat reference text as formal policy approval.
Actual applicability, amount basis, reviewed setup and independent Accounting
decision remain required for each real transaction. Synthetic references in tests
establish software behavior only.

## Bounded behavior

- The clerk sees the exact original principal and enters one actual total. Each
  optional additional component has a distinct reviewed collection type, positive
  exact-cent amount, applicable authority and actual assessment reference.
- Total must equal full original principal plus all listed charges. Charge recipes
  must belong to the same Accounting department/setup and original fund, using
  the same actual collection asset. No partial principal, inferred fee or bank
  transfer redemption is introduced.
- Principal still credits only the selected original return receivable. Additional
  revenue/liability credits and their cash-flow purposes come only from the
  selected ordinary collection recipes. Mixed original purposes retain their
  exact principal amounts; cash debits aggregate only identical purposes.
- Independent review re-resolves every charge recipe and compares retained
  metadata. Changed recipes require rejection and a new source. Posting uses the
  approved snapshots, even after later setup edits. Existing source/request/journal
  checksums and financial-row checks remain mandatory.
- The full receipt total follows existing deposit/whole-cheque clearing and bank
  return controls. Another dishonour creates a separate whole-return obligation;
  it cannot reopen the earlier principal or recognize the old charges again.
- Exact receipt correction reverses principal and charges together. Reconciliation
  retires the existing principal hold; a pending or later-dated correction cannot
  authorize an earlier or duplicate redemption. Historical sources and issued
  copies stay intact.
- Details and newly generated immutable internal copies show assessed charges,
  authority and assessment references. Existing read/export authority applies;
  these copies are not official receipts.

No models, migrations, permissions, database routing, new posting-rule instruction
types or third-party dependencies. The existing Treasury/source and Finance locks,
maker-checker, UAT mutation denial and retained original-OR evidence remain.

Validation uncovered a pre-existing chronology fixture failure on native MySQL:
unchanged parent206 repeats produced identical approval/scheduling timestamps,
which legitimately sort by stable task identity. The one chronology test now
records explicit successive action times and asserts their strict order. Every
original assertion and the separate equal-time pagination test remain. Production
task ordering and source history are unchanged; this is fixture stabilization,
not an assertion waiver or inherited-test migration. CONTINUE.md retains failed
gate, parent reproduction and subsequent exact-source validation evidence.

## Explicit remaining boundaries

Officer-advance replacement receipts remain principal-only. The service rejects
additional charges before reserving or writing a source, so receipt totals cannot
silently reduce advance balances. Ordinary separate authorized collections remain
available. A combined officer charge workflow needs its own dated-capacity and
subsidiary design/validation; this checkpoint does not claim it.

External cheque delivery/court authority, disputed partial settlement, actual LGU
ordinance/applicability, exact prescribed outputs, source-record qualification,
production storage/recovery and formal acceptance remain open. Real historical
imports remain deferred. No publication or deployment is authorized by this slice.
