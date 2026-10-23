# Phase B: retained files and citizen/memo access

Baseline: `04b25bf7b1c18a1d3932596597ba629e240ba252`.
Working branch: `codex/reconcile-private-file-access-20261023`.
Scope authorization: Phase A preparation and G5/G6 implementation only; no
publication, release, deployment, other feature group or operator-data operation.
Finance remains NO-GO. Risk tier: authorization/private evidence/shared storage.

## Source and dependency boundary

Reconcile these exact commits, consecutively after v197 (`ba6bdc4`):

- v198 `5206412dbdbc1022a775523d69cac54321bd4505`: retained upload integrity.
- v199 `dfa9dff11ff3792f435800fcc4b5e7eab3bc0a19`: linked source downloads.
- v200 `9bc00cee5081e6019b0d7e26873ffb177fb40f9e`: citizen private access.
- v201 `17c42230da02ed7fee694657f7f01578822f623a`: employee memos.
- v202 `b9b9cca4e1b3f90b121c3a98a0f10d16b1b779f3`: legacy attachments.

Apply only the G5/G6 path-specific diff against master. Retain master's doctrine,
handoff and testing protocol, dashboard service and dashboard regression unchanged
apart from an explicit new handoff entry. VERSION, CHANGELOG, dependencies, CI,
models' schema declarations and migration files are outside this phase.
No G1/G3/G9, G4/G11/G12, G7/G8 or G10 dependency was found indispensable.

## Helper, caller and route map

| Boundary | Coordinated paths and responsibilities |
| --- | --- |
| Shared retained bytes | `src/file_integrity.py`; `inventory/private_evidence.py`: safe filesystem namespace, existing hash/size evidence, one verified streaming handle, close on failure. Existing GSO consumers retain their strict contracts. |
| Records | `records/files.py`, `services.py`, `views.py`, `templates/records/record_detail.html`: native file and linked Report/Voucher/Assistance downloads, current department/record/source ownership, audit only after successful validation. |
| Citizen identity | `assistance/models.py`, `services/access_service.py`: signed request-scoped token, purpose salt, absolute expiry, active case and state-bound revision; no short-code authorization or rewritten legacy codes. |
| Citizen HTTP | `assistance/urls.py`, `views/__init__.py`, `views/public.py`: submission, confirmation, QR, edit/upload/remove, private current-document read, generic registered-email recovery and minimal public tracker. |
| Staff HTTP | `assistance/views/staff.py`, MSWD dashboard/detail templates: original MSWD scope and controlled preview URLs. |
| Citizen presentation | Assistance landing, confirmation, access-unavailable, edit, locked and tracking templates: coordinated recovery, private links and authorized current attachments. |
| Email/QR | `assistance/services/notifications.py`; existing request service link builder; confirmation/QR views and templates: actual private links in plain/HTML email, original lifetime retained through reads and QR. |
| Telegram | `telegram_bot/services/message_service.py`, `bot_handler.py`, mocked tests: token/reference pairing; expired/legacy PIN access rejected; no real messages. |
| Current attachments | `assistance/files.py`: safe current and migration-era attachment roots, controlled streaming and safe content disposition; no invented hashes. |
| Memo model/upload | `profiles/models.py`, `services/file_service.py`, `forms.py`, memo input widget: original upload callable identity, stable new filenames, ordinary profile edits preserve retained files. |
| Memo HTTP/presentation | `profiles/files.py`, `views.py`, `urls.py`, profile/edit templates: self or existing sensitive-profile manager, current memo only; retain legacy safe paths and original editing authority. |
| Generic media | `src/media.py`, `src/urls.py`: DEBUG handler denies reviewed confidential roots and memo subtrees while retaining public branding/avatar assets. |
| Link configuration | `src/settings/base.py`: positive private-link lifetime, default seven days; no routing/schema change. |

## Allowed/denied contract and unresolved assumptions

- Authorized Records readers also need download permission, visible current record
  and matching source office; valid superseded official Voucher outputs remain
  readable. Shadow, foreign, missing, altered or ambiguous sources fail closed.
- Matching active citizen token grants current-case reads and permitted edits.
  Approved/claimed cases remain readable but cannot mutate. Anonymous private
  reads, wrong-case, malformed, expired and legacy PIN-only access are denied.
- Public references expose structured status only. Renewal uses stored recipients,
  generic public responses and existing persistent throttling; never a supplied
  arbitrary recipient or a public private-link response.
- Legacy Assistance attachments and memos have no retained immutable baseline.
  Safe current bytes remain accessible under original authority with explicit
  `not-recorded` integrity status. Do not backfill checksums or relocate files.
- Memo self/manager access does not grant HR editing or generic directory access.
- Filesystem containment is supported; unqualified remote storage fails closed.
  Production web-server/object-store rules, access logs, malware checks, recovery
  and real deployment behavior remain unverified and outside this phase.
- Tokens are state-bound, not one-time persisted credentials. Renewal does not
  revoke every prior unexpired link; restoring exact prior state can restore a
  link within its lifetime. Existing Telegram associations are not retrospectively
  authenticated; operational review precedes sensitive external notification use.

## Historical evidence versus fresh verification

Historical feature-source passes do not validate this combined candidate. Retain
the documented raw-media disclosure, duplicate-code lookup failure, missing memo
upload attribute, and their failed/repaired runs in the original source records.
They are development findings, not claims about production exposure.

Fresh verification uses Python 3.11 and the existing pinned dependency environment.
`.tmp/phase-b/run_isolated.py` disables dotenv, overrides both aliases before Django
setup, uses fresh synthetic test stores and temporary media/private/export/backup
paths, and local-memory email. Existing/operator databases are never connections.
Django test setup materializes the existing schema only in disposable test stores;
no application migration change or operator migration command is authorized.
Exact commands, identities, results and remaining checks will be recorded below
after the owned runners terminate. No hosted CI or acceptance pass is implied.


## Fresh results and exact commands

Source is the uncommitted Phase-B patch on baseline
`04b25bf7b1c18a1d3932596597ba629e240ba252`, not a new commit.
Runtime/test/dependency fingerprint (1,461 files):
`315642c5b1f3be812aceb93aefe8d183a594fd00aa21af7e9810ceb17655a865`.
All recorded source hashes were unchanged through the final native pass.
This fingerprint excludes documentation and ignored test-runtime helpers.

Python executable for every command below:
`C:/xxx/_INSTALLS/_HERE/_xxx/grand-checkpoint209-pdf-venv/Scripts/python.exe`
(Python 3.11; `PYTHONDONTWRITEBYTECODE=1`).

```text
python -B -m pip check
python -B .tmp/phase-b/run_isolated.py test records.test_file_integrity records.test_source_downloads --noinput --verbosity 2
python -B .tmp/phase-b/run_isolated.py test records assistance profiles telegram_bot users.test_auth_security users.test_auth_concurrency reporting.tests gso_integration_tests.test_download_handles gso_integration_tests.test_packet_download_handles gso_integration_tests.test_grand_office_records departments.tests --noinput --verbosity 2
python -B .tmp/phase-b/native_gate.py
```

The native owner invokes the unchanged committed runner with this exact scope:

```text
python -B scripts/run_mysql_tests.py records assistance profiles telegram_bot users.test_auth_security users.test_auth_concurrency reporting.tests gso_integration_tests.test_download_handles gso_integration_tests.test_packet_download_handles gso_integration_tests.test_grand_office_records departments.tests --verbosity 2
```

Native test credentials are supplied only through the child environment, never
in command arguments/reports. The owner creates an exclusive local clone of a
stopped system-only MySQL template, verifies datadir/port/loopback and absence
of application schemas, and shuts down only that owned server. Original template
hashes match before/after; the owned server stopped and its port is closed.

| Fresh check | Result |
| --- | --- |
| Dependency consistency | PASS: no broken requirements |
| Initial Records integrity/source downloads | PASS: 32/32, zero skips, 1.984s test execution; precedes alternate-stream tightening |
| Final affected SQLite scope | PASS: 291 discovered/executed; 288 passed, 3 native-only skips; 73.495s test execution |
| Same final scope, native MySQL 8.4.11 | PASS: 291/291, zero skips; 86.599s test execution |
| Mocked Telegram | Included in each expanded run: 5/5; no real messages |
| Syntax and whitespace | PASS: AST parsing of 29 scoped Python files; `git diff --check` |
| Source/preservation guards | PASS: 1,461 runtime/test hashes; dashboard service/test, policy and baseline SQLite hash unchanged; both canonical operator DB hashes unchanged |

Execution durations above exclude test-schema setup. Both aliases were destroyed
after each successful test run. SQLite skips were exactly native authentication
collation and the two concurrent throttle-counter cases; all three actually
executed and passed on MySQL. Test IDs and raw-log SHA-256 receipts are retained
in `.tmp/phase-b/*.log.receipt.json`, with owner and source records in
`.tmp/phase-b/verification.json` and `source-candidate.json`.

### Failure retained and bounded security refinement

The adopted namespace helper accepted an NTFS alternate-data-stream filename.
A fresh database-free probe (`python -B .tmp/phase-b/namespace_check.py`) failed
before correction (`namespace-red.log`). The shared helper now rejects colons;
the existing Records unsafe-name test includes an alternate-stream subcase and
asserts rejection before opening storage. This is the sole application refinement
beyond the reconciled G5/G6 patch. No test assertion or gate was weakened.
The first diagnostic rerun expected ValidationError while the existing guard's
contract also allows ValueError; it raised ValueError (`namespace-green.log`).
That diagnostic expectation was corrected, not the production exception contract.
The final probe (`namespace-final.log`) and final 291-case runs pass. Preserve both
failed diagnostic records; neither is relabeled as a pass.

### Remaining evidence boundaries and next step

NOT RUN — OUT OF SCOPE: full-project suites and hosted candidate/resulting-master
CI. The shared affected consumers ran freshly on both backends; this is not a
release or whole-Finance gate. No prior feature-source pass substitutes for these
fresh results. NOT RUN: new real-browser, printer, deployment, production-storage,
recovery or human/LGU acceptance. Existing HTTP rendering/caller tests are not
presented as browser acceptance. No migration files were generated or changed.
The strong-link legacy transition and operational assumptions above still apply.

Next: owner reviews only this Phase-B diff and evidence. Keep the branch local,
uncommitted and untagged. Any further integration, publication, browser/operational
qualification or Phase C requires separate instruction. Do not start another
feature group. Finance remains NO-GO.

## Complete candidate file inventory

```text
AGENTS.md
CONTINUE.md
assistance/files.py
assistance/models.py
assistance/services/access_service.py
assistance/services/notifications.py
assistance/tests.py
assistance/urls.py
assistance/views/__init__.py
assistance/views/public.py
assistance/views/staff.py
docs/CITIZEN_FILE_ACCESS_SECURITY_REVIEW.md
docs/EMPLOYEE_MEMO_ACCESS.md
docs/PHASE_B_PRIVATE_ACCESS_RECONCILIATION_2026-10-23.md
docs/RECORDS.md
docs/gso/office-records.md
inventory/private_evidence.py
profiles/files.py
profiles/forms.py
profiles/models.py
profiles/services/file_service.py
profiles/templates/profiles/widgets/memo_input.html
profiles/tests.py
profiles/urls.py
profiles/views.py
records/files.py
records/services.py
records/test_file_integrity.py
records/test_source_downloads.py
records/views.py
src/file_integrity.py
src/media.py
src/settings/base.py
src/urls.py
telegram_bot/bot_handler.py
telegram_bot/services/message_service.py
telegram_bot/tests.py
templates/assistance/access_unavailable.html
templates/assistance/confirmation.html
templates/assistance/edit_locked.html
templates/assistance/edit_request.html
templates/assistance/landing.html
templates/assistance/mswd/dashboard.html
templates/assistance/mswd/request_detail.html
templates/assistance/track_request.html
templates/profiles/profile.html
templates/profiles/profile_edit.html
templates/records/record_detail.html
```
