# Phase B P1 focused checkpoint evidence

See [the remediation report](../../PHASE_B_P1_REMEDIATION_2026-10-23.md) and
[the current handoff](../../../CONTINUE.md). This is synthetic local evidence,
not hosted CI, full-project acceptance, integration approval or production readiness.

- `*.receipt.json`: original command arrays, exit codes, original parsed test IDs,
  skip details, raw-log SHA-256 and source fingerprint.
- `*.source.json`: exact 1,491-file runtime/test/helper byte-hash manifest.
- `*.log.gz`: lossless raw logs. Decompressed SHA-256 must match the receipt.
- `evidence-audit.json`: independently parsed counts and complete identities;
  documents the original SQLite parser's joined-output-line omission.
- `verification-helpers.json`: exact helper/input bytes encoded as base64 with
  SHA-256. No credentials, operator data or original recovery archive is included.
- `native-owner-result.json`: owned native server shutdown/template guard result.
- `artifact-manifest.json`: portable artifact and changed-candidate file hashes;
  excludes itself to avoid a recursive checksum.

To resume on another device, first inspect these helper snapshots and their safety
preflights, then restore them to a fresh `.tmp/p1` without overwriting existing
files. Decode each `bytes_base64` value, verify its SHA-256, and write its relative
key only beneath the chosen checkout. The native helper references this machine's
stopped system-only template and installed MySQL binary: that path is not a
portable database. Do not copy operator stores or run it against another existing
server. Establish a fresh owned native environment and record changed helper/input
hashes before future verification. Never bypass the runner's timezone, schema,
strict-mode, ownership, source or shutdown checks.

The original anchored receipt parser missed one SQLite identity due to joined
migration/test output. Preserve that receipt and use the supplemental audit for
its complete identity set; correct the parser in a new helper revision before
future runs rather than overwriting historical evidence.

These are hashes of the actual Windows test files, including their line endings.
A fresh checkout on another platform may have different byte hashes; do not
silently present that checkout as the tested environment. Re-establish source
identity and run the pending expanded scope on disposable stores.

The user requested a checkpoint after focused tests and a pause. Expanded
Assistance/Records/Profiles/Reporting/authentication/GSO/dashboard regression,
hosted CI and operational/browser/storage/recovery acceptance remain outstanding.
No Phase C, master merge, release or deployment is authorized. Finance stays NO-GO.
