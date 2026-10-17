# Custody review workbench

Published atfb2eae2 after validation on `codex/custody-review`. This is a necessary working
view for the employee movement/exit workflow; it does not complete clearance.
See [custody relationships](employee-custody-design.md), [roadmap](inventory-roadmap.md)
and [handoff](../CONTINUE.md).

## Records and scope

The GRAND-only read-only screen at `inventory:custody-review` reuses existing assets
and handoffs. It creates no employee table, migration, Finance query, custody change
or clearance finding. Explicit `inventory.view_asset` authority follows GRAND's
existing permission helper, including its assigned-department requirement. An
ungranted superuser is denied. No permissions are automatically granted.

Personal scope selects the authenticated user's explicit custodian relation across
owning offices. A current HR department change does not hide the retained assignment
or change the asset. Office scope selects only the GSO owning office, with existing
superuser scope and an explicit view grant. The personal screen does not expand
register editing, full register detail or other-office authority.

Named assignments and unlinked legacy records are separate. Names in legacy records
are never treated as identity matches. Pending incoming handoffs appear separately
from accepted custody. Retired rows remain visible as historical records. Empty or
filtered results cannot establish that an employee has no responsibilities; other
offices and unlinked source documents may still need review.

The witnessed-return release2a7bb5f adds a separate known GSO-held category and
pending returns involving the current employee. Retained return history and private
evidence use their own owner/former-custodian scope; a later custodian does not inherit
that evidence. See [returns](custody-returns.md) for the write workflow and migration.

Search uses retained labels/account snapshots and asset/property tags. Both lists
are paginated at25 rows and search length is bounded at100 characters. Responses are
not cached. GET is the only permitted method. Current HR comparisons use minimal
identity/department columns and GRAND's existing profile visibility predicate;
unavailable current HR information does not remove retained custody. Staff may see
an HR-unavailable review message for an inactive or missing profile without gaining
permission to inspect that person's private HR record.

## Review findings

The page flags a changed HR department, missing current department, changed identity
or office label, or unavailable current HR record. Matching current information is
not a clearance decision. Disabling login is not proof of employment termination.
No financial liability, deduction, payroll hold or journal entry is inferred.
This live view is not an immutable as-of report and cannot substitute for an approved
clearance/signature document.

## Remaining clearance implementation

Next implement a documented GSO review of an explicitly supplied HR request/reference,
with retained source evidence, unresolved-item notes and independent review. The
implemented witnessed-return path supports employees who can no longer sign in
without impersonating their acknowledgment. Keep return receipt,
employment status and financial liability as separate facts. A review conclusion
must recheck live custody/pending handoffs under locks and preserve its as-of source;
new later custody cannot be hidden behind an older conclusion. Resolve legacy and
other-office coverage explicitly before producing any official clearance output.

No complete HR separation source exists in the inspected GRAND profiles/users code.
Do not create one implicitly from account status or change HR/Finance tables here.

## Validation checkpoint

PASS: standalone boundary tests4/4 in0.454s; full shell70 discovered/61 executed/nine
native skips11.670s. Actual-GRAND SQLite49 tests found one incorrect test expectation:
the actual explicit-permission helper denies a user without a department. Corrected
the expectation and retained the source gate; owning GSO can still review the record.
Expanded actual-GRAND MySQL50/50 PASS14.501s, including six review cases and
retained-identity JSON search. Existing23 GRAND W036 warnings remain outside GSO.
Browser office/legacy and moved-employee personal views inspected at1440x1000 and
390x844; no overflow or duplicate IDs. Private synthetic logo/avatar assets are absent
(404s). Browsers/preview and owned native server stopped after schema cleanup. No schema or recovery-format change is introduced;
existing custody recovery remains applicable, with GET mutation checks added here.
BranchCI38947590308 passed before canonical master fast-forward/push; remote
master/tag verified. See the handoff for primary CI status.
