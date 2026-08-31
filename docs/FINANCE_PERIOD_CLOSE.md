# Finance period close and controlled reopen

## Checkpoint position

F7.4 is an implemented synthetic-control checkpoint for Accounting period close. It replaces the prior one-click close action with a governed checklist, immutable evidence, independent approval, and an ordered reopen route. It does **not** by itself certify an official signed financial statement or prove that a public close recommendation is the LGU's accepted local procedure.

## Working flow

1. Accounting resolves every JEV in the target period and closes earlier periods first.
2. The preparer records the adjusting-entry and applicable closing-entry review plus a readable retained-evidence reference.
3. GRAND pins the current close-policy version and evaluates the posted trial balance, subsidiary controls, mapped bank reconciliations, statement runs, source-system JEV handoffs, and year-end nominal balances.
4. A controlled starter begins in **Observe** mode. Core integrity gates block close; locally unconfirmed recommendations remain visible warnings.
5. A human-modifiable successor may use **Enforce** mode only after maker–checker review records its authority and local acceptance evidence.
6. Submission locks the policy/checklist JSON snapshots and SHA-256 checksums. A different authorized reviewer approves or returns the evidence. Changed source evidence forces refresh and resubmission.
7. Approval closes the period and blocks new posting.
8. Reopening requires a reason, retained authority, and an independent decision. Later closed periods must reopen first. The old close evidence remains immutable, and corrections require a successor close checklist.

## Export and safekeeping

The evidence CSV includes the pinned policy, each control result, messages, retained machine evidence, event history, and checksums. Every download is also archived under GRAND's single TraceSync-ready root:

`department / user / finance-period-close / year / month / artifact`

The adjacent manifest records the SHA-256 checksum and artifact metadata. Copy or synchronize the whole export root so artifacts remain beside their manifests.

## Internal guidance

The Period Close register and detail page provide a floating `?` window that stays over the current work. A department-specific Internal How-To covers preparation, independent review, ordered reopen, and export. Progress belongs to the current user and guide version; it is not transferred to a replacement employee and it never changes transaction authority.

## Public-source basis and local acceptance boundary

The controlled starter is informed by public COA materials that describe pre-closing trial balance after adjusting JEVs, closing JEVs, post-closing trial balance, reconciliation of supporting schedules, and year-end financial-statement responsibility. Relevant public references include:

- [COA Circular No. 2002-003 / New Government Accounting System Manual for LGUs](https://www.coa.gov.ph/wpfd_file/coa-circular-no-2002-003-june-20-2002/)
- [COA Barangay Financial Management, Chapter X](https://www.coa.gov.ph/wp-content/uploads/ABC-Help/Financial_Management_Brgy/ba1.1.htm)
- [COA Government Accounting Manual financial-reporting workflow](https://coa.gov.ph/wp-content/uploads/abc-help/gam_b/fr1.33.htm)

The barangay material and the Government Accounting Manual workflow are contextual control references, not automatic proof of the exact current LGU schedule, responsibility assignment, form, signatory, timing, or close policy. The Municipal Accountant and other named owners must confirm the applicable current authority, local memo/calendar, retained supporting schedules, and signed outputs before Enforce mode or official use.

## Remaining F7 and acceptance work

- verify the exact local monthly/year-end calendar, adjustment and closing-entry responsibilities, evidence packet, review sequence, and reopen authority;
- compare the control checklist with redacted consecutive local closes and reproduce signed reference outputs;
- validate statement notes, current tax/BIR outputs, locally accepted schedules, printer/paper handling, recovery, and named-office acceptance;
- broaden subsidiary ledgers where the discovered local process requires them.

No historical eGAPS migration or runtime dependency is introduced.
