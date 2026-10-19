# Obligation service line validation

## Reproduced gap

Local parent v0.7.203 is `5ad07d052324b744332164cd894592fa597b64d5`.
`ObligationRequestLine.clean` already requires a positive amount, the request's
exact authorized appropriation and Budget office, and a movement appropriate to
the request kind. Field validation also rejects unknown movement choices. The
form calls these rules, but the submission/certification service validated only
the header and aggregate financial effect. Saving draft models does not imply
`full_clean`; final movements are intentionally materialized by bulk creation.

Direct synthetic calls therefore accepted foreign-appropriation lines, mismatched
office metadata, zero/negative amounts, unknown movement types and unlinked
original reductions. Returns/cancellations could increase the obligation instead.
Final certification accepted invalid stored office/appropriation links too. This
does not demonstrate that an ordinary form can create every malformed line, or
that any production record was affected. It demonstrates a missing final service
boundary for existing financial rules.

## Minimal repair and behavior

`validate_obligation_request` calls each loaded line's existing `full_clean`
before projecting its financial effect. Submission and final certification already
share this validator. The final writer keeps its appropriation-line lock and
transaction; failure happens before movements, checksum, status, assigned number
or audit event are committed. The current HTTP action uses its existing guided
error/redirect behavior. No new local policy or duplicated financial rule.
Malformed stored rows are rejected, not silently repaired or removed; no existing
certified history is rewritten. This fix does not reconcile real legacy records.

Valid original obligations, linked reductions and positive adjustments retain
their independent approval, signed totals and exact original source history.
The dated-capacity control from v0.7.203 remains intact. No model, migration,
permission, database routing, journal recipe, source inference or form change.
Separate Finance/default stores, office/UAT boundaries, maker-checker controls and
downstream issuance/correction lineage remain mandatory.

## Regression evidence and limits

Nine new cases stay in the existing Budget test class; all prior test identities
and CI class/shard owners are retained (3071→3080). The cases cover the malformed
lines above, revalidation at certification, an authenticated HTTP rejection, and
permitted linked corrections with unchanged original movements.

Unchanged-parent proof:9 tests,10 expected assertion failures,zero errors,2.684s.
One positive case passes there; the extra failures are amount/direction subcases.
Corrected proof:9/9 pass,zero skips,3.724s. The original synthetic two-store/file
fixture remains unchanged, and the disposable Finance copy returns to the original
bytes after rollback. No operator data, mail or real transaction.

Fresh dependent SQLite:285 discovered,273 pass/12 native-only skips,182.061s.
Fresh native MySQL8.4.11/strict mode:285/285,319.677s,zero skips, including all12
races. Both aliases destroyed, owned server stopped, original template and tested
source hashes unchanged. Exact commands and local v0.7.204 checkpoint are recorded
in [CONTINUE.md](../CONTINUE.md). Scope includes Budget core/quarterly, payable
handoff, schedule office identity, central vouchers, and original, cancelled and
returned advance corrections. Actual label discovery includes12 imported existing
historical-forecast cases omitted by an initial273-ID prefix filter; all285 unique
IDs are now retained. No inherited test or CI gate is changed.

The new HTTP case checks the actual field-validation message and pending state.
The existing rendered Budget action/error layout is unchanged; the v0.7.203
synthetic browser result remains evidence for that unchanged layout only. No new
browser run, clerk/printer acceptance or production qualification is claimed.

Hosted whole-chain exact-candidate/master CI and publication remain unauthorized.
Finance stays **NO-GO** pending functional, financial-control, operational/recovery
and formal acceptance gates. No deployment or production operations.
