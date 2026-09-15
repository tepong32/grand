# Returned-cheque principal redemption

2026-09-15: validated v0.7.112 development checkpoint on `codex/finance-cheque-redemptions`,
based on pushed v0.7.111 (`37d4183`; [draft PR #72](https://github.com/tepong32/grand/pull/72)).
This is not master integration or full redemption/custody completion.

## Current implementation

A new ordinary receipt links to one independently posted and reconciled bank return.
Its approved recipe debits the actual collection asset and credits the selected original
receivable for the whole principal. The original cash-flow purpose and source identities
are pinned; no second revenue is recognized. The original OR surrender or loss-affidavit
reference is recorded as actual evidence. This implements the researched baseline as
an application control, not a claim of universal locally accepted procedure.

Cash and explicitly identified manager's/cashier's cheques use separate recorded facts.
Replacement cheque receipt is not settlement confirmation; bank clearing must be reviewed.
A subsequent bank return creates a new source-linked obligation. The earlier principal
receipt remains reserved against its original return, preventing a second collection
against the same obligation; subsequent redemption selects the later return.

Treasury/source locks and a stored generated active return key serialize competing
receipts and original-return corrections. Only independently posted/reconciled exact
receipt correction retires its reservation, retaining the original receipt's posted
status for dated deposit calculations. A later correction cannot release an earlier hold.
Original-return correction is blocked while a redemption reservation exists.

The ordinary collection posting, withdrawal, source correction, whole-cheque deposits,
clearing and retained-copy mechanisms are reused. Finance and default stores remain
separate; the explicit selected-return account instruction cannot be used through an
unlinked ordinary receipt capture route.

## Internal custody adapter

An explicitly authorized Treasury officer can associate the returned cheque with an
existing TracePoint item they prepared or currently hold. Item and source identities
are pinned in versioned associations; generated active keys prevent reuse for another
cheque or DV. An independent custody reviewer can withdraw a mistaken association
with a reason, preserving the earlier association and physical history.

Association does not assert physical receipt. The source shows TracePoint's current
packet/holder and confirmed handovers separately from financial settlement. Retained
copies include custody only when explicitly requested by an actor authorized for both
sources; downloading those copies rechecks the captured and current packet authority.
Ordinary Finance-only copies retain their existing permissions. Earlier copies remain
unchanged after a handover or corrected association.

This adapter covers internal custody. External payee/court delivery remains a separate
extension requiring actual authority and receiving evidence; an employee handover must
not be used to fabricate an external receipt.

## Validation

- FAIL - CAUSED BY CURRENT WORK: initial native redemption run, six tests, five passed
  and one fixture error, 36.544s, exit 1. The inherited deposit helper used a date before
  the new receipt. It now uses the receipt date; the service correctly rejected the old fixture.
- PASS: `.venv/Scripts/python.exe .tmp/prior_native_authority.py vouchers.test_cheque_redemptions vouchers.test_cheque_custody`:
  all 12 tests, including three native races, 27.250s, exit 0. Covers competing principal
  receipts, receipt versus original-return correction, competing custody links, repeated
  replacement return/redemption, source-correction retirement and protected frozen copies.
- PASS: a subsequent native run of the same labels passes 12/12 in 29.946s, exit 0,
  including the narrowed custody lock query. It precedes the final dated-return guard.
- PASS: `.venv/Scripts/python.exe .tmp/earlier_sqlite.py vouchers.test_cheque_redemptions vouchers.test_cheque_custody`:
  12 discovered, nine passed, three native-only skips, 16.024s, exit 0. Includes restricted
  association/withdrawal-history checks; precedes the final dated-return guard.
- PASS: `.venv/Scripts/python.exe .tmp/prior_native_authority.py vouchers.test_cheque_redemptions vouchers.test_cheque_custody`:
  13/13 including three races, 63.774s, exit 0. Includes the new case denying original-return
  correction before the principal receipt's correction date.
- FAIL - CAUSED BY CURRENT WORK: broad `.venv/Scripts/python.exe .tmp/earlier_sqlite.py vouchers finance accounting reporting tracepoint`,
  1,226 discovered, 1,115 passed, five failures, 106 native-only skips, 891.295s, exit 1.
  The new custody permission was incorrectly included in DV workbench navigation, so the
  collection-only role gained workbench access. All five failures reproduce that same
  inherited role contract. Removed custody from the DV action list; its own service
  permission and explicit UAT denial remain. PASS: focused collection-role/UAT checks
  (`CollectionWorkflowTests.test_collection_role_has_navigation_without_disbursement_or_posting_authority`
  and `CustodyTests.test_web_link_uat_denial_and_generated_active_item_identity`) pass on
  SQLite, 2/2 in 6.189s, exit 0.
- PASS: fresh final broad `.venv/Scripts/python.exe .tmp/earlier_sqlite.py vouchers finance accounting reporting tracepoint`:
  1,228 discovered, 1,121 passed, 107 native-only skips, 730.895s, exit 0. This includes the
  final navigation fix and all current runtime changes. Scope covers shared roles, DV
  custody linking, collection posting/correction, Finance configuration and reporting.
  The unrelated local Accounting policy-test draft was present in broad discovery but
  is excluded from this checkpoint's files.
- A subsequent cross-route audit aligned the existing DV item-link service to the same
  packet-before-item lock order. PASS: `.venv/Scripts/python.exe .tmp/prior_native_authority.py vouchers.test_cheque_custody vouchers.test_signature_custody`:
  all 17 selected tests in 30.364s, exit 0, including two custody races and the imported
  principal receipt cases. This includes the cheque-versus-DV claim race for one physical
  item; do not add overlapping runs as unique scenario counts. PASS: the four existing DV link
  regressions (`VoucherWorkflowTests.test_tracepoint_link_records_only_custody_reference_not_financial_fields`,
  `test_legacy_packet_link_requires_stored_owner_before_new_link_and_replay`,
  `test_legacy_packet_link_reloads_item_before_visibility_check`,
  `test_legacy_packet_link_rechecks_stored_association`) pass on SQLite in 2.694s, exit 0.
- PASS: synthetic browser capture, independent source review, posted cash receipt text,
  original source links, proposed financial rows and internal custody linking. Desktop
  1440px and mobile 390px are readable without horizontal page overflow. Manager/cashier
  clearing and actual internal handover are service-tested; their complete browser flows
  are NOT RUN - OUT OF SCOPE for unchanged underlying posting/TracePoint services.
- System, migration-drift and whitespace checks pass. Operator DB SHA-256 remains
  `C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C`.

The preceding presentation PR's hosted MySQL job was cancelled at its 30-minute job
limit while still progressing, without a completed test result. The next checkpoint
allows 60 minutes for the same full native regression; no test or gate is removed.
The following bank-return PR #72's complete hosted verify and MySQL jobs both passed
(MySQL 29m46s), including the presentation code. The next checkpoint still needs its own
hosted completion before integration. Local focused passes do not convert the earlier
cancelled hosted run into a pass. The synthetic browser/server are stopped.

## Still open in this phase

- External custody delivery to a payee or court, distinct from internal TracePoint handovers.
- Fees/penalties combined with principal need explicit reviewed component allocations.
  The current capture is principal-only and does not infer rates or balance differences.
- Officer cheque refunds retain their separate dated-capacity boundary.

System and migration-drift checks pass. No operator migration or bank contact occurred.
The bounded principal/internal-custody checkpoint is validated; the extensions above
remain open. The next mixed-purpose adapter is developed separately.
