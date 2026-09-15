# Cheque exceptions: modular implementation design

Date: 2026-09-15. Status: **design, not implemented functionality or LGU acceptance**.

The user has no local procedure to supply and authorizes research-led development.
Rare cases may be resolved by people. Missing local paperwork does not block ordinary
Finance development. Preserve an evidence trail for the affected transaction and keep
bank-specific requirements configurable. Do not build a general incident platform.

## Philippine reference basis

References checked on 2026-09-15:

| Reference | Verified scope and design consequence |
| --- | --- |
| [BLGF Local Treasury Operations Manual, Book 2](https://blgf.gov.ph/wp-content/uploads/2022/10/LTOM-Book-2-E-Copy.pdf), Collection Procedures, dishonoured cheques, sections 5–6 | Describes redemption using cash or manager's/cashier's cheque, a new OR linked to the cancelled OR, ordinance-based penalties, surrender of the old OR or a loss affidavit, and Treasury custody pending redemption with documented court-directed transfers. These are proposed baseline controls for the incoming module. |
| [Quezon, Isabela Municipal Accountant citizen services](https://quezonisabela.gov.ph/office-of-the-municipal-accountant/), Issuance of Accountant's Advice for Check Issued | Describes preparation, accountant approval and delivery of advice to the bank. This is a concrete LGU example, not a universal bank acknowledgement requirement. |
| [LANDBANK weAccess terms](https://www.landbank.com/public/upload/files/weAccess_Terms%20and%20%20Conditions.pdf), service features | Describes issued-cheque status inquiry, returned-cheque inquiry and Accountant's Advice/ACIC upload for LGUs and NGAs. Supports retaining portal evidence; it does not establish an API or an emergency approval bypass. |
| [LANDBANK Citizen's Charter, 2023 third edition](https://www.landbank.com/images/inner_template/1703647412_Citizens%20Charter_2023_3rd%20edition_website_conso.pdf), printed B-108–109 | Describes branch coordination for MDS advice, adjustment, cancellation and negotiation. Its described MDS context is national-government disbursement; do not copy it as an LGU regular-account rule. |

BLGF and municipal pages were available through indexed official-source text; direct
retrieval failed. LANDBANK's charter was readable in full. No source establishes this
LGU's currently accepted account codes, penalty rates, deadlines, signatories or bank
contract. Those remain configuration/rollout checks, not prerequisites for implementing
the modules. The designs below are GRAND engineering decisions informed by these
references. Do not present them as prescribed Philippine law. NGA accounting examples
must not silently determine LGU entries.

## A. Outgoing cheque presented before advice completion

Example: a payee reports being at the bank while advice is still awaiting approval.
Record a **presentation report** against the original instrument and case. Treasury
coordinates with Accounting and the servicing bank; GRAND records their actual responses.
Ordinary approval/submission/acknowledgement continues through the existing advice module.

Separate three facts: reported presentation, verified bank disposition and system
authorization. A report establishes neither payment nor a failed financial instrument.

| Bank outcome | Proposed system handling |
| --- | --- |
| Unconfirmed or pending | Keep the issue open with the responsible office and next action. No payment, cancellation, reversal or advice-state change. |
| Not paid; advice subsequently completed | Link actual advice/submission/response evidence and independent resolution. Preserve the earlier delay. Do not record a second claimant release. |
| Paid/negotiated despite incomplete system evidence | Retain bank debit/statement evidence and actual effective date. Accounting reconciles against the original payment JEV or governed no-entry decision. Block replacement/cancellation actions that could pay twice until reviewed resolution. Never backdate approval or manufacture acknowledgement. |
| Bank actually returned the instrument | Link the existing returned-instrument review when its source preconditions are satisfied. An unreleased/out-of-system case stays under explicit reconciliation; do not fake release merely to enter that route. |
| Wrong instrument or mistaken report | Independent reasoned dismissal retains the report and its evidence. |

### Implementation contract

Add a narrow `PaymentPresentationReport` model and `vouchers/payment_presentations.py`.
Use `PaymentInstrument`/`VoucherCase` foreign keys; optional advice version; immutable
instrument/advice snapshots and checksums; observed/effective dates separate from
recorded-at timestamps; reporter; source evidence; bank disposition; independent reviewer;
and resolution links. Keep original report immutable; later evidence and decisions are
append-only child records with sequential versions. Do not reuse the existing
`PaymentInstrumentException.RETURNED` merely for a payee's report.

Treasury captures; Accounting reviews verified disposition and closes. Add explicit
permissions through existing role setup, preserving office scope and UAT mutation denial.
Display on the instrument/case and in the existing advice workspace. No messaging,
bank credentials, automated calls or blanket release override is included.

Capture/review lock the existing case, then instrument, before report rows. Competing
capture must produce one active report per instrument; use a MySQL-compatible unique
active key as well as locks. Add reports to release, cancellation and replacement
validation only where verified unresolved bank evidence conflicts with that action.
An unverified complaint alone must not silently cancel a payable or assert settlement.
Audit the existing advice batch/case lock order before making any cross-service mutation;
recording a report should not mutate the advice batch.

## B. Incoming cheque dishonour and accounting disposition

Add `CollectionChequeReturn` and `vouchers/cheque_returns.py` beside clearing. Treasury
captures the original receipt, cheque identity, whole-deposit allocation, bank debit memo,
reason and actual debit date. Accounting independently verifies and approves the financial
treatment. A previously approved clearance remains historical evidence: a later bank
return is a new event, not a withdrawal pretending clearance never occurred.

Keep bank return, source-entry error, and bank's reversal of its own mistaken debit as
different event kinds. Require an exact original bank/receipt/deposit link, amount and
dated source evidence. Handle multi-charge receipts by preserving each original component;
never reverse an entire combined deposit containing unrelated receipts. Unsupported
partial bank debits stay under explicit reconciliation rather than becoming invented
partial-cheque settlement.

Reuse reviewed Finance Setup rules and `CollectionPostingRequest` materialization,
independent posting and cross-store reconciliation. Add explicit return event/source types
through Finance rule validation, journal source verification, manual-reversal protection
and source outputs together. Pin the reviewed release, rule, accounts, source lines and
cash-flow purposes in the approval. The ledger uses the actual bank effect and separately
reviewed counterpart allocations, not a hard-coded generic receivable or an automatic
mirror of both original receipt and deposit.

Each rule must state its supported collection category and authority/applicability
reference. A proposed recipe without reviewed applicable treatment can be saved and
reviewed but cannot post. This blocks only that posting; ordinary collections continue.
Fees require their own evidenced allocations; no residual amount is silently called a fee.

Lock Treasury department then collection sources in stable order; for an officer advance,
lock the default case first. Use the same locks as clearing, source correction and redemption.
Materialization locks the Finance fund/original source lines and uses a deterministic
request identity. A retry recovers only identical journal evidence. Pending return/reversal
holds prevent incompatible corrections or redemption; failed cross-store reconciliation
remains visible and cannot authorize a second posting.

## C. Redemption and instrument custody

Add `vouchers/cheque_redemptions.py` as an adapter over receipt capture, charges and bank
routing, linked to an independently posted/reconciled return. Retain original OR, new OR,
return approval and remaining principal. Reserve the obligation once across concurrent
redemptions. Start with full principal settlement; treat disputed partial settlement as
an explicit unsupported case, not completion. Penalties use separate reviewed collection
components and an applicable ordinance reference; no inferred rate or fine.

The baseline methods are cash and explicitly identified manager's/cashier's cheque.
The latter requires a cheque subtype extension; do not classify an ordinary personal
cheque as equivalent. Receipt of another cheque is not proof of clearing. New source
receipts and their corrections retain the redemption link so the obligation cannot be
silently reopened, paid twice or recognized twice by two routes.

Reuse TracePoint for the physical cheque and linked evidence packet. Record actual
custodian, transfer, receipt surrender/loss-affidavit evidence and eventual handover.
Financial settlement and physical handover have separate statuses. A court-directed
transfer retains authority and receiving evidence. Electronic approval never asserts a
physical act occurred. Source read/export permissions also apply to linked evidence.

Officer cheque refunds remain a separate dependent checkpoint: capacity is released
only at the supported effective settlement/clearing boundary and restored by actual
return/correction lineage, under existing case-first dated capacity checks. Ordinary
cheque functionality must not wait for this specialized extension.

## Checkpoints and acceptance examples

1. **Presentation reports:** evidence capture, independent resolution and duplicate-payment
   protection; no new journals. Test early presentation with bank pending, later regular
   advice, mistaken report and verified payment without prior acknowledgement.
2. **Incoming return:** whole-source bank debit, reviewed recipe, independent JEV and
   recovery. Demonstrate a 1,000 receipt in a 3,000 deposit: only its 1,000 bank effect
   and reviewed counterpart change; the other receipts remain intact.
3. **Redemption/custody:** new linked receipt, principal reservation, separately authorized
   penalty and actual handover. Replay cash and manager's-cheque redemption; prove a
   returned replacement does not erase the original collection/return history.
4. **Officer refund extension:** dated capacity before clearing, after clearing, after
   dishonour and after replacement redemption, including later-date commitments.

For each checkpoint test independent actors, wrong office, UAT plus operational grants,
stale version, duplicate submit, one-cent source drift, immutable earlier exports and
interrupted default/Finance reconciliation. Native races must cover conflicting reports,
report versus replacement, return versus clearing/correction, and competing redemption.
Review dated cash-flow/ledger output and bank reconciliation, not just model status.

Run affected SQLite tests first, then fresh two-store MySQL for financial persistence
and races; broaden across vouchers, Accounting, Finance rules and reporting where changed.
Browser checks cover the new ordinary-user forms. Each release records actual outcomes.
The examples above are **planned tests, not passing results**.

Keep rare manual cases visible with owner, evidence, next action and reason for resolution.
Do not let them indefinitely displace mixed instruments, remaining ordinary Finance
functions, actual inventory or required outputs. Exact local forms and operational
acceptance remain later gates. Existing bank-advice behavior is documented in
[Finance bank advice](FINANCE_BANK_ADVICE.md); this design does not change it.

## Validation of this design

Reviewed existing `vouchers/advice.py`, instrument exceptions, collection/clearing source
contracts and repository continuity. Documentation links and whitespace are checked during
publication. Runtime/native/browser suites: **NOT RUN - OUT OF SCOPE** for this design-only
change. No schema, ledger, operator database, bank or production action is authorized by
marking this document complete.
