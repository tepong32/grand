# Redacted Finance replay checklist

Use this gate before a real-case packet is referenced in repository-safe discovery records or replayed in GRAND. The controlled source packet remains outside the repository.

## A. Authority and scope

- [ ] `REPLAY-___`, `TX-___`, fiscal year, fund, office route, and enabled scope are assigned.
- [ ] The evidence custodian approved the use, capture method, storage location, participants, and retention period.
- [ ] Read-only eGAPS actions and prohibited actions are documented.
- [ ] The packet represents the intended variant; unusual conditions are identified rather than generalized.
- [ ] Evidence, decision, and acceptance owners are named by office/role.

## B. Redaction and repository safety

- [ ] Names and identifiers of citizens, employees, suppliers, claimants, representatives, and signatories are removed or replaced consistently.
- [ ] Signature images/specimens, TINs, bank accounts, check numbers, addresses, contacts, credentials, QR bearer values, and infrastructure details are removed.
- [ ] Document properties, filenames, comments, hidden sheets/rows/columns, formulas, links, images, and revision history were inspected for residual data.
- [ ] Dates and amounts are shifted or synthesized when required while preserving the route and arithmetic relationships.
- [ ] Form titles, geometry, relative dates, status labels, attachment types, routing annotations, numbering relationships, and control equations remain usable where approved.
- [ ] Only safe IDs and locators—not the controlled artifact or secret-bearing link—enter source control.
- [ ] A second reviewer completed a disclosure check.

## C. Actual-route capture

- [ ] Every authority decision, balance movement, action, print, signature, handoff, exception, and period-end proof has an actual-step row.
- [ ] Each row has an evidence label and artifact/authority ID.
- [ ] Wet signature, recorded confirmation, system approval, and physical custody are distinguished.
- [ ] Number assignment, version, print/reprint, correction, cancellation, reversal, replacement, and reopening rules are captured.
- [ ] Appropriation, allotment, obligation, payable, ledger, deduction, cash, register, and report totals reconcile with zero unexplained difference.
- [ ] Named process owners accepted the actual route or unresolved items identify the affected scope.

## D. GRAND synthetic replay

- [ ] Separate requesting-office, Budget, Accounting maker/reviewer/poster, Treasury maker/releaser, setup approver, and UAT-viewer accounts are used as applicable.
- [ ] The UAT viewer cannot perform consequential actions.
- [ ] Each actual step maps to a GRAND screen/service, permission, event/version, balance movement, output, custody record, and next gate.
- [ ] Each comparison is classified `Exact`, `Equivalent improvement`, `Partial`, `Missing`, `Extra`, or `Unknown`, with independent severity.
- [ ] Returns and corrections preserve IDs, versions, audit events, balances, and obsolete-output lineage.
- [ ] Concurrency, duplicate submission/idempotency, period lock, department boundary, and recovery behavior are tested where relevant.
- [ ] Screenshots and outputs use synthetic data and display a non-authoritative UAT marker.

## E. Acceptance

- [ ] Critical/high gaps have an accepted implementation or operational decision.
- [ ] Expected control totals and exact form/output comparisons are attached through safe evidence IDs.
- [ ] Budget, Accounting, Treasury, requesting-office, IT, management, and audit stakeholders accept only their named enabled scope.
- [ ] Acceptance records the build/commit, configuration/template versions, replay ID, result, date, conditions, and expiry/review trigger.
- [ ] No wording claims full eGAPS equivalence or official use without the applicable roadmap exit gate and recorded cutover authority.
