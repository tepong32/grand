# Finance role and permission matrix

This is the F1.1 target contract. `Target` means required by the complete-cycle design, not currently implemented. The existing Voucher Workbench roles remain a shadow prototype and must migrate through explicit permission mapping rather than name matching.

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
