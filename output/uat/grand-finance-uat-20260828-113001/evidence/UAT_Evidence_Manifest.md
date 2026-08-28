# GRAND Finance End-to-End UAT Evidence Manifest

- Run date: 28 August 2026
- Classification: Synthetic UAT only — do not pay
- Worktree: `C:\Users\Administrator\Desktop\GH\grand-finance-complete-cycle`
- Overall result: **PASS — 11 of 11 phases**

## Safety boundary

- Only the isolated worktree's `db.sqlite3` and `grand_finance.sqlite3` were used.
- Verified baseline copies are preserved under `tmp/uat-backups/20260828-113001/`.
- The primary GRAND checkout and eGAPS were not accessed or mutated.
- No real payment, official check printing, bank transmission, production cutover, or Records filing occurred.
- The real administrator's identity, password, and session details are excluded from stakeholder-facing evidence.

## Synthetic actors

| Display name | Username | Assigned department | Result |
|---|---|---|---|
| Budget Officer | `budget.officer` | Budget | Active; password hash verified |
| Accounting Preparer | `accounting.preparer` | Accounting | Active; password hash verified |
| Accounting Reviewer | `accounting.reviewer` | Accounting | Active; password hash verified |
| Treasury Officer | `treasury.officer` | Treasury | Active; password hash verified |

## Synthetic signatories

| Name | Position | Evidence use |
|---|---|---|
| Maria L. Santos (UAT) | Department Head | Initial wet-signature round |
| Elena R. Cruz (UAT) | Municipal Accountant | Both signature rounds |
| Ramon P. Flores (UAT) | Acting Department Head | Pre-check replacement signatory |

No signature images or simulated digital signatures were used.

## Expected versus actual

| Phase | Expected | Actual |
|---|---|---|
| 1 | Isolated baseline and backups | Passed; branch-local database guard and verified backups |
| 2 | Four exact users and role groups | Passed; assigned departments and explicit permissions verified |
| 3 | Controlled Office-compatible workbook | Passed; 11 named mappings, 8 line rows, print area, no macros/links |
| 4 | Preflight, approval, activation | Passed; active release with workbook and mapping checksums |
| 5 | Accounting setup | Passed; August 2026 period, fund, GSO center, expense/payable/EWT accounts |
| 6 | Budget certification | Passed; `UAT-OBR-00001`, ₱1,000.00, `UAT-APPROPRIATION-001` |
| 7 | DV and signatures | Passed; `UAT-DV-00001`, ₱1,000.00 gross, ₱100.00 EWT, ₱900.00 net |
| 8 | Validation and posting | Passed; `UAT-JEV-2026-0001`, posted and balanced ₱1,000.00/₱1,000.00 |
| 9 | Date/signatory amendment | Passed; Aug 28 → Aug 29, Maria → Ramon, number/amounts/JEV preserved |
| 10 | Treasury cycle | Passed; `UAT-000201` cancelled, reuse blocked, `UAT-000202` released |
| 11 | Configurable exemption | Passed; strict self-validation blocked, scoped exception demonstrated, then deactivated |

- Primary case: `CASE-2026-BE57E5B35F` — Completed
- Advice: `UAT-ADV-0001`
- Receipt: `UAT-RECEIPT-0001`

## Office compatibility

- Microsoft Excel 16 opened the authored workbook and both generated workbooks read-only.
- All three are file format 51 (`.xlsx`), have two worksheets, no VBA project, and zero external links.
- Microsoft PowerPoint 16 opened the 18-slide deck read-only; all 360 objects were present.
- Layout inspection found zero objects outside the 1280 × 720 slide canvas.
- See `office-compatibility.json` for the structured result.

## Test evidence

- Django system check: passed.
- Finance suites: 42 tests passed across `vouchers`, `finance`, and `accounting`.
- GRAND template preflight: passed with 11 required mappings and a valid print area.
- Browser verification: synthetic Accounting user, cropped screenshots, no CRUD performed during screenshot capture.
- UAT script result: `uat-results.json`.

## Preserved artifacts and SHA-256

| Artifact | SHA-256 |
|---|---|
| `GRAND_UAT_DV_v1.xlsx` | `B1DFA777F822CD859E72E66F91A586B8B382D769AF1ABC9C4CA308BC4EFEF8AB` |
| `GRAND_UAT_DV_generated_v1.xlsx` | `1F1F8D38C576C0669FB2961F0EDC5F25768C0E33EADFEF42EBB4DA343ABF916B` |
| `GRAND_UAT_DV_generated_v2_amended.xlsx` | `23F3ECD37E098A7669A424A962AEB05E56051942FFB7214140B375BD65728E92` |
| `GRAND_Finance_UAT_Stakeholder_Walkthrough.pptx` | `6E8DFD4D8E400C42EB75F718C9E75416F20FCD741C813AFADB2CA1D63C9C3B4E` |

## Screenshot index

- Finance Setup readiness, controlled template preflight, signatories, numbering, and readiness checks.
- OBR allocation, DV amounts, wet-signature circulation, posted JEV header/balance and journal lines.
- Completed non-financial amendment and checksum-backed output versioning.
- Cancelled/replacement check lineage and the standalone completed workbench.

## Intentional limitations

- The run uses only synthetic data and a local development server.
- No official-use promotion, Records filing, external bank interface, or production deployment was attempted.
- The workflow-exemption demonstration case stops at Accounting posting after proving the block/allow/deactivate control sequence; the primary case alone is the complete payable cycle.
- Guided manual UAT can now focus on usability, wording, browser-specific behavior, and repair backlog rather than waiting for missing workflow phases.
