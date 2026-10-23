# Phase B P1 remediation — 2026-10-23

## Scope and isolation

Base HEAD: `04b25bf7b1c18a1d3932596597ba629e240ba252`.
Original reviewed candidate fingerprint:
`315642c5b1f3be812aceb93aefe8d183a594fd00aa21af7e9810ceb17655a865`.
Original workspace: `C:/Users/Administrator/.codex/worktrees/grand-baseline-20261023-04b25bf-5d9da660b102`.
Remediation workspace: `C:/Users/Administrator/.codex/worktrees/grand-p1-20261023-2408aa82de6e`.
Branch: `codex/phase-b-p1-remediation-20261023`; local checkpoint and branch push
authorized after the focused native run. No master integration, version bump or tag.

An independent local clone (no shared Git object store) starts at the exact base.
All 48 candidate files and 23 top-level evidence files were copied and SHA-256
verified before remediation. Originals remain in place. Historical evidence copies
are in `.tmp/phase-b-original-evidence/`; `.tmp/p1/baseline-checkpoint.json` records
original branch/HEAD/status/staging, file sizes/hashes and evidence sizes/hashes.
The original Phase B report remains historical and unchanged. Its passes do not
validate this revised candidate. No operator database was opened or copied here.

Risk tier: authorization, private evidence, transaction boundaries and concurrency.
Only the two P1 findings and their directly affected mutation/binding callers are
in scope. No migrations, dependency/CI changes or other feature groups.

## Authoritative mutation boundary

`assistance/services/access_service.py::locked_request_for_mutation` opens an
atomic transaction on `default`. After a signature/shape check identifies the
request, an identity UPDATE of its existing activation value acquires the database
write lock without changing state. The subsequent locking read obtains current
activation, workflow and credential fields. Token signature/expiry and revision
are checked again after any wait. Internal document services without a web token
must still match the supplied snapshot's credential revision against the fresh row.

InnoDB retains the owning row write lock until commit/rollback; ordinary staff,
admin and service UPDATEs contend on the same row. SQLite reserves its writer
before the authoritative read; this does not rely on its ineffective FOR UPDATE.
An outer SQLite read transaction that cannot upgrade fails closed rather than
retrying or replaying a financial/citizen action. The public private-response
wrapper returns a generic 503 for database failures without exposing exception
details. No promise of automatic retry or successful simultaneous SQLite writes.

The citizen POST's authorization, locked-status check, form validation and write
remain inside this boundary. Only `full_name`, `email`, `phone` are saved; submitted
status, claim, activation, ownership and other privileged fields are ignored.
GET/read behavior and approved/claimed read-only pages remain unchanged. Acceptance
is linearized at the owning lock's fresh validation; a web token expiring while
waiting is rejected. Renewal/revocation semantics otherwise remain unchanged.

Document upload/replacement/removal acquire the same request lock before document
locks and before storage writes. They recheck current eligibility even when handed
a stale request object, and public callers pass the actual access token for fresh
expiry/revision checks. Rejections precede document/timeline/file changes. Removal
of a replaced file is deferred until transaction commit. This is not a general
transactional-filesystem or storage recovery guarantee.

Staff status changes already save explicit workflow fields; admin archive uses an
UPDATE. Claim/activation/credential changes through SQL also acquire the owning
write lock. No staff permission or approval route is broadened or replaced.

## Private Telegram boundary and delivery gate

`telegram_bot/bot_handler.py` guards start, linking and unlinking before reading
message text. It accepts only private chats with a positive integer chat ID.
Group, supergroup, channel, unknown or missing/malformed metadata produces no
credential parsing, lookup, binding, unlinking or account-bearing reply.
The binding service independently requires private-chat metadata and rechecks
current token authority and unclaimed state under the owning request lock.

Binding is not approval for external notifications. Staff callers in
`assistance/views/staff.py::mswd_request_detail_view` and
`mswd_update_document_ajax` still select stored chat IDs and call
`send_telegram_update`; no trustworthy qualification state currently gates them.
The existing unawaited async send helper is deliberately unchanged. This pass
does not repair or activate delivery, does not infer qualification from chat ID
presence or binding, and sends no real Telegram messages. Before delivery can be
enabled, design independently reviewable qualification, deny unqualified/legacy
destinations by default, enforce it at both callers and transport, then test with
mocked transport. This delivery work is DEFERRED, not an accepted notification gate.

## Verification protocol

Python 3.11: `C:/xxx/_INSTALLS/_HERE/_xxx/grand-checkpoint209-pdf-venv/Scripts/python.exe`.
All commands use `-B`; dotenv is disabled by the isolated runners. SQLite uses
fresh synthetic stores; native uses fresh test schemas on an exclusively owned
loopback clone of a stopped, system-only template. Existing migration definitions
are materialized only for disposable test setup, not changed or run on operators.
No original native template or operator database is a test connection.

`.tmp/p1/record_run.py` retains exact command arrays, exit codes, raw logs/hashes,
test identities, skips, summaries and before/after source verification. Each
`.source.json` includes all non-ignored Python, HTML and text files plus the
verification Python helpers and input label JSONs. This deliberately covers more
files than the older 1,461-file manifest. Documentation is excluded from test
fingerprints and is identified separately in the final artifact manifest.
New run names never overwrite old run evidence.

Concurrency tests use independent database connections, events and observed
`performance_schema.data_lock_waits`, not a sleep-based race guess. They assert
both the staff write result and citizen outcome/final fields. Coverage includes
approval, claim, deactivation, PIN/email changes, stale document removal,
replacement/new upload, token expiry during a lock wait and the opposite ordering
where citizen editing succeeds before staff approval. The native fixture requires
visibility of MySQL performance-schema waits; missing privileges are a gate failure,
never a substitute SQLite pass.

Final runtime/test/helper fingerprint (1,491 files):
`694a0b0ba89e3371e05c776c5e564f2f69b9682b938f80daca6774030c2ccd42`.
Both focused runs verified all fingerprinted files unchanged before/after execution.

| Fresh check | Result |
| --- | --- |
| Focused SQLite | PASS: 32 discovered; 22 passed, 10 native-only race skips; 2.058s test execution, exit 0 |
| Same focused scope, native MySQL 8.4.11 | PASS: 32/32, zero skips; 5.026s test execution, exit 0 |
| Native races | All 10 executed and passed, including both write orderings, credential changes, expiry after a lock wait and three document mutations |
| Private-chat handling/binding | All eight new tests and five existing handler tests passed on both backends; no real transport |
| Static checks | PASS: all 1,115 fingerprinted Python files parse; `git diff --check` passes |

The focused scope is exactly:
`assistance.test_citizen_mutations assistance.test_citizen_mutation_concurrency
telegram_bot.tests telegram_bot.test_private_chats`.
Commands (using the Python executable above):

```text
python -B .tmp/p1/record_run.py focused-sqlite-01 -- <python-executable> -B .tmp/p1/run_isolated.py test assistance.test_citizen_mutations assistance.test_citizen_mutation_concurrency telegram_bot.tests telegram_bot.test_private_chats --noinput --verbosity 2
python -B .tmp/p1/record_run.py focused-native-01 -- <python-executable> -B .tmp/p1/native_gate.py focused
```

The native gate invokes `python -B scripts/run_mysql_tests.py` with those exact
four labels and `--verbosity 2`; its owned server stopped successfully and the
system-only source template hashes were unchanged. Test execution times exclude
setup (total wrapper durations 120.688s SQLite /217.672s native).
Both database aliases were isolated by the runners; these focused tests require
only `default`. They do not claim Finance-alias execution or Finance acceptance.
Raw log SHA-256:

- SQLite: `a0b5891a4d2f42c4c3fbc039d467b3e0164f49c8e6267a5bf7cfc0d6907f813d`.
- Native: `37a135def5e2f9fbd813b086814f0e9b9c062bdde3e36444fff3ba2747d7119d`.

Portable, synthetic-only receipts, source manifests, helper snapshots and raw logs
are retained in `docs/evidence/phase-b-p1-2026-10-23/`. The ignored local copies
also remain in `.tmp/p1/`. Original Phase B evidence/recovery archives are not
included in the push. No new focused failure occurred; old Phase B failures remain
historical and are not claimed as resolved by a different run.

The first portable-evidence export guard stopped because the SQLite receipt's
anchored parser listed 31 identities: stdout/stderr joined the first test name
to the last migration line. Its original receipt and raw log remain unchanged.
The separate `evidence-audit.json` parses that joined line, verifies 32 unique
identities equal to the native run, and records the discrepancy. This is an
evidence-parser correction, not a rerun, changed assertion or relabeled failure.

The user requested checkpoint/stop after the current native run, then authorized
pushing this branch to resume from another device. Expanded regressions are
DEFERRED at that explicit pause, not passed or waived. Both P1 fixes have fresh
focused evidence, but the remediation is not integration-ready or fully accepted.
Next: run the expanded scope in `.tmp/p1/expanded-labels.json` on both disposable
backends, investigating all failures before a separate integration-readiness review.

## Remaining gates

Hosted exact-candidate/master CI, full-project acceptance, actual browser/mail
delivery, production storage/URL-log protection and recovery remain unperformed.
Storage directory swaps/in-place mutation and unqualified legacy Telegram
associations remain separate operational/security work. This remediation is not
production readiness or integration approval. Finance remains NO-GO.
