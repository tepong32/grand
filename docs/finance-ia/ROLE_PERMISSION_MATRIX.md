# Finance role and permission matrix

This is the F1.1 target contract. `Target` describes a complete-cycle design requirement, not proof of current implementation. Consult current feature records and CONTINUE.md for implemented scope. Role changes require explicit permission mapping rather than name matching.

## Local Form 1 signed-copy presets — 2026-10-17

The following opt-in presets are implemented locally and remain unpublished.
They extend the retained Form 1 source/copy permissions, not the financial source
editing or ledger-posting grants. See [actual scope and validation](../FINANCE_FORM1_SIGNED_COPIES_IN_PROGRESS.md).
Existing roles and the default UAT permission tuple are unchanged; no operator
assignment is performed by this implementation.

| Preset | Actual scope/actions | Exclusions |
| --- | --- | --- |
| Budget Form 1 Signed Copy Recorder | Original Budget office; record returned PDF, actual/unknown dates and custody facts; authorized original read/export | Cannot verify or issue through this preset; no source editing, JEV or cash authority |
| Budget Form 1 Signed Copy Verifier and Issuer | Original Budget office; independently verify/return and issue, together or separately; original read/export | Source makers and receipt recorders cannot decide their own evidence; no ledger/cash authority |
| Accounting Form 1 Final Package Viewer | Read/export only through actual original-source and signed-copy/final-package authority | No recording, verification or issuance; no hidden-office access |
| Treasury Form 1 Final Package Viewer | Same read/export boundary with actual Treasury source visibility | No recording, verification or issuance; no hidden-office access |

Both Budget presets retain only the existing read-only Budget audit bridge needed
for adopted historical cash. Actual paper signatories remain the named officers
and retained designation documents; these account roles do not substitute for
their signatures or require invented accounts. UAT membership denies every signed
financial mutation even when an operational preset is also granted, while
separately authorized read/export remains available. Source LGU/fund/year context
comes from the retained package, not the current site name or calendar year.

## Scope model

Every authorization decision combines:

```text
authenticated active user
AND assigned department/office scope
AND curated Finance role
AND explicit action permission
AND enabled transaction/fund/fiscal-year scope
AND current case/task state and state version
AND maker-checker, period, and exception controls
```

Superuser status or Django Admin access is not routine Finance transaction authority. Governed exemptions name the action, case/scope, authority, independent approver, reason, start/expiry, and immutable event.

## Curated roles

| Role | Default data scope | Target work | Consequential permissions | Explicit exclusions |
|---|---|---|---|---|
| Requesting-office maker | Own requesting office and cases it initiated/receives | Prepare requests, supporting references, obligation initiation, respond to returns, follow status | Create/edit own draft; submit; acknowledge return; view own case lineage | Cannot certify budget, recognize payable, prepare/post JEV, issue/release payment, or alter setup |
| Requesting-office reviewer | Own requesting office | Check and endorse locally required submissions | Review/endorse/return own-office draft where locally required | Cannot perform downstream Finance decisions |
| Budget maker | Budget scope for enabled funds/offices/years | Prepare budget versions, releases, obligation classification, adjustments, accountability work | Prepare/return/submit budget actions; reserve pending balance through service | Cannot approve own authority movement or post accounting entries |
| Budget approver/certifier | Budget scope for enabled funds/offices/years | Approve effective appropriation/allotment actions and certify obligations | Approve/reject/certify with current balance and version checks | Cannot approve own prepared action without accepted exemption |
| Accounting maker | Accounting scope for enabled funds/periods | Validate claim completeness, prepare DV/JEV, manage controlled paper return, reconcile schedules | Prepare/return/submit DV and JEV; record signed packet return; propose correction/reversal | Cannot independently approve/post own JEV or release payment |
| Accounting reviewer/poster | Accounting scope for enabled funds/periods | Independently review vouchers/JEVs, post/reverse through governed flow, close/reopen with authority | Approve/return/post/reverse; approve advice where locally assigned; close/reopen only with separate authority | Cannot rewrite posted history or silently change source facts |
| Treasury maker | Treasury scope for enabled bank/payment routes | Cash check, prepare instruments/advice, record exceptions and reconciliation work | Prepare/issue/cancel/replace; submit advice; import approved statement evidence | Cannot release own instrument where independence is required |
| Treasury releaser | Treasury scope for enabled bank/payment routes | Verify claimant/authority and release eligible instrument | Release/return; record acknowledgement; resolve stale/unclaimed action with authority | Cannot change Budget/Accounting authority or bypass finalized advice |
| Finance setup manager | Assigned configuration scope | Draft/import/master data, routes, templates, mappings, numbering policy | Prepare/submit/supersede draft setup | Cannot approve/activate own configuration |
| Finance setup approver | Assigned configuration scope | Independently approve/schedule/activate setup and readiness | Approve/return/schedule/activate with readiness checks | Cannot turn incomplete technical setup into operational authority |
| Auditor/UAT viewer | Accepted audit/UAT scope, time bound when needed | Read lineage, outputs, configuration, reconciliations, and gaps | Read/export only where separately permitted; no consequential action | Cannot submit, approve, post, issue, advise, release, configure, or reveal hidden departments |
| Finance support operator | Technical health scope, not transaction content by default | Monitor queues, outbox/inbox, backups, recovery receipts | Retry idempotent technical delivery; inspect safe diagnostics | Cannot make business decisions or read unrestricted financial content |

## Action matrix

`O` own-office/scope, `F` enabled Finance scope, `A` permitted action, `R` read only, and `—` excluded. Final local variants are LGU-confirmed through evidence.

| Capability | Req. maker | Budget maker | Budget approver | Acctg maker | Acctg reviewer | Treasury maker | Treasury releaser | Setup manager | Setup approver | Auditor/UAT |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| View/search case lineage | O | F | F | F | F | F | F | Setup-linked | Setup-linked | R |
| Initiate/submit request | A | R | R | R | R | R | R | — | — | — |
| Prepare appropriation/allotment | — | A | R | R | R | R | R | — | — | R |
| Approve appropriation/allotment | — | — | A | R | R | R | R | — | — | R |
| Prepare/certify obligation | Submit | A | A | R | R | R | R | — | — | R |
| Prepare DV/payable decision | R | R | R | A | Review | R | R | — | — | R |
| Prepare/submit JEV | R | R | R | A | Review | R | R | — | — | R |
| Post/reverse JEV | R | R | R | — | A | R | R | — | — | R |
| Prepare/cancel/replace instrument | R | R | R | R | R | A | Review | — | — | R |
| Finalize advice | R | R | R | Locally assigned | Locally assigned | Prepare | R | — | — | R |
| Release instrument | R | R | R | R | R | — | A | — | — | R |
| Reconcile/report/close | R | R | R | Prepare | Approve/post | Prepare | Approve | — | — | R |
| Prepare configuration/template | — | R | R | R | R | R | R | A | R | R |
| Approve/activate configuration | — | R | R | R | R | R | R | — | A | R |
| Consequential exemption | — | Request | Approve if authority | Request | Independent approve | Request | Independent approve | Request | Independent approve | R |

## Permission response contract

- Hidden action: user lacks general permission or object visibility; do not leak its existence.
- Visible disabled action: user can understand the next step but a known gate blocks it; state the gate and responsible role without exposing restricted details.
- Stale action: reject with a current-state explanation, preserve the user's entered safe data where possible, and refresh the case timeline.
- Denied action: return an accessible 403 and audit the denied consequential attempt without logging confidential form content.
- Read-only mode: remove mutation controls from keyboard and accessibility trees; a visual badge alone is insufficient.
