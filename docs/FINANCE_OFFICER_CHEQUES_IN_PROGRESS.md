# Officer cheque refund reservations and clearing

2026-09-15: validated v0.7.114 development checkpoint on `codex/finance-officer-cheques` in
`C:/Users/Administrator/.codex/worktrees/grand-cheque-components`, based on pushed
v0.7.113 `a3bd6c8` ([draft PR #74](https://github.com/tepong32/grand/pull/74)).
This is not master integration or operational acceptance.

## First module: pending instrument and reviewed clearing

Receive an explicitly identified cheque against an actual released original officer
advance, using the existing reviewed refund recipe. Reserve its full amount from the
receipt date alongside expenses and other refunds. Receipt and whole-cheque deposit
posting retain the original officer subsidiary; they do not establish bank clearing.
The source page and newly issued copies show pending or independently confirmed clearing.
An older issued copy remains unchanged when clearing is later confirmed or withdrawn.

Clearing confirmation and its reasoned independent withdrawal add no journal and do
not free an application reservation. The amount remains applied or reserved against the
same original advance, including checks against later dated commitments. Clearing
mutations lock the original default-store case before Treasury/source records.
Existing independent withdrawal and exact posted receipt/deposit corrections retain
their dated release boundaries. Cheque identity and whole-deposit rules also apply.

Actual dishonour remains blocked by the explicit officer-return guard. Its next adapter
must debit the original advance with the exact officer subsidiary, restore capacity only
from the verified return date, reserve any source-error reversal, and govern replacement
redemption. Do not disguise a real bank return as a receipt-entry mistake.

## Public-source basis and limits

[COA Circular 2009-002, as retained in the Supreme Court E-Library](https://elibrary.judiciary.gov.ph/thebookshelf/showdocs/10/45841)
describes returning unspent advance balances to the collecting officer with an official
receipt. This is historical source context, not a claim that its pre-audit regime is
currently applicable or that it authorizes every cheque type for every LGU. No universal
cheque-acceptance policy or automatic clearance is inferred. The user's authorized
modular direction and the existing independently reviewed local collection recipe govern
this software adapter. Exact forms and LGU acceptance remain separate gates.

## Validation

- PASS: `.tmp/component_sqlite.py vouchers.test_advance_cheques`, 23 passed and six
  native-only skips (29 discovered), 20.792s, exit 0.
- PASS: `.tmp/component_native.py vouchers.test_advance_cheques`, all 29 including six
  races, 89.537s, exit 0. Two races specifically cover cheque-versus-expense and
  clearing-withdrawal-versus-expense; four retain existing advance concurrency coverage.
- PASS: `.tmp/component_sqlite.py vouchers accounting reporting`, 925 passed and 111
  native-only skips (1,036 discovered), 585.778s, exit 0. This includes the final wording
  clarifications; the financial runtime is unchanged since the native pass.
Tests cover pending and confirmed amounts, independent clearing withdrawal, dated exact
corrections, immutable copies, later-date capacity, duplicate/mixed-method capture, UAT,
the explicit actual-return boundary, and expense-versus-cheque/withdrawal races.
- PASS: synthetic browser cheque capture, independent receipt review, actual service
  posting/reconciliation and pending status on desktop 1440px and mobile 390px. Final
  wording/screenshots were rechecked after restarting the fixture server; no horizontal
  overflow. Owned browser/server are stopped. Full clearing UI replay is NOT RUN - OUT
  OF SCOPE for unchanged forms; the newly enabled officer clearing path is tested by
  native services.

The dependent actual-return adapter is being developed separately in
`C:/Users/Administrator/.codex/worktrees/grand-officer-cheque-returns`. Align that
candidate to this module's committed checkpoint before publishing it; do not mix its
changes into this checkout's active regression.

See [exception design](FINANCE_CHEQUE_EXCEPTION_DESIGN.md),
[advance refunds](FINANCE_ADVANCE_REFUNDS_IN_PROGRESS.md) and
[component checkpoint](FINANCE_CHEQUE_COMPONENTS_IN_PROGRESS.md).
