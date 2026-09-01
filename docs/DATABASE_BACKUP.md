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

The existing `DATABASES` settings supply the two connection definitions. The command creates a temporary MySQL client file with restrictive permissions so the database password is not placed in the process argument list. The file is removed after the dump attempt and is never published.

## Create a backup set

Run the command in the same release image and environment as GRAND:

```text
python manage.py backup_databases --settings=src.settings.prod
```

The default invocation must produce both `default` and `finance`. `--database default` or `--database finance` is available for an explicitly authorized diagnostic copy, but its manifest is truthfully labeled `partial` and it is not a complete GRAND recovery point.

Use `--retain N` only after the LGU approves a retention value and confirms that an off-host copy job is working. The default does not delete old backups. A scheduler such as a Render Cron Job should invoke this management command as a discrete job; GRAND does not run a cron daemon inside the web process.

The command exits nonzero when configuration, native dump, compression, content validation, or publication fails. Only one run can hold the root lock. A failed run removes its staging directory and never replaces a previous completed set.

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

Before treating a copied set as retained evidence:

1. Confirm the set has one manifest and both named `.sql.gz` artifacts.
2. Calculate SHA-256 for each copied artifact and compare it to the corresponding manifest value.
3. Test gzip integrity and confirm decompressed content is nonempty.
4. Keep the full set together. A single database artifact is not a complete GRAND recovery point.
5. Record the copy destination, operator, time, and verification result in the approved restricted operations log.

Never edit a published manifest to say a restore passed. A restore rehearsal is separate evidence tied to the immutable backup ID and checksums.

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
