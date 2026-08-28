# Finance transaction variants and payable readiness

F5.2 adds governed transaction variants and a two-office documentary-readiness gate to the F5.1 certified-obligation handoff. It is an implemented synthetic control. It does not claim that a public COA/DBM source, documentary checklist, or blank form is automatically applicable or locally accepted.

## Governed Finance Setup

- A Finance Setup release can define typed variants for ordinary suppliers/contractors, payroll, reimbursement, utilities, financial assistance, cash advances, liquidations, infrastructure/progress billings, and other locally approved cases.
- Each variant records its code, type, explanation, effectivity, and reviewed COA/DBM/local authority and applicability basis.
- Each variant owns ordered documentary rules. A rule identifies the evidence kind, whether it is required or conditional, the exact applicability condition, whether an authority-backed waiver is allowed, and the reviewed authority basis.
- A typed variant without at least one documentary rule cannot satisfy Finance Setup activation readiness. Conditional rules cannot be saved without a stated condition.
- Variants and rules are editable only while their release is a draft. Submission locks their governed content; approval, scheduling, activation, supersession, retirement, and rollback follow the release lifecycle.
- Activating a successor release does not rewrite rules already pinned to an existing payable case.

## Requesting-office preparation

When a requesting office opens a payable using an active typed variant, GRAND:

1. binds the one certified authoritative obligation exactly as F5.1 requires;
2. starts the same case in **Requesting-office payable preparation**;
3. snapshots every applicable documentary rule, label, authority, required/conditional decision, and waiver policy into the case; and
4. assigns the checklist to the requesting department rather than prematurely routing it to DV preparation.

The requester resolves every pinned rule as:

- **Present and referenced** — a source-record reference is mandatory;
- **Condition not applicable** — allowed only for a conditional rule and requires a specific decision note; or
- **Waived by reviewed authority** — allowed only when the pinned rule expressly permits a waiver and requires its specific decision/authority note.

Pending rules block submission. Required evidence must be present or use an explicitly permitted waiver. GRAND retains source references rather than copying sensitive procurement, payroll, assistance, travel, or records content into the voucher case.

## Independent Accounting decision

Submission rechecks the authoritative obligation amount/checksum and requires an active Accounting department with the explicit payable-review permission. It then routes the same case to **Accounting payable-readiness review**.

The Accounting reviewer must belong to the currently assigned Accounting office and cannot be the requesting-office preparer or submitter. The reviewer either:

- accepts the intake as payment-ready and routes it to Accounting DV preparation; or
- returns the same case to the requesting department with a required correction basis.

A returned case reopens its pinned checklist. Resubmission clears the prior current-decision fields while immutable case events retain the earlier return. DV preparation remains blocked until the typed intake is accepted, and it rechecks obligation freshness again immediately before creating the DV.

## Internal How-Tos

The floating non-modal `?` panel now provides:

- requesting-office steps for variant selection, checklist decisions, duplicate review, submission, correction, and handoff recovery; and
- Accounting steps for segregation, obligation freshness, rule-by-rule review, acceptance, and return.

Seeder-authored instructions are versioned. A newer curated version retires the prior published version and publishes a successor without overwriting prior steps or copying personal tutorial checkmarks. Those checkmarks remain private learning aids—not workflow status, approval, performance evidence, or inherited employee history.

## Authority and acceptance boundary

The included transaction kinds are configuration capabilities, not declarations that every variant is enabled or accepted locally. Each enabled variant still needs a locally reviewed authority decision, accepted documentary rules, redacted completed-case replay, and any exact accepted form/template before official use.

## Remaining F5 work

- payable recognition and obligation-to-final-claim adjustment decisions beyond the current one-to-one equal-amount route;
- one-to-many, many-to-one, partial, progress, and final-payment relationships;
- controlled payable/transaction exports in the shared TraceSync-ready archive;
- accepted forms/templates and redacted replay for ordinary-supplier and every other enabled variant.

The F5 parent exit gate remains open until every enabled variant reproduces an accepted completed case through a payment-ready, budget-supported payable.
