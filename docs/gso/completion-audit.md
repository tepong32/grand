# GSO completion audit

GRAND follow-up, 2026-10-18: the source-baseline observations below are historical.
The [GRAND handoff](../../CONTINUE.md) owns v0.7.176 integration and the current
unpublished ICS/SPC preparation/source-worksheet work. Working drafts do not close
official-form, operational or Finance acceptance gaps.

Checkpoint: 2026-10-17. Rechecked published baseline89890e1, fetched master and
working tree clean and equal before this documentation audit. This is a finite scope audit, not a new feature list or compliance
certificate. The overall goal is incomplete. [CONTINUE](../CONTINUE.md) owns the
current checkpoint; the [roadmap](inventory-roadmap.md) and
[COA matrix](coa-requirements.md) retain the full requirements and source limits.

## What is available in code

The register, reviewed receiving, named custody/handoffs/returns, maintenance,
physical counts/reconciliation, supply requests/issues/returns, property packets
and reviewed movement reconstruction have documented implementations and test
receipts. Optional Finance links preserve separate physical and financial authority.
General correspondence uses native GRAND Records through the GSO dashboard.
See the linked feature documents in the roadmap for each workflow's limits.

These are code capabilities, not an installed LGU service. No operator migration,
role assignment, production deployment or official-form acceptance has occurred.
GRAND candidate a533482 and its remote master32ab046 remain distinct. Its handoff
still states production NO-GO; GSO release checks cannot satisfy that gate.

## Remaining work and selected approaches

| Gap | Selected approach | Required evidence before completion |
| --- | --- | --- |
| Follow-up acceptance of delivered but unresolved quantities | Linked follow-up inspection is now implemented with local validation complete; see [its design](receiving-followups.md) and CONTINUE for publication. It preserves the original accepted receipt and reuses existing review/materialization. Do not treat a later delivery as the old remainder. | Trace asset/stock links and Finance claim ceilings first; define exact retry, cumulative capacity, independent review and stale-support behavior. Implement and test a complete staff workflow before release. |
| Mistaken accepted quantity / physical reversal | The user-selected [clerical overstatement before use](receipt-quantity-corrections.md) has a reviewed workflow published at33cd899: source-lot adjustment or retained erroneous asset, original facts unchanged. See CONTINUE for release state. | Native races, source/hold checks, populated migration, real GRAND, browser and restore evidence are recorded in validation. Cases after use, changed inspection decisions and actual returns remain explicit reconciliation, not automatic repair. |
| Physical cost allocation and valuation | Keep documentary amounts separate from Accounting's approved treatment. Reuse native Finance dimensions and journal lineage, not another ledger. | Accountant-confirmed allocation basis and representative delivery/claim/component cases; prevent duplicate capacity and preserve unknown costs. |
| Official PAR/ICS/SPC/RPCPPE/RPCI/RSMI outputs | User authorizes fill-in placeholders while local details are unknown. PAR is available; ICS/SPC preparation, the scoped asset-to-ICS shortcut and a reviewed SPC source worksheet are implemented locally in GRAND. See [their contract](property-record-design.md#working-draft-preparation--2026-10-18) and current handoff for verification. These remain working records; no certified class/fund total or valuation is asserted. | Applicable issuance text, effectivity/amendment review, actual municipal template and numbering/sign-off process. No generated signature or implied approval. |
| Imported history and openings | Use explicit source-to-target identity maps and reviewed openings; preserve unreconciled records. | Representative export and source ownership, exclusion of prototype authentication/session data, department/user/Finance identity mapping, duplicate decisions and repeatable restored-copy import validation. Never match numeric IDs or names automatically. |
| Loss and relief from accountability | Distinguish missing-item findings, investigation, authorized relief and disposal. Do not retire or derecognize from a missing finding. | Verified applicable process and authority, evidence requirements and real office scenarios. A new incident form alone would not complete relief processing. |
| General office filing | Reuse native GRAND Records, already linked. Add operational associations only through its explicit supported-source policy. | A concrete filing use case and native ownership/confidentiality/retention/recovery review before adding inventory associations. |
| Vehicle use/fuel or additional office records | Do not expand into a fleet/procurement ERP by inference. Existing vehicle register and maintenance remain usable. | Confirmed record type and office process before adding more schema. This is conditional scope, not a fabricated blocker to existing workflows. |
| Production and recovery | Follow GRAND's two-store recovery and deployment procedure, including all private evidence/media. | Target environment, operator roles, disposition of the verified historical authentication exposure, protected storage, actual restore/RPO/RTO and operational acceptance. Synthetic drills and CI do not establish production readiness. |

## Why the next engineering item is concrete

`ReceivingLine` permits delivered quantity greater than accepted plus rejected.
`receiving.accept_receipt` materializes the accepted portion once, then makes the
receipt accepted/read-only. Each line currently has one registered asset or stock
movement link. At this audit baseline there was no follow-up remainder service; the subsequent development is tracked in the linked design. This is an observed source
gap, not an assumption based on a feature name. A naive second stock receipt or a
change to the original quantity would lose lineage or distort downstream support.

The follow-up implementation traces existing claim attribution, documentary cost
amendments, recognition mappings and property source snapshots. Its linked design
records the selected extension and remaining acceptance boundaries. The audit itself selected no schema or financial rule; the follow-up design records the subsequent minimal schema decision. The current
safe behavior remains documented in [receiving](receiving.md).

## Validation and stopping boundary

This audit reconciles committed source and existing test/publication evidence; it
does not claim new runtime or legal validation. Ordinary receiving design work can
continue without an official form or deployment decision. Do not call the whole
goal blocked while that meaningful work remains, and do not call it complete when
one code milestone ships. Record a specific missing external input only when it
actually prevents the corresponding work.

For the eventual completion review, demonstrate the agreed office scenarios in
the integrated installation, reconcile imports, verify scoped authority and
recoverability, and obtain the required local acceptance. Preserve unsupported
cases and deferred scope explicitly instead of adding speculative features to
keep an automated goal running.
