# Department assignment memo — controlled employee workflow

## Scope and existing authority

This local follow-up to the [citizen/file access review](CITIZEN_FILE_ACCESS_SECURITY_REVIEW.md)
addresses an observed employee workflow, not a new HR module or permission model.
The current assignment memo belongs to the existing EmployeeProfile. Its read
route uses the same sensitive-profile authority: the employee themselves or an
actor for whom `can_manage_employee_profiles` is true. HR department membership
alone, generic employee/profile directory access and `is_staff` alone do not
grant memo access. Upload, replacement and clearing retain the existing HR form
and profile-edit authority; employees do not gain HR editing rights.

The employee profile links to its current memo only for a sensitive-profile
reader. HR editing and its image modal use the controlled route. A custom
ClearableFileInput template preserves upload/clear behavior without rendering
the storage URL in Django's default “currently” link. No recovery email or
external delivery is introduced.

## Files and original records

New uploads retain the historical `temp_memo_path` callable identity used by the
existing migration, but use `users/<user-id>/memos/<random-id>.<extension>`.
This fixes the missing `EmployeeProfile.name` attribute, avoids mutable names/
department paths and fits the existing filename field. No field/migration changes.
The old post-save normalization was both reapplying upload_to to a complete path
and deleting the original before saving the replacement. It is removed: ordinary
profile/department edits leave the retained memo pointer and bytes unchanged.
Replacing/clearing through the existing HR form retains old stored files and its
existing ProfileEditLog events. This is not a new immutable document archive or
an automatic retention/deletion policy; there is no historical download endpoint.

The controlled GET/HEAD route selects the current profile field, checks the
`users/<folder>/memos/` namespace and safe filesystem containment, and streams
from that opened handle. Safe older username/nested memo paths remain supported;
no stored path is rewritten by this development. Missing, foreign-namespace,
traversal, drive/ADS, backslash and redirected paths fail closed. Authorization
and method checks precede opening a file. No retained memo checksum/size exists;
`X-GRAND-File-Integrity: not-recorded` makes no retrospective integrity claim.

Pillow-verified JPEG/PNG/GIF can preview inline; unknown/corrupt/other formats
download as binary attachments. No-sniff, sandbox CSP, private/no-store and
no-referrer headers constrain delivery. This does not establish malware scanning
or production file-integrity qualification. DEBUG generic media serving denies
all user memo subtrees, including legacy nested/case variants; public avatar
uploads remain available. Production web servers/object storage must separately
prevent direct serving of these bytes before operational acceptance.

## Regression evidence and gates

Three cases fail against unchanged v0.7.200 with assertion failures/zero errors:
raw private memo200, HR-page raw URL disclosure and memo upload500. Eleven
ProfileServiceTests (nine new) pass on the corrected synthetic copy; retained
source database/file and Finance-copy hashes are unchanged. Final fresh dependent SQLite216 (three native-only skips) and native107
(zero skips) pass in69.238s /65.562s respectively. Exact commands and
intermediate failures belong to [CONTINUE.md](../CONTINUE.md).
All prior test identities/classes/shard owners are unchanged (3047→3056 tests);
the CI gate is not altered.

Actual synthetic browser upload → HR preview → employee reading → replacement →
clearing passes, with two original stored images and three HR edit events retained.
The same employee link returns404 after clearing. Screenshots were inspected;
the mobile profile has no horizontal overflow. Missing synthetic branding/avatar
files remain known404s, not evidence of production rendering acceptance. No real
person's memo, operator database or external message was used.

No master integration, remote publication, deployment or production operation.
Required exact-candidate/master hosted CI, production private storage/log/recovery
qualification and formal LGU acceptance remain open. Finance remains **NO-GO**.
