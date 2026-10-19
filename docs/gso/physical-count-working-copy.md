# Physical-count reconciliation working copy

The count's Accounting comparison now links to **Print working reconciliation**.
The authenticated GET/HEAD working copy reuses the existing comparison projection
and exact read/office scope of its CSV export. It selects one Accounting import
once and identifies it beside the count date, round state and generation time.
It is a current working comparison, not an immutable issued or approved output.

## Staff workflow and source meaning

Open a physical verification round, choose Accounting comparison, then Print
working reconciliation. Review the preview and use Print / Save as PDF. Return to
the comparison for source review; this reader does not edit a count or import.

All existing comparison groups are retained without a row cap: matched by unique
GSO tag, GSO only, Accounting only, ambiguous Accounting tags and unregistered
findings. Ambiguous tags do not select a GSO record automatically. No Accounting
snapshot still permits a working GSO count copy, with its absence explicit.
An Accounting-only row does not become a physical finding or a missing asset.

GSO facts come from the count snapshots, rather than later live asset edits.
Accounting facts come from the selected imported rows, rather than a live Finance
query. The two names, tags, serials, offices, accounts, purchase dates and recorded
costs remain separate. Zero prints as zero; an unrecorded value stays unrecorded.
No quantities, accounting values, cross-source totals or signatures are invented.
Physical results, observations and existing follow-up/review notes remain visible.

The read permission is unchanged: explicit asset view plus an existing
verification start/record/close/import read grant, within the owning GSO scope.
Read-only UAT access remains usable. A superuser without an explicit grant is
denied. Current permission revocation takes effect on the next request. No new
permission, automatic grant, model, migration, storage, routing or Finance change.
Responses are private/no-store and nosniff. POST is rejected; source files are
not exposed or regenerated. Printing does not certify their file integrity.

## Printing and verification

The screen uses labelled keyboard-focusable horizontal table regions on small
devices. Print uses readable A4 landscape tables, repeated headers and source
round/date plus page numbers in browser-supported page margins. Long descriptions
wrap and rows avoid splitting. A browser without margin-box support may omit
those margin footers; physical printer/local-form acceptance remains separate.

Nine added cases stay in the existing RPCPPEDraftTests class; they exercise this
distinct source-backed working copy, without changing the supplied RPCPPE draft.
Unchanged local204 yields nine expected assertions/zero errors for the missing
route/link (1.504s). Corrected final proof passes9/9,zero skips,2.315s. Cases cover
all groups, missing Accounting data,114 count records, zero/unknown costs, retained
snapshots, escaped text, latest-source selection, live permissions/office/UAT,
GET/HEAD/private headers and absence of Inventory writes or Finance queries.

Actual browser checks follow the comparison link as a clerk and open the copy as
a UAT reader. The final five-page A4 PDF was rendered and every page inspected;
all source markers and round/page footers remain present. Mobile390px viewport
has375px document width; horizontal overflow stays within the table regions.
All Inventory source rows, the original synthetic pair/files and exact Finance
bytes remain unchanged. Browser and owned loopback server are stopped.

Initial private proof setup collided with retained synthetic department/user
names (zero tests executed). Only the exclusive disposable default copy was
renamed for the fixed test fixture; original sources and assertions are unchanged.
The first CLI PDF used its default Letter size. Final export explicitly respects
CSS A4; a restarted private WSGI server loaded the final print styles rather than
its earlier cached templates. Earlier PDFs are intermediate artifacts, not final
source evidence. Synthetic branding/favicon404s are fixture limitations.

Fresh broad GSO SQLite:429 discovered,398 passed/31 existing native-only skips,
85.834s,exit0; both aliases destroyed and final source hashes retained. The
unchanged native-only scenarios are not claimed as passes. A new native run is
out of scope for this reader: no Finance/persistence/schema/lock/routing change,
and the existing comparison queries are reused. Fresh auth/data-integrity cases
and actual browser/source/Finance hashes verify this new read-only path. The
earlier204 native result applies only to its unchanged contracts, not this view.
Framework/schema checks pass; no migration. Exact commands/local205 checkpoint
are in [CONTINUE.md](../../CONTINUE.md). Full hosted CI/publication, official RPCPPE,
Accounting valuation, printer/office acceptance, coordinated recovery and formal
LGU/GSO operational acceptance remain open. Finance remains **NO-GO**. No deployment
or production operation; no real historical import or financial/custody mutation.
