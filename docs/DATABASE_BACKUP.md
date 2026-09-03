# GRAND database backup and recovery

Status: the native two-database backup generator is implemented and synthetically tested. A successful command creates a recovery artifact; it does **not** prove that an LGU restore rehearsal has passed.

## What is protected

GRAND has two separately routed stores that form one application recovery point:

- `default` contains users, departments, vouchers, custody links, reports, and other platform transactions;
- `finance` contains the standalone Accounting and Budget authority data governed by `FinanceDatabaseRouter`.

The normal backup command captures both stores in one completed set. Each database remains a separate compressed native MySQL logical dump so routing and recovery can be checked independently.

Database backups are intentionally separate from `GRAND_EXPORT_ROOT`. The export root contains user-requested reports and transaction packages; `GRAND_BACKUP_ROOT` contains restricted recovery material. Uploaded media, the export root, encryption material, and external records still need their own approved backup arrangements.

## Production settings

Set these in the deployment environment, never in source control:

| Setting | Meaning | Default |
| --- | --- | --- |
| `GRAND_BACKUP_ROOT` | One persistent, access-restricted folder for completed backup sets | `<project>/backups` |
| `GRAND_BACKUP_RETENTION_COUNT` | Number of newest completed sets retained locally; `0` performs no automatic deletion | `0` |
| `GRAND_MYSQL_DUMP_COMMAND` | Path or command name for the deployment's compatible `mysqldump` client | `mysqldump` |
| `GRAND_MYSQL_CLIENT_COMMAND` | Path or command name for the compatible `mysql` restore client checked by production preflight | `mysql` |

The existing `DATABASES` settings supply the two connection definitions. The command creates a temporary MySQL client file with restrictive permissions so the database password is not placed in the process argument list. The file is removed after the dump attempt and is never published.

## Create a backup set

Run the command in the same release image and environment as GRAND:

```text
python manage.py backup_databases --settings=src.settings.prod
```

The default invocation must produce both `default` and `finance`. `--database default` or `--database finance` is available for an explicitly authorized diagnostic copy, but its manifest is truthfully labeled `partial` and it is not a complete GRAND recovery point.

Use `--retain N` only after the LGU approves a retention value and confirms that an off-host copy job is working. The default does not delete old backups. Invoke the command only from a discrete job that can write the approved persistent/off-host backup root; Render cron jobs cannot access persistent disks and therefore must not publish filesystem backups there. GRAND does not run a cron daemon inside the web process.

The command exits nonzero when configuration, native dump, compression, content validation, or publication fails. Only one run can hold the root lock. A failed run removes its staging directory and never replaces a previous completed set.

On success the command prints the completed set path and the SHA-256 of its immutable `manifest.json`. Retain that manifest hash separately from the copied backup set—for example, in the restricted operations log—so later verification can detect replacement of both an artifact and its local manifest.

## Portable folder contract

The root contains a marker and dated backup-set directories:

```text
GRAND_BACKUP_ROOT/
  GRAND_BACKUP_ROOT.json
  2026/09/01/20260901T083000000000Z-a1b2c3d4/
    grand-default-20260901T083000Z.sql.gz
    grand-finance-20260901T083000Z.sql.gz
    manifest.json
```

Temporary work and the run lock have dot-prefixed names. TraceSync or another copy job must ignore `.tmp` and `.grand-backup.lock`, and copy only the root marker plus non-dot dated sets containing `manifest.json` with `status: completed`.

Publication happens only after both gzip streams are readable and nonempty and every compressed artifact has a SHA-256 digest. The complete staging directory is renamed into the dated tree only after validation. The manifest records logical database names, engines, file sizes, hashes, application version, available deployment revision, scope, and `restore_tested: false`; it contains no credentials.

## Check an off-host copy

Run GRAND's read-only verifier against the copied dated set, not the live source directory:

```text
python manage.py verify_database_backup <copied-set-directory> --expect-manifest-sha256 <separately-retained-hash> --settings=src.settings.prod
```

Use `--json` to emit a machine-readable verification receipt for the approved restricted log. The receipt records the backup ID, verification time, computed manifest hash, every artifact hash/size, integrity result, and whether an external manifest hash was compared. It always retains `restore_tested: false` because reading gzip and checksums is not a database restore.

The verifier exits nonzero for an invalid identity/version/status, a set-directory/backup-ID mismatch, unsafe or duplicate filenames, missing/extra SQL artifacts, a non-MySQL entry, invalid gzip, empty content, size/hash drift, a partial set without explicit `--allow-partial`, a complete set without exactly both stores, a changed externally retained manifest hash, or an edited claim that restore testing already passed.

Before treating a copied set as retained evidence:

1. Confirm the set has one manifest and both named `.sql.gz` artifacts.
2. Run `verify_database_backup` and compare its manifest SHA-256 to the value retained outside the set.
3. Test gzip integrity and confirm decompressed content is nonempty.
4. Keep the full set together. A single database artifact is not a complete GRAND recovery point.
5. Record the copy destination, operator, time, and verification result in the approved restricted operations log.

The live `production_preflight` command independently confirms that both native clients are present and that the configured backup root supports create, fsync, atomic rename, read-back, and cleanup. It does not run a backup or restore, inspect an off-host destination, or satisfy this checklist by itself.

Never edit a published manifest to say a restore passed. A restore rehearsal is separate evidence tied to the immutable backup ID and checksums. Checksums prove internal integrity and, when an independently retained manifest hash is supplied, detect replacement relative to that retained value; they are not signatures and do not establish custody or authorship by themselves.

## Isolated restore rehearsal

Use a disposable, access-restricted MySQL host that cannot resolve to or overwrite production. The dumps use MySQL's `--databases` format, so they recreate/use their recorded database names; do not pipe them into a production server.

1. Select a completed off-host set and recheck both SHA-256 values.
2. Prepare a temporary MySQL client option file outside the repository with the isolated host, user, password, and port; restrict it to the operator account.
3. Restore `grand-default-...sql.gz`, then `grand-finance-...sql.gz`, using the compatible `mysql` client and that option file.
4. Point an isolated GRAND release matching the manifest version/revision to those restored databases.
5. Run `python manage.py check --settings=src.settings.prod`, inspect applied migrations for both stores, and execute the approved synthetic reconciliation/control-total checklist.
6. Test representative department access, one cross-store Finance case, critical report reproduction, and required media/export references without sending email or external notifications.
7. Record the backup ID, hashes, release, database versions, commands, timings, reconciliation totals, exceptions, witnesses, and recovery-time result in a separate signed or attributable rehearsal receipt.
8. Destroy the isolated restored data using the LGU's approved secure-disposal process.

### Record the result in GRAND

The F11 backup/restore readiness exercise now requires a structured two-store rehearsal record. The assigned exercise owner enters the exact dated backup-set ID and three backup hashes, off-host verification, preflight receipt checksum, approved policy/RPO/RTO, isolated host/release/database/log references, actual recovery timestamps, both store and migration confirmations, reconciled controls, a representative cross-store case, runtime-file check, secure-disposal reference, and every exception/resolution. GRAND calculates actual RPO/RTO and seals the record with SHA-256.

A different assigned witness can pass only when every required control is confirmed, no exception remains unresolved, and both actual targets are within the locally approved limits. Otherwise the witness requires a reasoned rerun. Passed evidence becomes immutable. The final cutover record must select the passed rehearsal from that exact cycle, so its backup ID and evidence checksum remain bound to the authority decision and schema-v9 portable evidence package.

Only references and hashes belong in this application record. Keep dumps, credentials, client option files, and sensitive restore logs inside their approved restricted custody location.

The local development databases use SQLite. The production backup writer deliberately refuses to copy SQLite files and therefore cannot give a false impression that a development file copy validates MySQL recovery.

## Failure handling

- A dump or verification failure leaves all older completed sets untouched.
- A concurrent-run lock causes a nonzero exit. Investigate the scheduled job before removing a stale lock; do not remove a lock held by a live process.
- A retention deletion problem is reported as a warning after the new verified set is already published. Operators must resolve the cleanup issue without deleting the new recovery point.
- Never place a public download endpoint over the backup root or copy backup artifacts into static/media directories.
- Alerting, schedule, off-host destination, encryption, retention period, recovery point objective, recovery time objective, and named restore witnesses remain deployment decisions requiring local approval.

## Acceptance gate

Production readiness requires more than passing unit tests. Before cutover, the LGU must supply and approve:

- the backup schedule and retention rule;
- a restricted persistent backup root and off-host copy destination;
- monitoring and failure escalation ownership;
- at least one successful restore rehearsal for both databases using an actual production-compatible artifact;
- reconciled control totals and role-shaped application checks after restore;
- approved RPO/RTO and retained rehearsal evidence.

Until those items exist, the truthful status is **backup creation implemented; production restore not yet proven**.
