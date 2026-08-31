# Finance evidence register

The register is an index, not an evidence repository. Keep confidential or controlled artifacts in the LGU-approved evidence location and record only a safe locator and access owner here.

## Field contract

| Field | Required content |
|---|---|
| Evidence ID | Stable `EV-###` identifier. |
| Label | `Observed in eGAPS`, `Official reference`, `LGU-confirmed`, `GRAND-implemented`, or `Unresolved`. |
| Title and version | Human-readable artifact or authority name, revision, and effectivity date when known. |
| Supports | Specific step, field, balance, certification, signature, number, output, exception, or decision. |
| Source/custodian | Public issuing body or responsible office/role; never a private employee name. |
| Safe locator | Public URL, repository path, or access-controlled reference that reveals no secret. |
| Sensitivity | `Public`, `Approved blank`, `Synthetic`, `Redacted controlled`, or `Restricted—not copied`. |
| Verification | Who compared it, when, and how authenticity/version was checked. |
| Status | `Proposed`, `Verified`, `Superseded`, `Rejected`, or `Expired`. |
| Related IDs | Steps, transactions, decisions, replays, and replacement evidence. |
| Acceptance | Named office/role, result, date, and safe acceptance reference. |

## Repository-safe baseline entries

| Evidence ID | Label | Title and version | Supports | Source/custodian | Safe locator | Sensitivity | Verification | Status | Related IDs | Acceptance |
|---|---|---|---|---|---|---|---|---|---|---|
| EV-001 | Official reference | Budget Operations Manual for LGUs, 2023 Edition | National budget-cycle terminology and baseline controls; local applicability remains to be confirmed | Department of Budget and Management | [Public DBM PDF](https://www.dbm.gov.ph/wp-content/uploads/Issuances/2023/Local-Budget-Circular/Budget%20Operations%20Manual%20for%20LGUs%2C%202023%20Edition.pdf) | Public | Confirm current issuance and applicability before implementation | Proposed | DEC-004 | Pending Budget/legal confirmation |
| EV-002 | Official reference | eBudget for LGUs User Manual v2, 2021-11-23 | Reference navigation, fields, and outputs; does not prove local eGAPS behavior | Department of Budget and Management | [Public DBM PDF](https://www.dbm.gov.ph/wp-content/uploads/LGRCB/eBudget-for-LGUs/DBM_E-BUDGET-for-LGUs_USERS-MANUAL_v2_20211123-%281%29.pdf) | Public | Compare against authorized local walkthrough; do not infer hidden rules | Proposed | DEC-004 | Pending Budget confirmation |
| EV-003 | Observed in eGAPS | Authorized read-only inspection summary | Visible client navigation, configuration, and outputs only | Authorized discovery team | [Modernization plan](../EGAPS_GRAND_PLAN.md) | Repository-safe summary | Scope and limits recorded in project documentation | Verified | DEC-001, DEC-002 | Not LGU process acceptance |
| EV-004 | GRAND-implemented | Finance process-fidelity baseline | Current GRAND coverage and known gaps | GRAND delivery team | [Process-fidelity baseline](../FINANCE_PROCESS_FIDELITY_BASELINE.md) | Repository-safe summary | Must be rechecked against the implementation at each slice | Verified | DEC-001, DEC-002, DEC-003 | Not LGU acceptance |
| EV-005 | GRAND-implemented | Finance complete-cycle roadmap | Delivery order, evidence labels, exit gates, and current product position | GRAND product authority | [Canonical roadmap](../FINANCE_ROADMAP.md) | Repository-safe project record | Accepted as the project delivery baseline | Verified | DEC-001, DEC-002, DEC-003 | Project-level acceptance only |

## New-entry template

Copy one row per independently verifiable authority or artifact. Split a packet into child evidence IDs when pages have different custody, sensitivity, version, or acceptance.

| Evidence ID | Label | Title and version | Supports | Source/custodian | Safe locator | Sensitivity | Verification | Status | Related IDs | Acceptance |
|---|---|---|---|---|---|---|---|---|---|---|
| EV-___ | Unresolved |  |  |  |  |  |  | Proposed |  | Pending |

## Verification checklist

- Confirm the issuing body, document title, version, effectivity, and superseding issuance.
- Confirm the artifact belongs to the selected fiscal year, fund, transaction type, and office route.
- Distinguish blank form geometry from a completed example and from an operator recollection.
- Record control totals independently; do not copy a displayed total without recomputation.
- Record whether an observation proves visibility, a performed step, a validation, or an authority.
- Link contradictory evidence to a decision-log item and leave the affected finding Unresolved.
- Re-verify time-sensitive authorities before design acceptance, UAT, and cutover.
