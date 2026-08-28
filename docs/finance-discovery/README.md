# Finance evidence register and interview kit

Status: F0.1 discovery package. These files are templates and repository-safe public/project evidence; they are not proof that an LGU process has been accepted.

Use this package to turn interviews, approved references, redacted artifacts, and synthetic replays into traceable Finance requirements. The canonical scope and evidence labels remain in the [Finance complete-cycle roadmap](../FINANCE_ROADMAP.md), while the [process discovery protocol](../FINANCE_PROCESS_DISCOVERY.md) controls walkthrough order and acceptance.

## Package

| Artifact | Purpose |
|---|---|
| [Evidence register](EVIDENCE_REGISTER.md) | Index authorities and artifacts without storing confidential material. |
| [Interview kit](INTERVIEW_KIT.md) | Prepare and run office interviews in the order authority and paper actually move. |
| [Transaction catalog](TRANSACTION_CATALOG.md) | Separate ordinary supplier, payroll, reimbursement, and other locally approved variants. |
| [Role and signature matrix](ROLE_SIGNATURE_MATRIX.md) | Distinguish work, approval, wet signature, custody, and system access by transaction type. |
| [Actual-step worksheet](ACTUAL_STEP_WORKSHEET.md) | Map every action, balance movement, print, signature, handoff, exception, and GRAND replay result. |
| [Decision log](DECISION_LOG.md) | Keep unresolved policy choices visible with owners, evidence needs, and affected scope. |
| [Redacted replay checklist](REDACTED_REPLAY_CHECKLIST.md) | Approve a safe packet, reconcile its control totals, and replay it with synthetic users. |

## Repository-safe handling

Commit only templates, public authorities, approved blank forms, synthetic examples, and summaries that cannot identify a person, supplier, claimant, account, check, credential, or protected infrastructure. The register may point to an access-controlled evidence location, but it must not contain the confidential artifact itself or a secret-bearing URL.

Use stable IDs:

- `EV-###` for authorities and artifacts;
- `TX-###` for transaction variants;
- `STEP-<TX>-###` for actual steps;
- `DEC-###` for decisions and unresolved questions;
- `REPLAY-###` for replay sessions.

Never renumber an issued ID. Mark a superseded entry and link its replacement.

## Working sequence

1. Name the process owner, interviewer, recorder, evidence custodian, and acceptance reviewers.
2. Add anticipated authorities and artifacts to the evidence register before the session.
3. Confirm a transaction variant in the catalog; do not reuse the ordinary-supplier route by default.
4. Record the actual route in the actual-step worksheet, including returns and repeated visits.
5. Record role, wet-signature, and custody distinctions in the matrix.
6. Put disagreements and missing authority in the decision log instead of choosing an answer silently.
7. Approve and redact a replay packet, then replay the same facts with separate synthetic roles.
8. Obtain named-office acceptance for the enabled scope and retain the acceptance reference as evidence.

## F0.1 completion rule

The templates are delivered by this package. F0 itself remains open until field evidence gives every required step, field, balance, certification, signature, number, output, and exception an owner, authority/evidence label, and acceptance example. An unresolved item blocks only the transaction type, office, fiscal year, output, or action recorded in its affected-scope field.
