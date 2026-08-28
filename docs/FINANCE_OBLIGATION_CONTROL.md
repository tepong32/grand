# GRAND Finance obligation control and RAAO-equivalent registry

This guide covers the F4.2 synthetic implementation linking requesting-office ALOBS/ORS/OBR initiation to Budget certification, posted obligation movements, and RAAO-equivalent accountability balances. Implementation does not by itself establish the locally accepted official form, numbering, signature, or report procedure.

## Authority and evidence boundary

The design is informed by the Department of Budget and Management's public [2023 Local Government Unit Budget Operations Manual](https://www.dbm.gov.ph/wp-content/uploads/Issuances/2023/Local-Budget-Circular/LOCAL-BUDGET-CIRCULAR-NO-152-DATED-JULY-14-2023.pdf) and the Commission on Audit's [Circular No. 2016-004 and Revised Chart of Accounts materials](https://www.coa.gov.ph/wp-content/uploads/ABC-Help/Various_Transaction/2016/COA_C2016-004.pdf). These are official public references, but GRAND still requires LGU-confirmed applicability, current issuances, approved blank/redacted forms, actual numbering, signatures, registry columns, and signed synthetic examples before official acceptance.

The implemented CSV is controlled registry interchange, not a claim that GRAND already reproduces the exact accepted RAAO or ALOBS/ORS/OBR print form. Evidence labels from the Finance roadmap continue to separate official requirement, locally confirmed practice, observed eGAPS behavior, implemented GRAND behavior, and unresolved assumption.

## Roles and workflow

1. A user currently assigned to the requesting department creates one draft, choosing an operational appropriation, applicable form type, unique office request reference, date, claimant/payee, particulars, evidence reference, and signed effect total.
2. The requester adds exact immutable appropriation lines. GRAND carries fund, responsibility center, PPA, funding source, account, and expense class forward instead of accepting retyped classification.
3. Draft or Budget-returned headers and lines are guided-editable with audit evidence. Submission closes direct editing and does not yet consume allotment.
4. A different user in the owning Budget office reviews authority, classification, support, signed effects, period, executable allotment, and already certified obligations.
5. Certification assigns the controlled obligation number, repeats all balance checks while locking the affected appropriation rows, and appends one immutable checksum-backed movement per submitted line.
6. Budget may return a submitted request with a specific correction reason. The requesting office corrects the same record instead of opening an unlinked duplicate.

## Balances and safeguards

For every authorized line, GRAND keeps these distinct:

- authorized appropriation;
- released allotment;
- reserve and deferral holds;
- executable allotment (`released - held`);
- certified net obligation; and
- unobligated allotment (`executable - obligated`).

Original requests add obligations. Adjustment requests may add or reduce. Returns and cancellations only reduce. Signed control totals use the same direction as the movement effects: positive for added obligation and negative for reductions. GRAND blocks duplicate original office references, duplicate certified numbers, negative obligations, excess obligations, and later allotment reductions/holds that would fall below obligations already certified.

## Modification allowance

- **Draft or returned:** the requesting office may correct the header and schedule; before/after evidence and state versions remain visible.
- **Submitted:** direct edits are closed; Budget certifies or returns the same request.
- **Certified, before DV/check issuance:** create a linked adjustment, return, or cancellation. The original movement remains immutable.
- **After a linked DV or check is issued:** GRAND blocks an obligation-only correction and requires the later coordinated voucher, accounting, or payment reversal/cancellation path.

The current branch creates the authoritative obligation UUID link needed by the next voucher-intake phase. Until F5 integration is accepted, the existing Voucher Workbench pilot OBR remains a shadow compatibility route rather than a second authoritative budget ledger.

## RAAO-equivalent view and exports

Authorized Budget users can review appropriation, released, held, executable, obligated, and unobligated totals and drill into the exact classified lines. Registry CSV exports include authority and obligation checksums, office/form/number/reference fields, correction lineage, classified dimensions, movement effects, and current balances.

The downloaded bytes are also archived under `GRAND_EXPORT_ROOT/<department>/<user>/finance-obligation-registry/<year>/<month>/...` with an adjacent SHA-256 manifest. Copy or synchronize the whole export root with TraceSync so artifacts and manifests stay together.

## Internal How-Tos

The floating `?` card supplies separate guides for requesting-office preparation and Budget certification/RAAO reconciliation. Guide visibility follows the employee's current department and permission. Tutorial progress records only that user's private step checkmarks; it is not transaction status, approval, attendance, performance evidence, or history transferred from a previous employee.

## Acceptance evidence still required

- current locally applicable ALOBS/ORS/OBR choice and exact blank/redacted form;
- form and registry numbering ownership and issuance timing;
- preparer, Budget certification, signature, and acting-authority matrix;
- request return, rejection, adjustment, release, cancellation, and period rules;
- exact RAAO/equivalent columns, grouping, carry-forward, certification, and report template;
- signed synthetic appropriation/allotment/obligation schedules whose totals reconcile to zero unexplained difference;
- ordinary supplier and later transaction-variant replays through the accepted DV boundary.
