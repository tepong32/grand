# Portable GRAND export archive

GRAND places every user-requested report or transaction export in one configurable filesystem root as well as returning the browser download. Point `GRAND_EXPORT_ROOT` at the single local folder watched by TraceSync. If the variable is not set, development uses `exports/` under the project root; runtime exports are excluded from Git.

## Portable layout

```text
GRAND_EXPORT_ROOT/
  GRAND_EXPORT_ROOT.json
  department/
    user/
      category/
        year/
          month/
            timestamp_checksum_filename.ext
            timestamp_checksum_filename.ext.manifest.json
```

Department, username, category, and filename segments are normalized for Windows and portable filesystems. User-provided path components cannot escape the configured root. Every artifact is written to a temporary sibling, flushed, then atomically moved into place. Repeated exports receive distinct timestamped names and do not silently overwrite earlier copies.

The adjacent JSON manifest records the artifact's SHA-256 checksum, size, export time, department, exporting user, category, relative path, and source-specific lineage such as report run, filters/period, transaction reference, source checksum, status, and whether the output is an approved official layout. The root marker explains the layout to a receiving system or administrator.

## TraceSync operation

Configure TraceSync to synchronize the entire `GRAND_EXPORT_ROOT`, not selected department subfolders. No per-user save-location selection is needed in GRAND. Copy each artifact together with its adjacent manifest and preserve the tree. On the receiving computer, verify the file's SHA-256 value against the manifest before treating the copy as intact.

This repository does not contain a TraceSync client or its configuration schema, so GRAND deliberately relies only on ordinary folders and files. If TraceSync later requires a specific control file or ignore convention, record and test that adapter without changing the department/user/category contract.

## Security and records boundary

- The export action reuses the source screen's permission and current-department boundary. A folder path never grants application access.
- Export archives may contain personal, financial, or confidential data. The operating system and TraceSync destination must enforce access control, encryption at rest/in transit, malware protection, and approved retention.
- A synchronized export is a portable safekeeping copy, not by itself an authoritative Records filing, database backup, legal record, or disaster-recovery proof.
- Official status comes from the report/template and workflow evidence recorded by GRAND. Copying a pilot or transaction CSV does not make it official.
- Operators should perform restore/checksum drills and monitor sync failures. GRAND's successful archive response proves the local atomic copy and checksum, not successful arrival on another computer.

## Adding another export

New modules call the shared archive service with bytes, the current department and user, a stable category, a safe display filename, and source metadata. Browser responses expose `X-GRAND-Export-Archived: true` and the archived SHA-256 without disclosing the server's absolute path. Tests must prove authorization, department isolation, portable path construction, artifact/manifest creation, and checksum equality.
