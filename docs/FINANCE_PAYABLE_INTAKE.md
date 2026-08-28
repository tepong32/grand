# Finance payable intake and obligation handoff

F5.1 replaces the Voucher Workbench's normal entry point with a requesting-office payable intake backed by one certified F4.2 obligation. This is an implemented synthetic control, not proof that a local form, checklist, or procedure has been accepted for official use.

## Implemented slice

- The user's current department can select only its own unlinked, certified original obligation.
- GRAND pins the obligation UUID, controlled number, corrected lineage amount, checksum, and classified allocation projection into the shared case; it does not post a second Budget balance or consume a second OBR number.
- The intake references the governed payee/transaction type plus claim, invoice, procurement, delivery, inspection/acceptance, and source evidence.
- The ordinary-supplier one-to-one pilot requires the payable claim to equal the current certified obligation lineage. A changed final claim must use the governed pre-DV obligation adjustment route first.
- Similar payee/invoice/claim references create a human-review warning, not an automatic accusation or rejection.
- The core transaction database and Finance authority database use a recoverable UUID handoff. A pending or failed link cannot proceed silently; the requesting office can reconcile the same case.
- DV preparation independently rechecks the link, current lineage amount, and checksum. A later pre-DV obligation correction pauses the case for payable reconciliation.
- The department-specific floating Internal How-To explains intake, modification, duplicate review, and handoff recovery. Its checkmarks remain private tutorial progress only.

## Modification boundary

Before a DV or check is issued, correct obligation amount through a linked F4.2 adjustment, return, or cancellation, then reconcile payable evidence. After a DV/check exists, use the applicable voucher, accounting, or payment reversal/cancellation route; do not overwrite the certified obligation or pinned payable history.

## Still to do in F5

- F5.2 now implements configurable completeness and conditional-document rules, authority-backed waivers, and requesting-office/Accounting return routes; local rule acceptance and payable recognition policy remain open;
- one-to-many, many-to-one, partial, progress, and final-payment relationships where accepted;
- F5.2 can govern payroll, reimbursement, utility, financial assistance, cash advance/liquidation, infrastructure/progress billing, and other variants, but each enabled variant still needs accepted rules and a redacted replay;
- accepted COA/DBM/local templates and replay of redacted completed cases through the parent F5 exit gate;
- controlled payable/transaction exports in the shared TraceSync-ready archive where required.

The F5 parent phase remains incomplete until every enabled variant reproduces an accepted redacted case from request through a payment-ready, budget-supported payable.
