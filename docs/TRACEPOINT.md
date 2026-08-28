# TracePoint physical custody

Release status: delivered in GRAND `0.6.6` through the reviewed `0.6.0`–`0.6.6` patch train.

TracePoint is GRAND's physical-document custody capability. It records who is responsible for a tagged paper packet, when responsibility changed, and whether the packet merely reached its destination or the underlying work was completed.

TracePoint does not replace the Records registry, Reporting, or Assistance. Those modules remain authoritative for their digital files and business workflows. TracePoint links to them when useful and adds an auditable trail for the physical bundle.

## Initial operating model

1. An authorized preparer registers a packet, describes its contents, chooses its final department or employee destination, and optionally links an approved report or departmental record.
2. For a bundle of separate vouchers, the preparer can register each voucher under a stable `TPV-...` reference and record its expected attachments. Simple and historical packets can continue using only the packet-level manifest.
3. The preparer may define plain-language office checkpoints for review, signature, approval, certification, or release. The same office may appear more than once for different work.
4. GRAND produces one stable, opaque packet QR label. The label contains no employee, citizen, or document details.
5. The preparer scans the packet label to activate it and becomes its first recorded holder.
6. At every handoff, the packet QR and the receiving employee's daily QR are scanned at a shared workstation, tablet, or authorized phone.
7. GRAND shows the packet, current holder, intended receiver, possible checkpoint, and destination for confirmation. Scanning alone never transfers custody.
8. Confirmation appends a receipt to the custody ledger and atomically changes the current holder. A matching checkpoint is completed only when selected on that receipt.
9. Arrival at the declared destination remains **Active** by default, because the papers may be there only for signing or onward routing. The receiving station must deliberately select terminal delivery, and required checkpoints must already be completed or formally skipped, before GRAND marks the packet **Delivered**.
10. An authorized employee separately marks it **Completed** when the associated work is actually finished.

Checkpoints are operational guidance, not a rigid route engine: unplanned real-world handoffs remain recordable. Required checkpoints govern only terminal delivery. This preserves flexibility while making known signature and review stops visible.

When vouchers physically separate, the current holder may split selected voucher items into a child packet with its own packet QR. Pending checkpoints follow the child packet. A holder may later rebundle selected vouchers into another compatible packet when both bundles share the same origin and workflow state—and, once active, the same current holder. Every item move is append-only on both packet histories.

## Identity and QR rules

- A packet keeps one stable public tracking identity for its lifetime. Opening it requires authentication and object-level access; possession of its QR is not authorization.
- Each active employee can receive one short-lived QR credential for the current local government business day. The credential is random, opaque, stored only as a hash, and immediately invalid when revoked, replaced, expired, or when the employee is no longer eligible.
- The authenticated `User` with an active `EmployeeProfile` is the canonical employee identity. A QR is a temporary proof used by that identity, not a second employee account.
- Daily credentials never encode an employee number, name, department, role, date, or predictable signature.
- Packet and employee QRs remain distinct from Assistance secure-edit QR codes.
- Shared receiving stations are a first-class workflow. Personal phones are optional, not required.

A photographed daily QR can still be replayed during its validity window. Short validity, revocation, confirmation, authenticated stations, rate limits, and designated-recipient checks reduce that risk. Sensitive packets can require stricter confirmation, but the first release does not claim biometric proof.

## Packet and ledger contract

A tracked packet records:

- an opaque public identifier and human-readable tracking reference;
- origin department and preparer;
- final destination department and optional employee;
- current holder and current department;
- a plain-language contents manifest and optional expected document/page count;
- confidentiality level and operational status;
- optional links to one governed report run and/or department record;
- optional parent/child packet lineage for physical splits;
- optional individually identified voucher items with attachment/page expectations and immutable movement entries;
- ordered, repeatable office checkpoints with purpose, responsible office or employee, requirement status, and completion/exception evidence;
- timestamps and a state version used to reject stale concurrent updates.

Every confirmed handoff appends an immutable ledger entry containing its sequence, prior and receiving employees, department and position snapshots, server timestamp, status before and after, scan-session/idempotency identity, and optional receipt note. Historical handoffs are never edited or deleted. Corrections and discrepancies are new events that reference the original entry and explain what changed.

Duplicate submissions, repeated scans, and two stations attempting the same transfer must not produce two receipts. Implementation uses short-lived scan sessions, idempotency keys, database transactions, row locking, and state-version checks.

## Status meanings

| Status | Meaning |
| --- | --- |
| Draft | Registered but its physical label has not been activated by the preparer. |
| Active | In physical circulation with a recorded current holder. |
| Delivered | The declared final destination deliberately confirmed terminal receipt after required checkpoints were completed or formally skipped. |
| Completed | Authorized staff confirmed the underlying work is finished. |
| On hold | Movement is intentionally paused with a recorded reason. |
| Cancelled | Tracking ended before delivery, with an auditable reason. |

Delivered and Completed are intentionally separate. A packet can be physically present at Accounting, for example, while review or payment work remains unfinished.

## Access and governance

Eligibility to receive a normal internal packet requires an active authenticated user, an active employee profile, and a current department assignment. Explicit permissions govern workspace access, preparation, label printing, completion, exception resolution, credential revocation, and restricted packets.

Department membership remains a boundary. Origin staff, the current holder, the declared recipient, and explicitly authorized oversight roles receive only the access needed for their part of the workflow. Cross-department receipt does not expose every record owned by the origin department. Linked reports and records keep their own download and confidentiality permissions.

The ledger uses server time. User-entered notes cannot replace custody timestamps. All activation, receipt, delivery, completion, hold, cancellation, correction, credential replacement, and revocation actions are audited.

## Patch delivery train

TracePoint is delivered as a reviewed `0.6.x` patch train. Here, patch numbers identify safe operational slices rather than claiming that every slice is a bug-only Semantic Versioning release.

| Version | Branch | Delivery |
| --- | --- | --- |
| 0.6.0 | `codex/tracepoint-custody-planning` | Contract, threat boundaries, status model, permissions, and operator workflow. |
| 0.6.1 | `codex/tracepoint-packet-foundation` | Packet identity, destinations, governed source links, permissions, migrations, and tests. |
| 0.6.2 | `codex/tracepoint-qr-credentials` | Stable packet labels, daily employee credentials, expiry, replacement, and revocation. |
| 0.6.3 | `codex/tracepoint-handoff-ledger` | Scan sessions, confirmation, atomic handoffs, idempotency, concurrency protection, and immutable receipts. |
| 0.6.4 | `codex/tracepoint-delivery-controls` | Delivery/completion, holds, discrepancies, append-only corrections, and exception governance. |
| 0.6.5 | `codex/tracepoint-operations-ui` | Plain-language operational UI, timelines, dashboards, print labels, synthetic QA, and showcase assets. |
| 0.6.6 | `codex/tracepoint-batches-checkpoints` | Stable voucher manifests, audited split/rebundle lineage, repeatable checkpoints, temporary destination visits, and deliberate terminal delivery. |

Every slice receives focused tests, Django checks, migration-drift checks, the complete suite, synthetic screenshots where applicable, a detailed commit, branch review, CI, and merge before the next branch begins. The repository `VERSION` file advances with each slice; the completed train receives a versioned release commit and annotated Git tag after final verification.

## Operator quick start

1. An authorized preparer opens **TracePoint**, selects **Prepare a packet**, records a plain-language manifest and final office or employee, and optionally adds individual vouchers and repeated office checkpoints before printing the stable packet label.
2. The preparer opens **My daily code**. At a shared receiving station, staff scan the packet label first and the preparer's daily code second, compare the physical bundle with the confirmation screen, and confirm activation.
3. Every receiving employee repeats the same packet-code, employee-code, review, and confirmation sequence. They select a checkpoint only when its work was actually done. The real route may still pass through an unplanned eligible employee.
4. A visit to the destination for a signature is confirmed as an ordinary receipt and remains **Active**. On the later return that truly ends movement, the receiver selects **This is the final, terminal delivery**. An authorized destination employee marks it **Completed** only after the underlying office work is finished.
5. If vouchers physically separate, the current holder selects the affected items, creates a child packet, prints its new packet label, and continues both trails independently. Rebundling is allowed only while compatible packets are in the same responsible employee's custody.
6. Missing contents, damage, or a wrong route are recorded as discrepancies. Authorized supervisors resolve issues, formally skip an impossible checkpoint, or append a custody correction; they never rewrite an earlier receipt.

Daily codes are bearer credentials for the current local day. Employees should display them only during a handoff, replace or revoke a photographed or exposed code immediately, and never send them through ordinary chat. Production access logs should avoid retaining full scan URLs because those URLs contain the short-lived bearer token.

## Rollout guidance

Begin with one repeatable route, such as MSWD-prepared voucher bundles received by Accounting. Place the shared station where the physical receiving step already happens, name the person responsible for exceptions, and compare TracePoint against the paper log during the pilot. Expand only after employees can complete the two-code confirmation reliably and management has agreed on label placement, packet manifests, end-of-day code practice, and completion responsibility.

## GRAND Finance integration roadmap

TracePoint's general custody engine is implemented, but its current Voucher Workbench link is optional and manual. F6 and F8 of the [GRAND Finance complete-cycle roadmap](FINANCE_ROADMAP.md) will add a governed finance integration after the LGU confirms the physical route.

The target behavior is:

1. GRAND freezes the exact finance document version and packet manifest at the approved print/assembly point.
2. The financial case creates or requires a verified TracePoint packet/item link without copying voucher amounts or confidential finance fields into the custody domain.
3. Required office/signature checkpoints are derived from the pinned transaction route; real unplanned handoffs remain recordable.
4. A finance action may require evidence that the right printed version reached or returned from an approved checkpoint, but TracePoint never approves the budget, voucher, JEV, advice, or payment.
5. A material finance correction supersedes the printed version and starts the approved reprint/re-sign route while retaining the prior custody history.
6. Treasury release and terminal packet delivery/completion remain separate events and reconcile to the financial release record.

The integration must preserve least privilege: a custody receiver can confirm possession without gaining access to voucher amounts, attachments, accounting entries, or payment authority.

## Deferred scope

The initial train deliberately excludes GPS surveillance, biometrics, public tracking, required personal phones, route enforcement, offline synchronization, warehouse inventory, and one-click bulk receipt. Individual voucher references identify bundled contents but do not create a separate QR on every voucher; a new packet QR is created only when items physically split into a child packet.
