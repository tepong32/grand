# Citizen and file access review — 2026-10-19

Status: **confirmed development defects; recommended development approved by the
owner on 2026-10-19; implemented in local v0.7.200; owner paused after checkpoint**.
Reviewed base: local v0.7.199 / `dfa9dff11ff3792f435800fcc4b5e7eab3bc0a19`.
No remote publication, production investigation, data operation or real email.
Finance remains NO-GO. The owner decision is DECISION-OPS-005 in the
[decision register](IMPLEMENTATION_DECISIONS.md).

## Observed behavior

An exclusive copy of the retained synthetic Records fixture was used. Actual
Django requests at the reviewed source revision show:

| Check | Result |
| --- | --- |
| Anonymous raw media request for a Records upload | 200 with the exact file bytes, while the controlled Records route redirects to login |
| Anonymous raw media requests for Report, Voucher and Assistance files | 200 for all three; no Records download audit event |
| Same-size corrupted Records file | Raw media returns corrupted bytes with200; the checked download rejects it with404 |
| Public tracker with reference code alone | 200 reveals the attachment filename and its raw media URL |
| Citizen edit page with one six-digit code alone | 200 reveals synthetic personal details and attachment links without login |
| Two active requests with the same edit code | The token-only edit lookup returns500 / `MultipleObjectsReturned` |

The media results apply to the Django **DEBUG development handler**. They do not
prove that any production host exposes these URLs. No production host, citizen
file, real credential or actual email was accessed. Deployment configuration and
private storage/recovery qualification remain separate, unperformed gates.

Private receipt: `.tmp/citizen-privacy-reproduction.json`; command:
`python -B .tmp/reproduce_citizen_privacy.py`. All assertions passed. Original
synthetic database/file hashes and the copied Finance database hash remain
unchanged. Only the disposable default-store copy was populated/manipulated.
The two deliberately duplicated codes were synthetic; no existing code was reset.

## Source trace at reviewed v0.7.199

- `src/urls.py` mounts Django's generic media handler under DEBUG without a
  confidentiality check. The checked application endpoints do not control it.
- `assistance/models.py` generates six numeric digits for `edit_code`. That field
  is not unique. Reference codes use a month/year/count format.
- `assistance/views/public.py` retrieves an active request by edit code alone for
  the edit page and upload route. The tracker requires only the reference code.
- `templates/assistance/` uses raw `doc.file.url` for citizen links and staff
  image/PDF previews. Email/QR/submission/recovery flows also use the legacy edit
  URL. Blocking raw files alone would break these legitimate journeys.
- `assistance/decorators.py` supplies the existing MSWD staff scope. Records,
  Reporting and Vouchers have their own controlled read routes. Preserve them;
  do not replace their authority with a generic logged-in-file handler.

## Recommended bounded change

Keep account-free citizen access and existing staff authority. Replace six-digit-
only access with a cryptographically strong, request-scoped private link, using
Django's signing facilities where suitable. Recommend a configurable **seven-day
link lifetime**, with a clear expired-link page and renewal sent only to the
already registered email. No new citizen account system or financial role.

The proposed employee/citizen behavior is:

1. Submission returns a private access link to the submitting browser and sends
   it through the existing email workflow. No sensitive attachment is public.
2. A reference code alone shows only minimal structured tracking status. It
   reveals no names, contact details, attachment names/URLs or free-text staff
   notes. Detailed history remains behind private access or existing staff scope.
3. The private link opens the correct active request even when two legacy edit
   codes collide. Approved/claimed cases retain their existing edit lock while
   allowing authorized reading of their current attachments.
4. Upload, replacement, removal, validation, confirmation, QR and resend paths use
   the same scoped access contract. Retire all six-digit-only authorization
   paths together; do not leave a weaker fallback behind a stronger screen.
5. Old short-code links/QRs receive a clear recovery notice rather than access to
   an arbitrary matching request. Recovery must not reveal addresses, accept a
   caller-supplied destination or disclose whether a private request exists.
6. Existing MSWD staff previews and Records downloads keep their current scope.
   Citizen and staff previews use controlled file URLs, not raw storage URLs.
7. Sensitive media namespaces cannot be read through generic development media
   serving, including alternate case/separators and redirected filesystem paths.
   Keep legitimate public branding/profile/sample assets working. Production
   servers/storage must enforce the equivalent boundary before acceptance.

Use current request identity and framework primitives where they satisfy expiry,
scope and revocation. Do not promise a zero-migration solution before reviewing
those requirements. Any necessary schema transition must be additive, preserve
source records and collision evidence, and receive the required migration/native
validation. Do not rewrite historical codes to hide duplicates or manipulate any
operator database. No production transition is authorized by this design.

The material owner choice is retiring the present short-code-only citizen access
contract, including previously issued links/QRs, in favor of expiring private
links and registered-email recovery. That affects an established user journey and
was resolved by the owner: develop the recommended secure-access workflow. No statutory Accounting decision
is being delegated to this technical design.

## Verification required before a checkpoint

- Authenticated/anonymous regressions that fail against the current raw-media,
  tracker disclosure and duplicate-code defects.
- Valid, forged, wrong-request, expired and revoked access; legacy recovery;
  removed documents/inactive requests; approved/claimed edit locks; CSRF/methods;
  current staff office/Records permissions; no token/address disclosure.
- Initial submission, email-link access, expiry/renewal, upload/replace/remove,
  locked reading and ordinary staff previews in an actual synthetic browser.
- Private-file raw-URL denial without breaking public assets; traversal,
  encoding/separator/case variations and redirected directories.
- Affected Assistance, Records, Reporting/Voucher output, shared URL/security
  and export regressions; broader suites appropriate to the final scope. Native
  testing is mandatory if persistence/identity/transaction behavior changes.
- Synthetic file/database recovery and protected-store guards for any storage or
  schema change. Never substitute a synthetic drill for production qualification.

## Implemented development contract

The isolated `codex/citizen-private-access` change uses Django timestamp signing,
a dedicated purpose salt and a server-keyed SHA256 revision of request ID,
reference, legacy code and registered email. The decodable payload contains only
the ID and keyed revision. The legacy PIN is neither published in email nor an
authorization fallback. Duplicate PINs retain their original evidence and cannot
make request lookup ambiguous. No schema, migration, persisted identity, Finance
route, financial permission or database router changes.

`ASSISTANCE_PRIVATE_LINK_SECONDS` is a positive environment setting, defaulting
to604800 (seven days). GET, QR, confirmation, file access and ordinary editing do
not extend the original lifetime. Renewals send a newly signed link only to each
matching active request's stored email. Existing and absent addresses receive the
same public message. Both endpoints reuse existing default-store AuthAttemptBucket
atomic counters: ten attempts/network/minute and three/keyed casefold-email/hour.
Cache clearing cannot reset these counters; counter/lookup failures return503.
Native email matching is followed by Python casefold equality to reject fuzzy
collation matches. No caller-selected recipient or private URL is returned publicly.
The plain-text email now retains its actual links; stripping HTML previously
lost them. An authorized email edit revokes the previous link and asks the citizen
to renew through the updated registered inbox. Other edits preserve the token.

Deactivation, changing the legacy credential or changing the email invalidates
the matching signed revision. This is state-bound access, not a persisted
one-time token or a per-link revocation registry. Restoring exactly the prior
state within its lifetime can restore that link's validity; expiry is absolute.
Renewing does not cancel every other unexpired link. No revocation-management
screen, account system, silently rewritten codes or historical token migration
is introduced. The existing mutable Assistance document behavior is retained,
including replacement/removal timeline entries; this is not immutable attachment
version storage. No missing hash/size baseline is manufactured.

Edit/upload/removal, confirmation/QR and the bot's reference/token lookup share
the same signed contract. Telegram PIN linking is retired as well; opt-in bot
help describes the new token. The confirmation page no longer encourages
copying a credential to an external bot. Existing Telegram associations are not
silently cleared or retrospectively verified; operational review must resolve
any legacy association before sensitive external notifications are accepted.
No real email or Telegram message was used for validation.

Public tracking receives only the reference and structured status, not the case
object, attachments or free-text notes. Citizen current-file reads require the
matching active case/token; staff reads reuse the exact existing MSWD boundary.
Removed/inactive/foreign attachments fail closed. Approved/claimed cases remain
readable but uneditable. Records keeps its distinct native scope and download
integrity rules. No new logged-in-only generic file grant is introduced.

Controlled files validate the Assistance namespace and stream that opened handle.
PDF-signature files and Pillow-verified JPEG/PNG/GIF retain inline previews with
no-sniff and a sandbox CSP; other uploads are forced binary downloads. This is
not antivirus qualification or proof that an arbitrary PDF is safe. File responses
are private/no-store. Private HTML uses same-origin referrers so HTTP-development
CSRF still works and external destinations receive no private URL; file responses
use no-referrer. There is no CSRF exemption or trust for a null Origin.

The DEBUG media handler denies the four reviewed namespaces: `records/`,
`reporting/outputs/`, `vouchers/` and `assistance_docs/`, using normalized path
components, case-insensitive matching and rejection of traversal, backslashes,
absolute/drive paths and redirected filesystem targets. Ordinary public assets
remain available. This does not classify every other legacy media directory.
Production reverse proxies/object storage must enforce equivalent restrictions;
Django cannot control a web server that serves the underlying private bytes
directly. No storage relocation, production configuration or deployment occurred.

## Validation and remaining acceptance

PASS final frozen code: focused SQLite157/157 (11.562s, zero skips) and native
MySQL8.4.11 Assistance/Telegram/Records/auth-concurrency96/96 (14.618s, zero skips).
The native process completed before it could be interrupted after the owner asked
to skip remaining checks. Its owned server stopped; the original template hashes
are unchanged. Both runs used exclusive disposable stores. Earlier broader SQLite
1227 tests passed with101 native-only skips; that run predates final safeguards
and is reused only for unaffected module coverage. No full final suite is claimed.

Three regressions fail against unchanged199 with assertion failures/zero errors:
duplicate-PIN edit500, tracker attachment disclosure and anonymous raw-media200.
All28 AssistanceFlowTests pass on the final source, including24 added cases.
Existing test identities/classes/shard owners are unchanged; discovery3023→3047
and the existing eight partitions remain complete/distinct. No CI gate was changed.
Framework/schema checks, dependency checks/audit, runner tests9/9, AST parsing and
diff whitespace checks passed. Exact commands and investigated intermediate
failures are recorded in [the handoff](../CONTINUE.md).

Actual synthetic browser proof passed submission, same-token edit, upload/replace/
remove, staff image/PDF preview, public status, expired recovery, approved-case
locked reading and registered-email renewal. SAMEORIGIN framing preserves staff
PDF previews. Final mobile/screenshots were inspected. No real external message
or operator data; original fixture/file and copied Finance hashes are unchanged.
All owned browser/test servers stopped. Missing synthetic brand/avatar assets
remain fixture404s, not accepted form or production rendering evidence.

NOT RUN — further/full/hosted checks: the owner requested the local VM checkpoint
and pause. Nothing was merged, pushed or deployed; published master stays187.
Hosted exact-candidate and published-master checks remain required before any
future authorized publication. Prior baseline CI does not validate this slice.

Mandatory publication/operational gates remain: hosted full candidate/master CI
at the exact revision, legacy-link communication/recovery assistance, verified
registered-mail delivery and the existing shared default-store counter lifecycle
in the intended topology,
HTTPS/private URL log redaction and backup/recovery/storage qualification. Request
URLs can appear in browser history and same-origin/server logs; access to those
logs must be protected and token paths redacted before operational acceptance.
Generic responses do not establish constant-time email-account indistinguishability:
delivery remains synchronous, and no asynchronous mail infrastructure is added.
Unreviewed legacy media namespaces and pre-existing bot associations remain
explicit privacy-review work. Historical form/financial/LGU acceptance is unchanged.

This development is not a complete privacy audit, production migration,
publication/deployment authorization or formal acceptance. Finance remains NO-GO.

## Retained legacy attachments — 2026-10-19

After local201, source tracing found migration0002 stored RequestDocument files
under `assistance_uploads/year/month`;0003 only altered upload_to to assistance_docs.
It did not move old files. Both controlled Assistance and linked Records readers
therefore rejected a retained valid legacy file while generic DEBUG media could
still expose it. No actual historical/operator attachment was inspected.

Four new tests reproduce six assertion failures/zero errors against unchanged201:
raw legacy200 including case variants, citizen/staff/Records controlled404, and
corrupt PNG500. The corrected shared namespace check accepts either retained root,
then enforces existing containment/redirect/path rules. It opens no file itself;
each reader validates/streams its same opened handle. Office, token, current-case,
removal and native Records audit authority remain unchanged. No migration, file
move, path rewrite, historical import or fabricated hash/size baseline.

Pillow's explicit SyntaxError for an invalid PNG checksum now falls back to binary
attachment delivery. No executable inline preview or artificial repaired image is
created. The same policy already applies to unknown uploads. DEBUG raw delivery
denies assistance_uploads as well as the previously reviewed confidential paths.
Other legacy media and production web-server/storage qualification remain open.

All49 Assistance-flow/linked-Records cases pass, including four new methods kept
in existing classes. Real synthetic browser proof opens the same retained PNG in
citizen/MSWD previews, rejects raw access with404 and saves its exact original
bytes through the native Records Download action, with one audit event. Original
source pair/file and copied Finance hashes remain unchanged; browser/server stopped.
Screenshots were inspected. Missing fixture branding/avatar404s remain separate.
Fresh dependent verification, commands, local version and remaining gates belong
to [CONTINUE.md](../CONTINUE.md). This is not historical migration or LGU acceptance.
