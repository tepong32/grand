# Secure Phase B checkpoint evidence

See [the final report](../../PHASE_B_SECURITY_CHECKPOINT_2026-10-24.md).
Receipts retain exact command arrays, exits, counts, identities, skips, raw-log
SHA-256 and source fingerprints. Decompress `*.raw.gz` losslessly to verify those
raw hashes. `*.source.json` includes 1,499 runtime/test/helper byte hashes.
`verification-helpers.json` contains the exact executable/input helper bytes as
base64 with SHA-256; `environment.json` records runtime versions. Native owner
receipt verifies server shutdown and source-template preservation. No operator
data, secrets or recovery archive is included. Do not relabel this as hosted CI,
full-project/Finance validation, production readiness or checkpoint acceptance.

For another device, inspect helpers first and restore only into a fresh owned
`.tmp/secure-phase-b` without overwriting existing files; verify decoded hashes.
Restore the retained `.tmp/p1` helpers from the parent checkpoint's evidence too.
The new manifest helper reads `.tmp/secure-phase-b/baseline.json`: its `files`
member is the parent P1 `focused-native-01.source.json`'s `files` mapping. Original
private baseline metadata remains local; only that public source list is needed
for verification. Native helpers reference this machine's stopped system-only
MySQL template and binary; they are not permission to connect to any existing
operator/production server. Establish an owned native environment on the target
machine and retain new helper hashes before rerunning. Preserve strict/timezone,
identity/schema and shutdown checks. Real Telegram HTTP requests are forbidden.
Windows line endings form part of the recorded byte hashes; a fresh checkout
with different bytes/environment requires a fresh source identity and evidence.

The VM CLI preview is read-only. Its release/tag operation was not executed.
The reviewed commit-only VM helper creates no release/tag. Owner acceptance,
exact-revision CI before integration and all operational/Finance gates remain.
