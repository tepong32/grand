# Complete-cycle Finance information architecture

Status: F1.1 design contract and synthetic prototype, with the narrow F1.2 permission-shaped Finance entry, F1.3 shared-case finder, and F1.4 private saved case views implemented. This package defines the intended navigation, role boundaries, shared-case vocabulary, and interaction model. These controls do not grant transaction authority or satisfy the F1 production exit gate.

## Design outcome

GRAND Finance has one entry point and one case lineage. A user lands on the work their role can perform, while authorized search and the case timeline expose the same underlying history without copying the case into Budget, Accounting, and Treasury records.

```text
Finance overview
  -> My Work (permission-derived tasks)
  -> Cases (authorized cross-cycle search)
  -> Reports and reconciliation
  -> Setup and controls

One case
  -> authority chain
  -> current task and accountable office
  -> documents and controlled outputs
  -> accounting and payment
  -> append-only timeline and corrections
```

The navigation labels remain stable across roles. Counts, saved views, actions, supporting guidance, and accessible detail are role-shaped.

The implemented `/finance/` entry now applies the first part of this contract without inventing a second queue. It presents plain cards for existing Budget, Voucher, Accounting, Reporting, setup, discovery, and field workspaces only when their current access checks allow them. Existing workspace links remain available in the account drawer, while the top bar uses one Finance destination. Voucher-authorized users can hand a controlled-reference or safe-token search into the existing permission-filtered shared-case workbench and keep up to 25 human-named private filter shortcuts. Every shortcut is rechecked against current scope; no separate index, hidden-object count, assignment, or suggestion is created. See [Finance operations entry](../FINANCE_OPERATIONS_ENTRY.md).

## Package

| Artifact | Contract |
|---|---|
| [Role and permission matrix](ROLE_PERMISSION_MATRIX.md) | Curated roles, scopes, consequential actions, and segregation expectations. |
| [Landing, case, timeline, search, and notification contract](CASE_AND_WORKSPACE_CONTRACT.md) | Shared information architecture and stable case/event fields. |
| [Status vocabulary](STATUS_VOCABULARY.md) | Separate case phase, work-task state, authority/artifact state, and exceptions. |
| [Clickable synthetic prototype](prototype/index.html) | Responsive, no-backend walkthrough of Overview, My Work, case detail, and search. |
| [Prototype notes and review script](PROTOTYPE.md) | Review boundaries, scenarios, and acceptance capture. |
| [Implemented Finance operations entry](../FINANCE_OPERATIONS_ENTRY.md) | Permission composition, navigation, shared-case finder, private saved views, Internal How-To, and authority boundaries for F1.2–F1.4. |

## Non-negotiable boundaries

- Department membership is a data boundary; a permission does not silently widen it.
- A role exposes actions, not copied cases. The same stable case ID and event lineage survive every handoff.
- Request, appropriation, allotment, obligation, payable, accounting recognition, and cash payment remain separate authorities and amounts.
- A task status does not imply that an artifact is approved, posted, signed, advised, released, or reconciled.
- TracePoint custody and Records retention are linked evidence domains, not Finance approvals.
- Wet signatures are recorded as returned paper evidence, never represented as user digital signatures.
- Search returns only objects the user may view; result counts and suggestions must not leak hidden objects.
- The prototype is synthetic and deliberately marks unavailable/undiscovered actions. It is not an implementation promise beyond this contract.

## F1 review gate

Synthetic and named-user walkthroughs must demonstrate that users see only their entry cards, queues, and permitted actions; the same case remains traceable across the complete cycle; statuses use the agreed vocabulary; search does not reveal restricted data; and reviewers accept the desktop and narrow layouts. Findings become governed Finance discovery decisions and, where useful during preparation, `DEC-###` worksheet items. F1 remains open until permission, concurrency, recovery, identity, audit, calendar/period, numbering, health, backup, supported-device/accessibility, and local acceptance requirements are implemented and tested.
