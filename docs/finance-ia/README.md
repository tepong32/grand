# Complete-cycle Finance information architecture

Status: F1.1 design contract and synthetic prototype. This package defines the intended navigation, role boundaries, shared-case vocabulary, and interaction model before dense Finance models are added. It does not grant transaction authority or satisfy the F1 production exit gate.

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

## Package

| Artifact | Contract |
|---|---|
| [Role and permission matrix](ROLE_PERMISSION_MATRIX.md) | Curated roles, scopes, consequential actions, and segregation expectations. |
| [Landing, case, timeline, search, and notification contract](CASE_AND_WORKSPACE_CONTRACT.md) | Shared information architecture and stable case/event fields. |
| [Status vocabulary](STATUS_VOCABULARY.md) | Separate case phase, work-task state, authority/artifact state, and exceptions. |
| [Clickable synthetic prototype](prototype/index.html) | Responsive, no-backend walkthrough of Overview, My Work, case detail, and search. |
| [Prototype notes and review script](PROTOTYPE.md) | Review boundaries, scenarios, and acceptance capture. |

## Non-negotiable boundaries

- Department membership is a data boundary; a permission does not silently widen it.
- A role exposes actions, not copied cases. The same stable case ID and event lineage survive every handoff.
- Request, appropriation, allotment, obligation, payable, accounting recognition, and cash payment remain separate authorities and amounts.
- A task status does not imply that an artifact is approved, posted, signed, advised, released, or reconciled.
- TracePoint custody and Records retention are linked evidence domains, not Finance approvals.
- Wet signatures are recorded as returned paper evidence, never represented as user digital signatures.
- Search returns only objects the user may view; result counts and suggestions must not leak hidden objects.
- The prototype is synthetic and deliberately marks unavailable/undiscovered actions. It is not an implementation promise beyond this contract.

## F1.1 review gate

Synthetic role walkthroughs must demonstrate that users see only their queues and permitted actions; the same case remains traceable across the complete cycle; statuses use the agreed vocabulary; search does not reveal restricted data; and reviewers accept the desktop and narrow layouts. Findings become `DEC-###` items in the [Finance decision log](../finance-discovery/DECISION_LOG.md). F1 remains open until permission, concurrency, recovery, identity, audit, calendar/period, numbering, health, and backup requirements are implemented and tested.
