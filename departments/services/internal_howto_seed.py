from __future__ import annotations

from django.db import transaction

from ..models import Department, InternalHowTo, InternalHowToStep


ACCOUNTING_GUIDES = (
    {
        "slug": "finance-fiscal-foundation-manager",
        "version": 1,
        "title": "Prepare the fiscal-year foundation",
        "summary": "Build and hand off the governed calendar and classifications, then export one retained review register.",
        "permission": "accounting.manage_accounting_setup",
        "patterns": ["accounting:setup*"],
        "order": 5,
        "steps": (
            ("Create or adopt the typed year", "Open Fiscal-year and accounting setup. Create the intended year or adopt the exact independently approved Finance Setup release, then confirm its dates, business date, version, and source checksum.", "One draft typed year identifies the source release or the named manual preparation basis.", "Adoption copies governed values; it does not approve the year or establish opening balances.", "Open Accounting setup", "accounting:setup"),
            ("Complete the calendar and shared dimensions", "Add the real periods, funds, responsibility centers, posting accounts, funding sources, and PPA/MFO/project/activity hierarchy. Use readable authority references and effective dates.", "Later screens can select governed codes instead of asking staff to retype them.", "Do not guess local COA/DBM applicability or activate a starter merely because its code looks familiar.", "", ""),
            ("Check the five readiness rows", "Read the structural result under Technical, Budget, Accounting, Treasury, and Forms. Complete the linked setup and opening-control work before asking an independent approver to decide each layer.", "Every failed structural result names the work still needed.", "A green structural check is not an approval and does not replace retained local evidence.", "Open Opening Controls", "accounting:opening_workspace"),
            ("Correct only inside the modification window", "Before any DV or payment instrument is issued for the affected year, use Edit and record the exact reason and supporting reference. Resubmit after the affected readiness decisions reopen.", "The before/after audit event and repeated independent review remain reconstructible.", "After issuance, use the applicable successor, return, reversal, cancellation, or replacement workflow; never rewrite used history.", "", ""),
            ("Export the review register", "Choose one typed year, or all years, under Portable foundation register and download the CSV. Send or preserve the complete TraceSync export folder with each manifest beside its artifact.", "The retained register contains readiness, periods, classifications, mappings, authority references, counts, and checksum evidence for the current department.", "The register is a review aid. Exporting it does not approve, activate, or authorize production use.", "Open Accounting setup", "accounting:setup"),
            ("Submit for independent review", "Submit the completed fiscal-year definition. Give the approver the retained source references and foundation-register location needed to reproduce your review.", "The year enters For review with the submitting user and state version recorded.", "The preparer or submitter cannot approve the same fiscal year.", "", ""),
        ),
    },
    {
        "slug": "finance-fiscal-foundation-review",
        "version": 1,
        "title": "Review fiscal-year readiness independently",
        "summary": "Review the governed fiscal year and each readiness layer without becoming its preparer.",
        "permission": "accounting.approve_fiscal_readiness",
        "patterns": ["accounting:setup*"],
        "order": 6,
        "steps": (
            ("Confirm independence and scope", "Open the submitted typed fiscal year and verify the Accounting office, year, state version, preparer, submitter, source release, and checksum.", "The review concerns one exact department and fiscal-year definition prepared by another user.", "Do not approve on another person's account or review a year you prepared or submitted.", "Open Accounting setup", "accounting:setup"),
            ("Reproduce the foundation register", "Export the selected fiscal year and compare its periods, funds, centers, accounts, funding sources, program hierarchy, mappings, and readiness rows with the retained local sources.", "Every reviewed classification and evidence note is visible in one checksummed, archived register.", "An export is evidence of what was reviewed; it is not itself proof that a source is current or locally applicable.", "", ""),
            ("Approve or return the year definition", "Approve the submitted fiscal year only after its governed dates and source lineage agree. Return the work through the applicable setup correction route when they do not.", "The approver is recorded separately from the maker and submitter.", "Year approval alone does not approve the five readiness layers or make the year active.", "", ""),
            ("Decide every readiness layer", "For each structural result, read the actual retained evidence and enter a specific authority or acceptance reference. Approve only when both the structural result and evidence pass; otherwise return it for a named correction.", "Technical, Budget, Accounting, Treasury, and Forms retain independent decisions and state versions.", "Do not use a generic note or infer Treasury/form readiness from Accounting data checks.", "", ""),
            ("Activate last", "Activate only after the fiscal year is approved and all five readiness layers pass. Recheck that the opening batch is independently approved, posted, and reconciled with zero difference.", "Exactly one active fiscal year governs new work for the Accounting office.", "Activation is still not production cutover authority; F11 field evidence and the separate exact-scope decision remain required.", "", ""),
        ),
    },
    {
        "slug": "finance-accounting-period-close",
        "version": 1,
        "title": "Close and, when authorized, reopen an Accounting period",
        "summary": "Finish period work, prepare checksummed close evidence, obtain an independent decision, and retain the ordered reopen trail without leaving the current page.",
        "permission": "accounting.view_accounting_workspace",
        "patterns": ["accounting:period_close_*", "accounting:workspace", "accounting:setup"],
        "order": 58,
        "steps": (
            ("Resolve period work", "Finish each JEV by posting it or using its governed return, discard, or reversal route. Close earlier periods first.", "The target period has no unresolved JEV and its posted debit and credit agree.", "Do not edit posted evidence or close a later period ahead of an earlier open one.", "Open Accounting", "accounting:workspace"),
            ("Review adjustments", "Review adjusting JEVs and, for the fiscal-year end, applicable closing JEVs. Record what was checked and why no entry is required when that is the result.", "The close checklist carries a readable adjustment and closing-entry review basis.", "The system does not invent an adjustment or treat a blank note as evidence.", "Open Trial Balance", "accounting:trial_balance"),
            ("Prepare the checklist", "Choose the open period and record the retained packet, schedule, folder, or records reference. GRAND pins the current policy and reads current reconciliation, reporting, handoff, and ledger evidence.", "Required failures are red; locally unconfirmed starter recommendations remain visible as yellow warnings.", "A warning under observe mode is not proof that the LGU accepted an official local rule.", "Open Period Close", "accounting:period_close_workspace"),
            ("Submit independently", "Refresh after correcting sources, then submit the ready checklist to a different authorized reviewer.", "Submission locks the policy and checklist snapshots and their checksums.", "The preparer or submitter cannot approve the same close evidence.", "Open Period Close", "accounting:period_close_workspace"),
            ("Review and close", "Compare the retained references, checks, warnings, policy, and checksum. Approve only when the evidence is unchanged and sufficient; otherwise return it with a specific note.", "Approval closes the period and blocks new posting while preserving an append-only decision trail.", "Closing a period is not the same as certifying an official signed financial statement.", "Open Period Close", "accounting:period_close_workspace"),
            ("Reopen in order", "If a discovered error requires a posting, record the correction reason and retained authority. A different authorized reviewer decides the request. Reopen later closed periods first.", "The earlier close remains immutable; corrections require a successor close checklist and another independent approval.", "Never reopen merely to overwrite prior evidence or bypass a governed reversal or adjustment.", "Open Period Close", "accounting:period_close_workspace"),
            ("Export retained evidence", "Download the close evidence when the records packet or reviewer requires it. GRAND also archives the exact file and manifest under the single TraceSync-ready export root.", "The CSV contains the policy, every check, event history, and checksums in the department/user/category folder structure.", "Copy or synchronize the whole export root so manifests remain beside their artifacts.", "Open Period Close", "accounting:period_close_workspace"),
        ),
    },
    {
        "slug": "finance-accountability-reporting-accounting",
        "version": 9,
        "title": "Prepare, map, and review Accounting reports",
        "summary": "Prepare operational schedules and governed management statements from posted entries, explain every measure and equation, and retain portable reproduction evidence.",
        "permission": "reporting.view_reporting_workspace",
        "patterns": ["reporting:*", "accounting:trial_balance", "accounting:entry_*"],
        "order": 60,
        "steps": (
            ("Choose the report starter", "Open Reports and choose an operational schedule or either management financial statement. Confirm whether the report covers activity during a period or balances through an end date.", "The run pins the exact definition, template, period, output format, and applicable statement mapping.", "The starters follow accounting-control guidance but are not automatically the LGU's accepted signed forms or BIR returns.", "Open Reports", "reporting:workspace"),
            ("Check local applicability", "Read the authority/reference and applicability badge. Keep the definition as Local confirmation pending until the Municipal Accountant or named owner confirms the exact form, signatories, routing, and retained comparison evidence.", "Official-form claims remain separate from a technically correct report.", "Do not mark a public recommendation as locally accepted without actual confirmation.", "", ""),
            ("Generate and reconcile", "Generate the covered period. Confirm total posted debit equals total posted credit and that the control status reads reconciled.", "The report stores immutable row, control, freshness, and checksum evidence.", "A control exception cannot enter official review; correct the posted source through normal Accounting routes, then generate a successor.", "Open Trial Balance", "accounting:trial_balance"),
            ("Maintain the statement mapping", "Open Statement mappings. Compare the broad starter with the latest signed local statements and reviewed COA/GAM guidance. Create a readable successor, assign every active posting account exactly once, record the authority and local acceptance evidence, then submit it to a different authorized reviewer.", "An independently activated version becomes the pinned basis of new management statement runs while earlier versions remain reproducible.", "Do not activate a mapping merely because the broad starter generates a balanced equation; local statement acceptance is a separate decision.", "Open Statement mappings", "reporting:statement_mapping_list"),
            ("Explain the statements", "For financial position, verify Assets equals Liabilities plus Equity plus the visible unclosed operating result. For financial performance, verify posted Revenue less Expense equals the reported surplus or deficit. Review mapping coverage, period, source freshness, and JEV drill-through.", "Every dashboard measure and statement line has a definition, covered period, freshness time, control result, and retained source path.", "Closing a ledger period does not certify or accept the resulting statements.", "Open Reports", "reporting:workspace"),
            ("Prepare the statement notes", "Open Statement notes and select the reconciled position and performance runs for the same period. Complete each editable candidate topic from retained schedules, or mark it not applicable with a specific reason. Link it to pinned statement lines where useful.", "Submission freezes the disclosure text, linked runs, mappings, source evidence, and checksum for independent review.", "Candidate topics are prompts, not an automatic COA or local disclosure checklist. Confirm current applicability before locally accepted use.", "Open Statement notes", "reporting:statement_note_set_list"),
            ("Compare a signed reference safely", "From a statement run, create a signed-reference comparison using a redacted copy and enter each visible control total. Submit it so GRAND checks exact differences and pins the file and run checksums.", "A different reviewer can reconcile only a zero-difference comparison whose evidence has not drifted.", "Control-total agreement does not automatically prove labels, notes, geometry, pagination, form stock, or current official acceptance.", "Open Reports", "reporting:workspace"),
            ("Promote a checked layout", "After a different user approves the template for preview, open its promotion comparison. Use the accepted prior output for the same period and format, record the side-by-side form, signatory, pagination, overflow, and printer checks, then submit the retained preview.", "GRAND locks the template snapshot, automatic data/control comparison, impact list, and checksum before an independent approval and separate activation.", "Do not use the retired direct-fidelity shortcut or activate a layout with unresolved golden differences. Roll back with a reason if a production print problem appears.", "Open Reports", "reporting:workspace"),
            ("Accept the actual local form", "Open Local form acceptance after template activation. When useful, choose Use DBM starter and create the matching editable candidate. Compare every candidate section with the current blank/redacted local form, record whether it matched or does not apply with a retained reference, then confirm the actual source, delivery, people, copies, deadlines, custody, paper, pagination, overflow, and accessibility behavior. Perform every practical test and send each attempt to a different witness.", "A different form reviewer accepts only the exact checksummed reference and activated template after every candidate row is locally resolved and all required categories have a current witnessed pass.", "The 31 DBM starters are not installed official forms. An unmapped, unconfirmed, or inventory-only candidate cannot be accepted; failed attempts remain visible and accepted changes use a fully retested successor.", "Open Local form acceptance", "reporting:local_form_workspace"),
            ("Reconcile subsidiary schedules", "For payable and withholding schedules, compare the schedule balance with the mapped general-ledger control balance at the same end date. Resolve a missing mapping or difference in Subsidiary Controls before regenerating.", "The report advances only when immutable subsidiary details agree exactly with posted control accounts by fund.", "Do not force a schedule balance or use a tax working schedule as a filed BIR form.", "Open Subsidiary Controls", "accounting:subsidiary_controls"),
            ("Prepare governed tax schedules", "Choose Governed Tax Withholding Detail when certificate support needs voucher, payee, ATC, base, rate, and posted-JEV evidence. Choose Governed Tax Return / Remittance Summary when Accounting needs totals grouped by return form, tax family, ATC, and rate for the covered period.", "Each line is recalculated against its pinned locally confirmed rule, checked against the posted withholding movement, and retained with source drill-through.", "These are controlled source schedules, not filed BIR returns, issued certificates, proof of remittance, or automatic deadline advice. Restrict TIN-bearing exports to authorized Accounting custody.", "Open Reports", "reporting:workspace"),
            ("Drill through the total", "Use Source drill-through to open retained posted JEVs and compare fund, account, source reference, description, debit, credit, and posting evidence.", "Every reported control total is explainable from permission-checked source entries.", "Never edit a posted JEV to make a report agree; use a governed adjustment or reversal.", "", ""),
            ("Review and approve independently", "A different authorized reviewer checks the control evidence, source entries, exact local template, and applicability record before review and approval.", "The approval is attributable and the prior run remains retained if superseded.", "Pilot layouts and pending local applicability stay unavailable for official approval.", "", ""),
            ("Assemble the accountability package", "Open Accountability packages. Choose the independently accepted checklist profile and exact period, then select the approved Budget, Accounting, Treasury, statement-note, signed-reference, and verified tax evidence offered for each required slot.", "Submission freezes the profile, source UUIDs, periods, workflow states, and SHA-256 checksums for a different Accounting reviewer.", "Before approval, replace a mistaken selection only with a reason; after approval, create a linked successor. Use the source module's reversal or adjustment route for financial corrections—changing a report package never reverses a JEV or payment.", "Open Accountability packages", "reporting:accountability_workspace"),
            ("Export and safeguard", "Download the output, control-evidence CSV, and reproduction receipt when required. Copy or synchronize the complete GRAND export root so each artifact remains beside its manifest.", "TraceSync-ready department/user/category folders retain checksums and reproduction keys without user re-filing.", "Keep the complete export folder rather than isolated files without manifests.", "", ""),
        ),
    },
    {
        "slug": "finance-bank-advice-review",
        "version": 1,
        "title": "Review bank advice and record the bank response",
        "summary": "Independently review a retained multi-voucher advice version, then record the bank's actual acknowledgement or return before Treasury may release a check.",
        "permission": "vouchers.approve_bank_advice",
        "patterns": ["vouchers:advice_*", "vouchers:case_*"],
        "order": 53,
        "steps": (
            ("Open the retained advice version", "Compare the advice number, bank account, Finance Setup release, check list, case links, total, and snapshot checksum with the reviewed preparation schedule.", "One advice version contains only issued checks for one bank account and one pinned configuration release.", "The GRAND starter is editable working material; it is not automatically the locally accepted bank or COA form.", "Open Bank Advice", "vouchers:advice_workspace"),
            ("Check maker and reviewer separation", "Confirm that you did not prepare or submit the version. Review the cited authority, preparation note, and local-applicability note.", "A different authorized Accounting reviewer records the decision basis.", "Return vague, pending, or unverified authority notes instead of treating them as acceptance.", "", ""),
            ("Approve or return for correction", "Approve the retained snapshot or give a specific correction instruction. A returned version is never overwritten; the preparer creates a reasoned successor from its instruments.", "The decision, actor, time, reason, and prior version remain reconstructible.", "Corrections may remove an item but cannot import an unrelated check into that successor.", "", ""),
            ("Wait for actual bank submission", "Treasury records the submission and retained transmission reference only after sending the approved version to the bank.", "The record distinguishes internal approval from external submission.", "Do not acknowledge a merely approved version or infer delivery from a printed schedule.", "", ""),
            ("Record the bank response", "Use the bank's response and retained evidence to acknowledge the submitted version or return it with a reason.", "Only an acknowledged current advice can advance all ready cases to Treasury release.", "A bank return restores the affected checks to the advice queue and requires a reasoned successor; it does not erase the original version.", "", ""),
        ),
    },
    {
        "slug": "finance-returned-instrument-review",
        "version": 1,
        "title": "Review a returned released instrument",
        "summary": "Trace Treasury's bank-return evidence to the original advice and payment entry, decide the accounting treatment, and authorize replacement only after the governed posting decision is complete.",
        "permission": "vouchers.review_returned_instruments",
        "patterns": ["vouchers:advice_*", "accounting:entry_*", "accounting:workspace"],
        "order": 54,
        "steps": (
            ("Trace the original payment", "Open the returned-item review and compare the released check, acknowledged advice, claimant release, original payment posting request, bank-return evidence, and open Treasury exception.", "The same instrument and payment event are traceable from issue through bank return.", "Do not classify an unissued or unreleased check through this route.", "Open Bank Advice", "vouchers:advice_workspace"),
            ("Ask Treasury to clarify when needed", "Return the review with a specific evidence gap. Treasury must answer through a successor clarification version.", "Both the first submission and clarification remain retained.", "Do not replace Treasury's source evidence inside Accounting.", "", ""),
            ("Choose the governed outcome", "Select Reissue only when the evidence supports replacement; otherwise select Close without reissue. Record the reviewed authority and decision basis.", "The outcome is explicit and independently attributable.", "Classification alone does not authorize another check.", "", ""),
            ("Complete the accounting decision", "Post the generated returned-payment reversal when the active posting rule requires it, or retain the governed no-entry decision. The reversal restores bank/cash and the payable against the original release entry.", "The returned payment is reflected once in the ledger or explicitly documented as requiring no entry.", "Never edit or delete the original posted payment JEV.", "Open Accounting", "accounting:workspace"),
            ("Return control to Treasury", "After the posting request is posted or marked not required, GRAND returns the case to the exact Treasury stage. Replacement is enabled only for an approved Reissue outcome.", "A linked replacement closes the review and exception while preserving the original instrument.", "Do not manually bypass the open review or reuse the old check number.", "", ""),
        ),
    },
    {
        "slug": "finance-cash-position-review",
        "version": 1,
        "title": "Review Treasury cash policies and positions",
        "summary": "Independently review bank/fund cash rules and reconciled cash-position snapshots before they may govern check issue.",
        "permission": "vouchers.approve_cash_position",
        "patterns": ["vouchers:cash_*", "accounting:bank_reconciliation_*"],
        "order": 52,
        "steps": (
            ("Review the local rule before activation", "Compare the bank account, fund, Observe/Enforce choice, reserve, position-age limit, and unclaimed/stale thresholds with the named local authority, bank terms, and accepted Treasury procedure.", "The policy describes an applicable local control rather than copying a generic public rule.", "Keep a new route in Observe mode until named owners accept its operation and evidence.", "Open Cash Position", "vouchers:cash_workspace"),
            ("Confirm maker/checker separation", "Verify that you did not create or submit the policy or position you are deciding.", "A different authorized reviewer records the decision basis.", "Do not approve through the preparer's account.", "", ""),
            ("Trace the bank basis", "Open the pinned bank reconciliation and compare its bank, fund, period end, book balance, and checksum with the cash position.", "The position starts from independently reconciled book evidence.", "A budget balance, bank-screen screenshot, or unposted forecast cannot substitute for the reconciled cash basis.", "Open Bank Reconciliation", "accounting:bank_reconciliation_workspace"),
            ("Review confirmed later movements", "Check each summarized inflow, outflow, restricted amount, and evidence reference after the reconciliation date. Confirm that outstanding issued reservations are not entered again as outflows.", "The calculation is reproducible and does not double count issued instruments.", "Return unclear summaries for a successor version; never edit submitted evidence.", "", ""),
            ("Approve or return", "Record the reviewed policy/schedule references when approving, or a specific correction instruction when returning.", "Approval creates a checksum-backed source for Treasury; a return keeps the version and calls for a reasoned successor.", "Approval confirms the GRAND control, not an unverified official form layout.", "", ""),
        ),
    },
    {
        "slug": "finance-bank-reconciliation-prepare",
        "version": 5,
        "title": "Prepare a monthly bank reconciliation",
        "summary": "Stage the bank statement, carry unresolved approved timing items, match posted journals, and submit only a zero-difference adjusted-balance schedule.",
        "permission": "accounting.prepare_bank_reconciliation",
        "patterns": ["accounting:bank_reconciliation_*"],
        "order": 50,
        "steps": (
            ("Create the monthly control", "Choose one mapped bank account and fund, enter the statement period/receipt date, and copy the independently checked opening, closing, row, deposit, and withdrawal controls.", "A draft identifies one bank account, one fund, and one monthly statement.", "Use the bank-account code adopted in Finance Setup; do not enter a replacement COA account.", "Open Bank Reconciliation", "accounting:bank_reconciliation_workspace"),
            ("Stage the bank CSV", "Upload the UTF-8 starter CSV. GRAND checks each date, one-sided amount, optional running balance, declared totals, closing equation, and SHA-256 source checksum.", "The statement becomes Validated only when every source control agrees.", "Before submission you may restage a corrected source, but must explain the replacement; prior versions remain retained.", "Open Bank Reconciliation", "accounting:bank_reconciliation_workspace"),
            ("Carry unresolved prior timing items", "After validation, use Carry unresolved prior items. GRAND brings forward only the latest active item from an earlier independently reconciled statement for the same bank account and fund, preserving its original evidence, expected-clearance date, source statement, and checksum.", "The current schedule shows the item's age and flags a past expected-clearance date without retyping the old evidence.", "Investigate overdue items. Do not create a fresh item merely to reset its age or expected date.", "Open Bank Reconciliation", "accounting:bank_reconciliation_workspace"),
            ("Match only posted book evidence", "Run unique exact matching, then review remaining same-amount candidates manually against bank references, checks, transfers, and posted JEVs.", "Every bank row points to one posted bank-account journal line with the same amount and direction.", "A bank charge, credit memo, or book error with no posted line requires an authorized JEV or correction before the BRS can close.", "Open Accounting", "accounting:workspace"),
            ("Explain new ledger-only timing items", "For each new posted bank line absent from the statement, record the check/deposit evidence, reason, and expected clearance date.", "Deposits in transit and outstanding checks are explicit and feed the adjusted-balance calculation.", "Classification is not an adjustment and does not hide an unexplained difference.", "", ""),
            ("Correct before submission with a reason", "If a match, classification, control, or source file is wrong, use its guided correction action and record why. Removing a later bank match reopens every timing item it had cleared; rematching closes that same retained lineage again.", "GRAND retains the before/after history and never rewrites the reconciled prior statement.", "Do not edit database rows, erase the old month, or silently replace a match.", "", ""),
            ("Reach zero and submit", "Confirm adjusted bank balance equals the posted GL book balance, every statement row is matched, and every ledger-only line is classified; then submit to a different reviewer.", "The BRS is read-only under independent review with a checksum-backed snapshot.", "Do not force agreement with a balancing line or approve your own preparation.", "", ""),
            ("Export portable evidence", "After review, export the controlled CSV when needed. GRAND archives the same bytes and manifest inside the department/user/category TraceSync-ready folder tree.", "The statement, matches, timing items, control totals, and checksums remain portable.", "Use the locally accepted signed BRS template for official submission until its exact layout is confirmed and configured.", "", ""),
        ),
    },
    {
        "slug": "finance-bank-reconciliation-review",
        "version": 2,
        "title": "Review a bank reconciliation independently",
        "summary": "Review the statement, posted GL, reconciling items, and adjusted-balance result before closing the monthly control.",
        "permission": "accounting.approve_bank_reconciliation",
        "patterns": ["accounting:bank_reconciliation_*"],
        "order": 51,
        "steps": (
            ("Confirm independent assignment", "Verify that you did not create or submit this reconciliation and that the bank account, fund, period, and department are correct.", "The maker/checker separation is clear.", "Do not review through the preparer's account.", "Open Bank Reconciliation", "accounting:bank_reconciliation_workspace"),
            ("Compare statement and matches", "Review the checksummed current statement version and trace every bank row to its posted JEV, payment, remittance, deposit, debit memo, or credit memo evidence.", "No statement-only transaction remains unrecognized in the books.", "GRAND's exact checks do not replace review of the bank's source document.", "", ""),
            ("Review timing-item lineage and equation", "Check each outstanding check or deposit in transit against its evidence and expected clearance date. For a carried item, trace the linked prior reconciled statement and investigate its age or overdue warning. For a later clearance, confirm the bank row closes the retained prior-item lineage; then confirm adjusted bank and GL book balances are equal.", "The unexplained difference is exactly zero and old timing items are neither silently dropped nor recreated.", "Bank charges, credits, and book errors normally require a JEV, not timing-item classification.", "", ""),
            ("Approve or return", "Record the signed BRS, GL comparison, bank statement, and supporting-schedule reference when approving; otherwise return a specific correction instruction.", "Approval creates an immutable reconciliation checksum; return reopens the reasoned correction window.", "Official submission copies and deadlines remain subject to locally accepted COA/LGU practice.", "", ""),
        ),
    },
    {
        "slug": "finance-remittance-accounting",
        "version": 3,
        "title": "Review and post withholding remittances",
        "summary": "Independently review Treasury's exact schedule, then post the generated liability-reducing JEV after actual release.",
        "permission": "vouchers.approve_remittances",
        "patterns": ["vouchers:remittance_*", "accounting:workspace", "accounting:entry_*"],
        "order": 55,
        "steps": (
            ("Review the submitted schedule", "Open the remittance and compare its fund, agency, date, authority/evidence references, selected subsidiary balances, and total to the reviewed return or schedule.", "The batch agrees with its accepted local source and every selected liability is still available.", "A public COA or agency memo is guidance; record local applicability and the actual reviewed schedule.", "Open Remittances", "vouchers:remittance_workspace"),
            ("Approve or return independently", "Record a specific approval basis, or return the same batch with corrections Treasury can act on.", "An approved schedule becomes read-only; a return reopens the reasoned modification allowance.", "The preparer cannot approve the same batch.", "", ""),
            ("Create the released remittance JEV", "After Treasury records actual release, use Create remittance JEV in Accounting. GRAND resolves each pinned withholding account and the bank mapping from the checksummed rule.", "The draft debits the exact posted liabilities and credits the releasing bank for the control total.", "Do not create a manual duplicate or substitute a different liability account when a mapping changed.", "Open Accounting", "accounting:workspace"),
            ("Submit and post independently", "Submit the balanced generated draft and have a different authorized poster review and post it.", "The remittance becomes complete only after the ledger entry posts and the handoff reconciles.", "Discarding a pre-post draft creates a new controlled JEV request; it never repeats the actual remittance.", "", ""),
            ("Verify governed tax filing evidence", "When a released governed-tax batch carries submitted filing evidence, compare its form/period, actual channel, filing acknowledgement, payment proof, custody reference, and source. For the recommended GRAND source, verify the approved report run, official template version, reconciled control, and copied checksums. For the advanced external path, verify the stated exception basis, retained schedule, and SHA-256.", "A different Accounting reviewer verifies the exact checksum-backed evidence or returns specific correction instructions.", "Verification records the comparison; it does not file a return, calculate a deadline, or prove official acceptance without the referenced external acknowledgement.", "Open Remittances", "vouchers:remittance_workspace"),
            ("Correct after posting", "Use a linked reversal or adjustment with a reason. Keep the original batch, release evidence, and JEV intact.", "The liability schedule and general ledger remain reconstructible.", "Never edit or delete posted subsidiary detail.", "", ""),
        ),
    },
    {
        "slug": "finance-opening-prepare",
        "title": "Stage and correct opening balances",
        "summary": "Prepare controlled opening rows, resolve differences, and submit only after every declared control is exact.",
        "permission": "accounting.prepare_opening_balances",
        "patterns": ["accounting:opening_*"],
        "order": 20,
        "steps": (
            ("Create the control batch", "Open Opening Controls, choose the typed fiscal year and opening period, then record the reviewed source reference and independent row/debit/credit totals.", "A draft batch displays the declared controls before any rows are staged.", "Do not invent a balancing row or use an unapproved account code.", "Open Opening Controls", "accounting:opening_workspace"),
            ("Stage the reviewed CSV", "Upload the UTF-8 controlled source. GRAND records its SHA-256 checksum and maps each fund, account, and responsibility center.", "Every source row appears with a valid or needs-correction result.", "Replacing a draft source is allowed, but it creates new staging evidence.", "Open Opening Controls", "accounting:opening_workspace"),
            ("Correct with evidence", "Use Correct on the flagged row or Correct declared controls. Cite the reviewed schedule, instruction, or authority for the change.", "The row/control returns to draft and the before/after evidence is retained.", "Never edit a posted opening JEV; use the governed adjustment route.", "", ""),
            ("Validate to zero difference", "Run validation again and confirm row count, batch debit/credit, and every per-fund total agree exactly.", "The batch status becomes Validated with no row or control errors.", "A globally balanced file can still be invalid when one fund is out of balance.", "", ""),
            ("Submit for independent review", "Submit the validated batch. A different authorized approver must review the supporting schedule and controls.", "The batch moves to For review and becomes read-only to the preparer.", "", "", ""),
        ),
    },
    {
        "slug": "finance-opening-approve",
        "title": "Review opening controls independently",
        "summary": "Approve only a checksum-backed, zero-difference opening schedule, or return it with a useful correction basis.",
        "permission": "accounting.approve_opening_balances",
        "patterns": ["accounting:opening_*"],
        "order": 30,
        "steps": (
            ("Confirm segregation", "Verify that you are not the creator or submitter and that the selected fiscal year, period, and department are correct.", "The review is independent and within your current department.", "Do not share accounts or approve on another person's behalf.", "", ""),
            ("Compare source and controls", "Review the source reference/checksum, declared totals, mapped rows, validation errors, and per-fund balance against the accepted schedule.", "No unexplained row, debit, credit, or fund difference remains.", "GRAND validation does not replace review of the signed/local source evidence.", "", ""),
            ("Approve or return", "Record the supporting schedule/control evidence when approving. If anything is wrong, return the batch with a specific correction reason.", "Approval permits posting; return reopens governed preparation.", "An approved batch may be returned only before posting.", "", ""),
        ),
    },
    {
        "slug": "finance-opening-post",
        "title": "Post and reconcile opening JEVs",
        "summary": "Post independently approved per-fund opening entries, then close the readiness gate only after reconciliation reaches zero.",
        "permission": "accounting.post_opening_balances",
        "patterns": ["accounting:opening_*"],
        "order": 40,
        "steps": (
            ("Recheck posting readiness", "Confirm the year is approved or active, the opening period is open, and the batch remains independently approved.", "The Post opening JEVs action is available.", "The preparer cannot post the same batch.", "", ""),
            ("Post the generated entries", "Post once. GRAND creates one balanced, immutable opening JEV per fund with source and batch lineage.", "The batch becomes Posted; reconciliation pending.", "Do not retry by creating manual duplicate JEVs.", "", ""),
            ("Run the separate reconciliation", "Compare staged row/debit/credit controls to the generated posted JEV lineage using Reconcile posted controls.", "Every difference is zero and the batch becomes Reconciled.", "A failure remains recorded for investigation and does not satisfy fiscal readiness.", "", ""),
            ("Export review evidence", "Use Export controlled CSV when a reviewer needs portable data. GRAND also retains it in the configured export root with its checksum manifest.", "The browser copy and archive manifest carry the same SHA-256.", "The CSV is not automatically an official COA form.", "", ""),
        ),
    },
    {
        "slug": "finance-journal-prepare",
        "version": 3,
        "title": "Prepare and submit a journal entry",
        "summary": "Create manual JEVs only for supported events, or materialize a voucher JEV from its pinned posting rule, then send it to a different poster.",
        "permission": "accounting.prepare_journal_entries",
        "patterns": ["accounting:entry_*", "accounting:workspace"],
        "order": 60,
        "steps": (
            ("Choose the correct source route", "For a voucher handoff, review whether it is recognition, payment release, or another governed event, its recognition point, current event amount, and pinned posting-rule title, then use Create GRAND JEV. Use New journal only for a separately supported manual event.", "The selected route preserves the source, physical-instrument trigger, and policy lineage.", "Do not recreate a voucher or opening-balance JEV manually.", "Open Accounting", "accounting:workspace"),
            ("Create or inspect the draft", "For a manual event, choose the open period and fund and record its reference, date, and source. For a voucher event, let GRAND resolve the pinned account/amount instructions and verify the generated rule checksum.", "A department-scoped draft exists with its source evidence.", "A mapping error must be corrected in governed setup; do not substitute an unexplained account.", "", ""),
            ("Add controlled lines", "Add one positive debit or credit per line using active posting accounts and the correct responsibility center.", "The live totals are non-zero and equal.", "Do not use a manual journal to bypass a source-generated voucher or opening route.", "", ""),
            ("Replace a discarded event draft safely", "If a generated payment-event draft must be discarded before posting, record the reason. GRAND retains the voided draft and reserves a new controlled JEV number for a successor request.", "The voucher stays at Accounting payment-event posting and a new request appears without re-releasing the check.", "Do not issue a manual duplicate or repeat the physical release.", "", ""),
            ("Submit for posting", "Review the source evidence and totals, then submit. The draft becomes read-only while under independent review.", "A different poster receives the entry in the posting queue.", "", "", ""),
        ),
    },
    {
        "slug": "finance-journal-post",
        "version": 5,
        "title": "Review, post, or return a JEV",
        "summary": "Independently review source lineage and balanced lines before they enter the immutable ledger.",
        "permission": "accounting.post_journal_entries",
        "patterns": ["accounting:entry_*", "accounting:workspace"],
        "order": 70,
        "steps": (
            ("Review the submitted entry", "Confirm the period/fund, source reference, description, accounts, centers, line details, and equal debit/credit totals. For a voucher JEV, compare its event, recognition decision, pinned posting-rule checksum, claimant/payee, and deduction subsidiary labels to the handoff.", "The entry agrees with its supporting evidence and immutable posting rule.", "Posting is an authoritative boundary; do not approve an unexplained mapping, missing subsidiary identity, or a rule used at the wrong recognition point.", "Open Accounting", "accounting:workspace"),
            ("Return or post", "Return with a specific reason when review can be resolved on the same generated draft. Otherwise post once; a recognition JEV moves to check preparation, while a payment-event JEV resumes its exact recorded Treasury stage or completes the last release.", "The entry is either editable again by its preparer or immutable in the ledger, and the shared case resumes once.", "Do not manually move a voucher around its recorded resume stage.", "", ""),
            ("Correct after posting properly", "Use a linked reversing or adjusting entry with a mandatory reason rather than changing posted lines.", "The original and correction both remain traceable.", "", "", ""),
        ),
    },
    {
        "slug": "finance-dv-prepare",
        "version": 5,
        "title": "Prepare and route a disbursement voucher",
        "summary": "Continue the shared Budget–Accounting–Treasury case without re-encoding facts or bypassing wet-signature custody.",
        "permission": "vouchers.prepare_disbursement_voucher",
        "patterns": ["vouchers:*"],
        "order": 80,
        "steps": (
            ("Open your Accounting queue", "Select a case at Accounting preparation and review its claim-to-allocation control, relationship types, recognition/adjustment decision, Budget classification, claimant/payee, and documents.", "The shared case—not a copied transaction—is open with zero relationship difference.", "Current Voucher Workbench controls remain a controlled UAT slice until parent roadmap gates pass.", "Open Finance Queue", "vouchers:workspace"),
            ("Return before DV when relationships need correction", "If the claim, obligation allocation, or snapshot is wrong, return the same case to requesting-office payable preparation with a specific reason before creating a DV.", "The governed pre-DV modification window reopens without losing prior review history.", "After a DV exists, use the coordinated voucher/payment correction route instead.", "", ""),
            ("Prepare the DV and deductions", "Use governed setup values and add one deduction row at a time. For a governed tax, choose the locally confirmed rule, enter the taxable base, and let GRAND require the exact configured amount, payee identity, and TIN when the rule calls for it. Add another row for each different tax or ordinary deduction, then reconcile gross less total deductions to net.", "Each governed tax row pins its ATC, rate, forms, authority, payee, base, and checksums for later Accounting reporting; the DV is ready for its controlled print and signature route.", "Do not guess a rate or use a candidate rule. A starter or pilot workbook is not automatically a locally accepted official form.", "", ""),
            ("Correct before issue", "While no check or payment instrument has been issued and no JEV has posted, return the case through its guided correction action, record the reason, and prepare the corrected DV and deduction rows as the current version.", "The earlier preparation and route history remain traceable while the corrected current values are revalidated and reprinted as required.", "After a JEV posts or a check/payment instrument is issued, do not edit the voucher or tax evidence in place; use the governed adjustment/reversal and, when applicable, cancellation and replacement route.", "", ""),
            ("Prepare one signing file", "At the controlled signing-copy card, choose Prepare print-ready file. Download only the current version and compare its visible layout, paper size, names, totals, and signature labels before printing.", "GRAND pins the output checksum and automatically retains the same bytes and manifest in the TraceSync-ready export folder.", "Do not alter the generated signing file. Correct the governed source/template and create a reasoned replacement instead.", "", ""),
            ("Record what was actually printed", "Enter the number of copies and the printer, paper stock, tray, duplex, or margin setting actually used. Add a short alignment or quality note when useful.", "The current print version carries immutable operator, time, copy, and printer evidence.", "Do not claim that a file was printed until the physical copies were checked.", "", ""),
            ("Assemble the physical packet", "Count the documents and pages, describe the assembly, and create the linked TracePoint packet. GRAND builds the configured office/signatory checkpoints without copying voucher amounts into TracePoint.", "The exact signing version is linked to one custody item and its receiving route.", "The TracePoint record proves custody events; it does not replace the paper signatures or Finance record.", "", ""),
            ("Replace bad copies safely", "If the current copies are damaged, misaligned, or wrong, enter a specific replacement reason. Mark every earlier physical copy DO NOT SIGN, prepare the successor version, then repeat print recording and packet assembly.", "The earlier output and signing round are superseded while their evidence remains visible.", "Never reuse or silently discard a superseded signing copy.", "", ""),
            ("Record each returned signature", "After the linked packet returns, select the signer task and record the actual returned wet signature with a useful note. Repeat only for the current print version and signature round.", "When all current tasks are returned, the packet is marked returned and the case advances to Accounting validation.", "Do not record a digital approval or a signature expected later as if the paper were already returned.", "", ""),
        ),
    },
    {
        "slug": "finance-subsidiary-reconcile",
        "version": 1,
        "title": "Reconcile payable and withholding controls",
        "summary": "Explain mapped GL control balances through claimant/payee and deduction detail, record exceptions, and export portable evidence.",
        "permission": "accounting.reconcile_control_accounts",
        "patterns": ["accounting:subsidiary_*", "accounting:entry_*"],
        "order": 75,
        "steps": (
            ("Choose the cut-off", "Open Subsidiary controls and select the review date. GRAND includes only posted entries through that date.", "Payable, withholding, and GL control balances use one cut-off.", "Do not compare a current subsidiary list to a GL report from another date.", "Open Subsidiary Controls", "accounting:subsidiary_controls"),
            ("Review each mapped control", "Compare each fund and control account's GL credit balance with its claimant/payee or deduction subsidiary balance.", "Every configured control is explained by the same posted journal lines.", "A zero total is not accepted as configured reconciliation when no payable or deduction mappings exist.", "", ""),
            ("Investigate differences", "Open the journal evidence and identify manual, opening, adjustment, or incorrectly mapped control-account lines that lack matching subsidiary identity. Correct posted errors only by a governed reversal or adjustment.", "Each difference has a traceable cause and correction route.", "Never add a balancing subsidiary row or rewrite a posted journal merely to reach zero.", "", ""),
            ("Record the result", "When the comparison is ready, use Record immutable reconciliation. GRAND preserves the result rows, preparer, cut-off, and SHA-256 checksum whether balanced or exceptional.", "A dated reconciliation run remains available for later review.", "Recording an exception is evidence of review, not proof that the exception is resolved.", "", ""),
            ("Export portable evidence", "Export the payable schedule, withholding schedule, and recorded reconciliation when authorized. Copy or synchronize the entire GRAND export root so each file stays beside its manifest.", "The same browser bytes are retained in the department/user/file TraceSync-ready tree.", "Controlled CSVs are not automatically official COA or locally accepted schedules; retain the accepted signed form where required.", "", ""),
        ),
    },
    {
        "slug": "finance-voucher-validate",
        "version": 1,
        "title": "Validate the DV and request its governed JEV",
        "summary": "Apply the payable recognition decision at the correct configured event, pin the reviewed rule, and hand one immutable request to journal preparation.",
        "permission": "vouchers.validate_accounting_voucher",
        "patterns": ["vouchers:*", "accounting:workspace"],
        "order": 85,
        "steps": (
            ("Recheck the current signing packet", "Confirm the latest controlled signing copy and TracePoint packet returned with all required wet signatures before validation.", "Only the current non-superseded print version is eligible.", "Do not validate against an older or replaced signing copy.", "Open Finance Queue", "vouchers:workspace"),
            ("Read the recognition decision", "Review the payment-ready intake's recognition decision and basis. Confirm the pinned transaction variant has the matching event and recognition point.", "The accounting event is explicit before any JEV is generated.", "An earlier accrual or existing payable must be linked; never collapse it into a second DV recognition.", "", ""),
            ("Validate and pin the rule", "Enter the controlled JEV number/date and validation note. GRAND snapshots the rule, ordered debit/credit instructions, authority, and checksum with the voucher facts.", "One immutable pending handoff appears in Accounting.", "If the rule belongs to an earlier or later point, stop and correct the process rather than forcing it here.", "", ""),
            ("Resolve a returned draft", "If mapping or source evidence is wrong, discard the unposted generated JEV, return the same voucher for correction, and create a new versioned handoff after revalidation.", "The failed or cancelled request remains visible and no duplicate posts.", "After posting, use a reversing or adjusting JEV; never rewrite the original.", "", ""),
        ),
    },
    {
        "slug": "finance-configure",
        "version": 4,
        "title": "Prepare governed Finance setup",
        "summary": "Version master data, rules, signatories, numbering, and templates before transaction users depend on them.",
        "permission": "finance.manage_finance_configuration",
        "patterns": ["finance:*", "accounting:setup*"],
        "order": 10,
        "steps": (
            ("Work in a draft release", "Create or open the correct department and fiscal-year configuration release before changing controlled setup.", "Changes are isolated from active transaction policy.", "", "Open Finance Setup", "finance:workspace"),
            ("Define transaction variants and evidence", "Add each locally enabled transaction variant, then add its ordered required or conditional documentary rules. State the exact applicability condition and whether reviewed authority permits a waiver.", "Every enabled payable route has a typed, reviewable checklist before release activation.", "Do not infer local applicability or form acceptance from a public COA/DBM source alone.", "", ""),
            ("Describe each accounting event", "For recognition, liquidation, payment, remittance, or another enabled event, choose its exact recognition point and add ordered debit/credit instructions. Start from the editable recognition recipe when useful, then replace its warning with the locally reviewed authority and wording.", "Each transaction variant has a human-readable rule that produces a balanced JEV.", "A generated starter is not accepted policy and blocks submission until its authority note is replaced.", "", ""),
            ("Configure each tax rule plainly", "Use Add tax rule and enter the tax family, ATC, percentage, taxable-base description, return or certificate form codes, reporting-date basis, rounding method, TIN requirement, authority, and local acceptance evidence. Keep a researched starter as Candidate until the Municipal Accountant or named local owner confirms its actual scope and effectivity.", "Transaction users see a readable locally confirmed rule instead of editing JSON, and every governed voucher line can pin the exact version used.", "Do not copy a BIR rate, form code, threshold, or deadline into active policy merely because it appears in a public source; confirm the current taxpayer, transaction, and LGU applicability first.", "", ""),
            ("Record authority and effectivity", "For each code/rule, enter the authority reference, effective dates, version, and locally confirmed scope.", "The release explains which authority and period it implements.", "An official source still requires applicability confirmation.", "", ""),
            ("Resolve readiness blockers", "Complete required funds/accounts, signatories, numbering, evidence rules, posting rules, and accepted templates, then submit for independent approval.", "Readiness has no blocking items and an approver can review the release.", "A posting rule must contain both debit and credit instructions.", "", ""),
        ),
    },
)

REQUESTING_GUIDES = (
    {
        "slug": "finance-requesting-office-obligation",
        "title": "Prepare and submit an obligation request",
        "summary": "Initiate the locally applicable ALOBS/ORS/OBR without retyping authority, and correct it only inside the governed modification window.",
        "permission": "budget.initiate_obligation_requests",
        "patterns": ["budget:obligation_*"],
        "order": 1,
        "steps": (
            ("Open your obligation queue", "Open Obligation control and confirm you are working under your current assigned department, not a previous employee's tutorial or transaction history.", "Only this department's requests and your private guide checkmarks are shown.", "Tutorial progress is only your private step checklist; it is not approval, work status, performance evidence, or inherited history.", "Open Obligation Control", "budget:obligation_workspace"),
            ("Start the request once", "Choose the exact operational appropriation, locally applicable ALOBS/ORS/OBR type, unique office request reference, date, claimant/payee, particulars, evidence reference, and signed effect total.", "One traceable draft identifies the intended authority and claim.", "Do not duplicate a prior request reference or treat an approved proposal as spendable authority.", "New Obligation Request", "budget:obligation_create"),
            ("Add the exact schedule", "Select authorized lines instead of retyping fund, office, PPA, funding source, account, and expense class. Enter positive amounts; the movement supplies the sign.", "The schedule retains appropriation and allotment lineage.", "The signed control total is positive for new obligations and negative for returns/reductions.", "", ""),
            ("Use guided draft corrections", "Before submission, or after a Budget return, use Correct/Remove and the header edit. Review the zero control difference and the specific return reason.", "Every permitted change carries retained audit evidence.", "Submitted or certified rows cannot be silently edited or deleted.", "", ""),
            ("Submit to Budget", "Submit only when the exact schedule and signed effect agree. Budget will recheck unobligated allotment under a database lock and either certify or return a specific correction.", "The request enters Budget's certification queue without consuming balance early.", "Do not create a replacement draft merely because Budget returned the same request.", "", ""),
            ("Correct certified history safely", "If a certified obligation must change before any DV/check issuance, create a linked adjustment, return, or cancellation. After issuance, follow the coordinated voucher/payment reversal route.", "Original and successor movements remain reconstructible.", "Never overwrite a certified obligation or bypass a later issued artifact.", "", ""),
        ),
    },
    {
        "slug": "finance-payable-readiness-review",
        "version": 2,
        "title": "Review payable documentary readiness",
        "summary": "Independently accept a transaction-specific payable checklist or return the same case with a precise correction basis.",
        "permission": "vouchers.review_payable_intake",
        "patterns": ["vouchers:*"],
        "order": 75,
        "steps": (
            ("Open the Accounting review queue", "Select a case at Accounting payable-readiness review. Confirm that the current requesting office—not Accounting—submitted the intake.", "The shared case shows the pinned certified obligation, claim, transaction variant, and documentary checklist.", "Do not review a case prepared or submitted by you, and do not accept work assigned to another Accounting office.", "Open Finance Queue", "vouchers:workspace"),
            ("Reconcile every obligation relationship", "Review each obligation UUID, full/partial/progress/final relationship, allocation version, current capacity, and lineage checksum. Confirm the allocation total equals the claim control exactly.", "One-to-many and many-to-one relationships are explicit and the control difference is zero.", "If a pre-DV obligation correction changed an amount or checksum, return for relationship reconciliation instead of continuing.", "Open Obligation Control", "budget:obligation_workspace"),
            ("Review every configured rule", "For each pinned rule, inspect the authority/applicability basis and the referenced source evidence. Confirm required items are present, conditional items have a specific not-applicable decision, and any waiver is explicitly allowed.", "Every checklist result is supported without copying sensitive source documents into GRAND.", "A public COA/DBM source is evidence for review; it is not automatic proof of local applicability or template acceptance.", "", ""),
            ("Record recognition and adjustment decisions", "Choose the reviewed recognition route and whether a governed obligation adjustment is reflected, unnecessary, or a partial/progress balance is intentionally retained. Record a specific basis for both decisions.", "Accounting's routing decisions are pinned for the later F7 posting rule and transaction export.", "This decision does not itself post a JEV or prove that a public COA/DBM source is locally accepted.", "", ""),
            ("Accept or return the same case", "Accept only when the relationships, claim, duplicate review, checklist, and recognition/adjustment decisions are payment-ready. Otherwise return with a correction reason the requesting office can act on.", "Acceptance routes the same case to DV preparation; return reopens its requesting-office checklist with full history retained.", "Do not create a replacement case merely to correct the intake.", "", ""),
        ),
    },
    {
        "slug": "finance-requesting-office-payable-intake",
        "version": 3,
        "title": "Open a payable from a certified obligation",
        "summary": "Carry one certified obligation into Accounting without recreating its Budget authority or hiding document gaps.",
        "permission": "vouchers.initiate_payable_case",
        "patterns": ["vouchers:*"],
        "order": 2,
        "steps": (
            ("Select available obligation capacity", "Open the Finance Queue and select a certified original obligation belonging to your current department with remaining claim capacity.", "The payable pins the controlled number, UUID, checksum, current corrected amount, and first allocation.", "Do not create a second Budget ledger or select another department's obligation.", "Open Finance Queue", "vouchers:workspace"),
            ("Choose the governed transaction variant", "Choose the governed payee and the exact locally approved transaction variant, then record the claim and source-record references that apply.", "The case pins the active variant and its authority-backed documentary rules without duplicating the authoritative procurement or records system.", "A public COA/DBM source or a generic transaction label is not automatic proof of local applicability.", "New Payable", "vouchers:case_create"),
            ("Build the exact relationship", "Choose full, partial, progress, or final for the first allocation. When several obligations support one claim, set the claim control and add the remaining obligations on the case. Separate cases may consume remaining capacity from the same obligation.", "Every valid one-to-one, one-to-many, or many-to-one relationship is explicit and capacity-protected.", "A final/full allocation must consume exact remaining capacity; use partial/progress only under locally accepted evidence.", "", ""),
            ("Reconcile the control total", "Confirm active allocations equal the payable claim control exactly. A lower final claim requires a governed pre-DV Budget adjustment before a final allocation.", "The control difference is zero with no over-allocation.", "Do not force the claim to fit, hide a balance, or overwrite a certified obligation.", "Open Obligation Control", "budget:obligation_workspace"),
            ("Use guided pre-DV modifications", "While the case is in payable preparation, revise the claim control, add an obligation, or create a versioned allocation revision/removal with a reason. If Accounting already accepted it, ask Accounting to return the same case before DV creation.", "Every before/after amount and reason remains traceable.", "After a DV or check exists, use the later coordinated reversal/cancellation route.", "", ""),
            ("Resolve the pinned checklist", "Open the new case and record each documentary rule as present, condition not applicable, or expressly waived where the reviewed rule permits it. Reference the source record and explain every not-applicable or waiver decision.", "No documentary rule remains pending, every required item is present or validly waived, and conditional decisions are explicit.", "Do not paste sensitive source content, mark a required item not applicable, or invent a waiver that Finance Setup does not allow.", "", ""),
            ("Review duplicate warnings", "Investigate similar payee/invoice or claim references and record a human review note when needed.", "The warning is resolved by an authorized person rather than treated as an automatic accusation.", "A warning is not proof of duplicate payment.", "", ""),
            ("Submit and correct the same case", "Send the completed checklist to Accounting. If it is returned, read the recorded reason, correct the evidence decisions, and resubmit the same case.", "Accounting receives an independently reviewable intake; a return preserves prior review evidence while reopening your checklist.", "Tutorial checkmarks are only your private learning aid; they do not submit, approve, or prove completion of this payable.", "", ""),
            ("Recover or refresh a handoff", "If the case reports a failed link or a governed Budget correction changed an allocation snapshot, use Reconcile obligation link while the case is back in payable preparation.", "Both databases agree on every active case/obligation UUID, amount, and checksum.", "Do not advance a pending, failed, stale, or non-zero-difference relationship.", "", ""),
            ("Export the transaction safely", "Use Export transaction when authorized. GRAND downloads the same CSV bytes retained under department/user/category/year/month with a sibling checksum manifest.", "The complete relationship, decisions, and documentary references can be copied through the single TraceSync-ready root.", "The export is controlled interchange, not automatically an official COA/DBM/local form.", "", ""),
        ),
    },
)


BUDGET_GUIDES = (
    {
        "slug": "finance-accountability-reporting-budget",
        "version": 5,
        "title": "Prepare the quarterly Budget accountability schedule",
        "summary": "Generate cumulative Budget accountability and Budget-versus-posted-actual controls while keeping working starters distinct from locally accepted official forms.",
        "permission": "reporting.view_reporting_workspace",
        "patterns": ["reporting:*", "budget:authorization_*", "budget:allotment_*", "budget:obligation_*"],
        "order": 60,
        "steps": (
            ("Open the quarterly starter", "Open Reports and choose Quarterly Budget Accountability Schedule. Select the quarter start and end covered by the review.", "The report calculates cumulative authority and posted movements through the selected period end.", "The native starter is LBAc Form No. 2-equivalent working material; it is not automatically the current locally accepted DBM/COA form.", "Open Reports", "reporting:workspace"),
            ("Confirm authority and local use", "Read the DBM recommendation basis and Local confirmation pending badge. Ask the named Budget owner to confirm the actual form, deadlines, signatories, copies, recipients, and retained signed comparison.", "The definition becomes Locally confirmed only with a specific authority and acceptance note.", "Do not infer current local applicability from a generic circular or manual alone.", "", ""),
            ("Generate and read the equation", "Generate the run and review appropriation, released allotment, reserve/deferral, executable allotment, obligation, unreleased appropriation, and unobligated allotment.", "No cumulative balance is negative or exceeds its controlling authority.", "A control exception blocks review; correct the authoritative Budget transaction through its governed successor route.", "Open Budget Accountability", "budget:obligation_workspace"),
            ("Compare posted actuals carefully", "Choose Budget versus Posted Actual for the same fiscal year and period end. Review only exact fiscal-year, fund, responsibility-center, and account matches and investigate every unmatched or ambiguous Accounting expense key.", "Posted actuals are never silently spread across several PPAs or Budget lines.", "Resolve the classification bridge with Budget and Accounting evidence; do not allocate an amount merely to clear the exception.", "Open Reports", "reporting:workspace"),
            ("Drill through movements", "Open the appropriation, allotment order, or certified obligation from Source drill-through and compare the retained numbers, dates, checksums, classifications, and evidence references.", "Each total traces to immutable posted Budget movements.", "Do not create a balancing movement merely to force a report total.", "", ""),
            ("Compare and promote the editable layout", "Create a new template version when the LGU supplies its blank XLSX/PDF. Map and preflight it, obtain a different user's preview approval, then prepare a promotion using the accepted prior output for the same period and format.", "The promotion record shows automatic data/control agreement, changed layout fields, schedule impact, independent approval, activation, and recoverable rollback without a code deployment.", "Never overwrite an approved version, accept unresolved golden differences, or confuse a blank public form with local approval.", "", ""),
            ("Record local form acceptance", "Open Local form acceptance and choose Use DBM starter when the office is comparing one of the 31 listed LBP/LBA/LBR/LBE/LBAc forms. Create only the matching editable candidate, compare each field/source/control/owner/print section with the current blank/redacted local form, record a retained local reference for every matched or not-applicable decision, then confirm the source, delivery, people, copies, deadlines, custody, and layout. Link only the activated report template and retain independently witnessed tests.", "The accepted form version pins the exact template, reference, locally resolved sections, practical results, people, and SHA-256 evidence while prior versions remain traceable.", "A DBM candidate, technically balanced Budget report, or public blank form does not establish local acceptance. Unconfirmed rows block submission; repeat testing through a successor whenever the accepted form changes.", "Open Local form acceptance", "reporting:local_form_workspace"),
            ("Review, export, and safeguard", "Have a different authorized user review the controls. Export the output, source evidence, and reproduction receipt, then copy or synchronize the complete GRAND export root.", "The report and its TraceSync manifests remain portable and explainable.", "Pending local applicability or pilot fidelity remains unavailable for official approval.", "", ""),
        ),
    },
    {
        "slug": "finance-obligation-certification",
        "title": "Certify obligations and reconcile RAAO balances",
        "summary": "Independently certify requesting-office ALOBS/ORS/OBR schedules only inside executable allotment and preserve their registry lineage.",
        "permission": "budget.certify_obligations",
        "patterns": ["budget:obligation_*"],
        "order": 2,
        "steps": (
            ("Review the Budget queue", "Open Obligation control and select a request awaiting certification. Confirm the requesting office, form type, request reference, claimant/payee, particulars, date, and evidence reference.", "The reviewer is looking at the same submitted request, not a copied voucher record.", "The requesting-office submitter cannot certify the same request.", "Open Obligation Control", "budget:obligation_workspace"),
            ("Trace authority and allotment", "Follow each schedule row to its immutable appropriation and posted allotment. Review released, held, executable, already obligated, and unobligated amounts.", "Every proposed effect has sufficient executable allotment.", "Draft or unposted allotment does not support certification.", "", ""),
            ("Reconcile signed effects", "Confirm positive obligation and negative reduction effects sum exactly to the signed control total, with zero difference and the applicable period open.", "The request reproduces the reviewed schedule total exactly.", "Do not use a balancing row to conceal an unexplained difference.", "", ""),
            ("Certify or return", "Assign the controlled ALOBS/ORS/OBR number, record the independent review basis, and certify; otherwise return a specific guided correction reason.", "Certification creates one checksum-backed immutable movement per line exactly once.", "Concurrent certification rechecks the line balances under database locks.", "", ""),
            ("Use successor corrections", "For a certified error before DV/check issuance, require a linked adjustment, return, or cancellation with its own signed effect. After issuance, route the correction across the later voucher/payment controls.", "The registry never rewrites prior certified facts.", "Do not certify an obligation-only correction after its downstream issuance boundary.", "", ""),
            ("Export and reconcile", "Review PPA/account/office drilldowns and export the certified RAAO-equivalent registry when authorized. Preserve the entire TraceSync-ready export tree and sibling manifests.", "The same bytes and SHA-256 evidence are available for download and portable safekeeping.", "The exact official template remains acceptance-gated until locally confirmed.", "Export Registry", "budget:obligation_registry_export"),
        ),
    },
    {
        "slug": "finance-allotment-release-control",
        "title": "Prepare and post allotment releases",
        "summary": "Release or adjust allotment only against immutable authorized appropriation lines, with exact totals and correction lineage.",
        "permission": "budget.view_allotment_control",
        "patterns": ["budget:allotment_*"],
        "order": 3,
        "steps": (
            ("Choose operational authority", "Open Allotment control and choose the exact authorized annual, supplemental, or reenacted appropriation. Review authorized, released, held, unreleased, and executable totals.", "The order is tied to one immutable appropriation schedule and fiscal year.", "An approved proposal is not enough; only operationally authorized appropriation is eligible.", "Open Allotment Control", "budget:allotment_workspace"),
            ("Prepare the order header", "Record the ARO/equivalent number and type, release and effectivity dates, accepted authority/evidence references, purpose, and signed control total.", "A draft order identifies its source authority and signed schedule.", "GRAND labels its export as controlled interchange until the exact locally accepted DBM/COA template is confirmed.", "New Release Order", "budget:allotment_create"),
            ("Add authorized schedule lines", "Select only lines from the linked appropriation and use the movement allowed for the order: release, reserve/deferral, adjustment, return, or cancellation.", "Every amount retains fund, office, PPA, account, expense-class, and appropriation lineage.", "Do not retype classification codes or use negative amounts; the movement type supplies direction.", "", ""),
            ("Reconcile and submit", "Make the computed line total equal the signed control total exactly, then submit. GRAND rechecks cumulative released and held balances under a lock.", "No line exceeds appropriation, falls below zero, or holds more than released allotment.", "A draft or returned order may be edited; a submitted order is read-only.", "", ""),
            ("Post independently", "A different authorized officer reviews the signed schedule, evidence, effectivity, and zero control difference before posting.", "Immutable allotment movements and a checksum update the authority balances once.", "The preparer cannot post the same order.", "", ""),
            ("Correct without overwriting", "For a posted error or later action, create a linked adjustment, return, or cancellation order and explain the authority. Export the posted schedule when needed.", "The original and every successor remain reconstructible in the ledger and TraceSync-ready export archive.", "Never edit or delete a posted order or movement.", "", ""),
        ),
    },
    {
        "slug": "finance-appropriation-authorization",
        "title": "Authorize operational appropriations",
        "summary": "Turn only the exact approved final, supplemental, or reenacted version into operational authority after ordinance, review, effectivity, and control totals agree.",
        "permission": "budget.authorize_appropriations",
        "patterns": ["budget:authorization_*", "budget:version_detail"],
        "order": 5,
        "steps": (
            ("Verify the exact approved version", "Open the linked final, supplemental, or reenacted version and compare its classified lines, targets, source lineage, and total to the accepted signed schedule.", "The evidence record points to the exact independently approved version.", "A department, executive, or Sanggunian proposal is not yet operational authority.", "Open Annual Budget", "budget:workspace"),
            ("Check authority and review", "Verify the ordinance or applicable authority number/date, effectivity, review reference/date/result, and every condition against accepted evidence.", "The review is favorable or favorable with fully recorded conditions.", "Do not authorize a pending or adverse review result.", "", ""),
            ("Reconcile the signed control total", "Confirm the signed appropriation schedule total equals GRAND's exact version total with zero difference.", "The control difference is exactly zero.", "Never insert a balancing line merely to force agreement.", "", ""),
            ("Authorize independently", "Record the authorization basis. GRAND snapshots every classified line, computes a checksum, and marks the version spendable only after this action.", "An immutable operational appropriation schedule and checksum are created.", "The evidence preparer cannot authorize the same record.", "", ""),
            ("Correct through a successor", "After authorization, preserve the original. Use the applicable supplemental, reenacted, or other formally approved successor version and repeat the evidence gate.", "Original and successor authority remain reconstructible.", "Never silently edit an authorized schedule.", "", ""),
        ),
    },
    {
        "slug": "finance-annual-budget-preparation",
        "title": "Prepare the annual budget call and proposals",
        "summary": "Set reviewed department ceilings, prepare classified proposal versions, and keep proposals visibly separate from spendable authority.",
        "permission": "budget.view_budget_workspace",
        "patterns": ["budget:*"],
        "order": 10,
        "steps": (
            ("Prepare the annual call", "Create the fiscal-year call with its reviewed authority, instructions, proposal window, and department/fund/expense-class ceilings.", "A draft call contains the complete ceiling controls needed for review.", "A ceiling is neither an appropriation nor an allotment release.", "Open Annual Budget", "budget:workspace"),
            ("Submit for independent publication", "Submit the call to a different authorized reviewer. The reviewer publishes it or returns a specific correction reason.", "A published call becomes the controlled basis for proposal intake.", "Published calls and ceilings are immutable; issue a successor when formally required.", "", ""),
            ("Build an explicit proposal version", "Choose the requesting office and add lines using governed fund, office, PPA, funding source, account, expense class, appropriation type, target, and amount.", "The proposal total and per-ceiling remaining amount are visible.", "Do not recreate classification codes as free text.", "New Proposal Version", "budget:version_create"),
            ("Review without overwriting", "Use comments, comparison, return reasons, and successor versions. Submit only when every classified total is inside its published ceiling.", "The independent reviewer can approve or return the exact version reviewed.", "Approved proposals are still not spendable until F3.2 authority evidence is recorded.", "", ""),
            ("Export portable review data", "Export the classified CSV when review or safekeeping requires it. GRAND archives the same bytes and checksum manifest under the TraceSync-ready export root.", "The download identifies its version, status, and non-official-form boundary.", "Copy or synchronize the entire export root, not isolated files without manifests.", "", ""),
        ),
    },
    {
        "slug": "finance-budget-voucher",
        "title": "Initiate and certify a Budget voucher case",
        "summary": "Start one shared case and certify only an authorized, available obligation allocation.",
        "permission": "vouchers.initiate_budget_case",
        "patterns": ["vouchers:*"],
        "order": 20,
        "steps": (
            ("Open the Budget queue", "Create or select the requesting office's case and identify the claimant/payee, particulars, transaction type, and governed classification.", "One stable case begins the cross-office route.", "Do not recreate an existing case for the same claim.", "Open Finance Queue", "vouchers:workspace"),
            ("Check authoritative obligation", "Confirm the locally required documents and review the separate F4.2 certified obligation and authority lineage that this pilot case must reference during F5 integration.", "The case is supported by a traceable certified obligation.", "The current Voucher Workbench OBR remains a shadow compatibility record until the obligation UUID link is implemented and accepted.", "Open Obligation Control", "budget:obligation_workspace"),
            ("Complete or return the shadow step", "For current UAT only, complete the supported pilot allocation once, or return the case with a correction reason that the requesting office can act on.", "The shared shadow case advances to Accounting or reopens visibly for correction.", "Do not treat the pilot allocation as a second authoritative budget balance ledger.", "", ""),
        ),
    },
)

TREASURY_GUIDES = (
    {
        "slug": "finance-accountability-reporting-treasury",
        "version": 4,
        "title": "Prepare the payment instrument and disbursement register",
        "summary": "Report issued, advised, released, returned, cancelled, and replacement instruments with complete voucher and custody evidence.",
        "permission": "reporting.view_reporting_workspace",
        "patterns": ["reporting:*", "vouchers:case_*", "vouchers:advice_*"],
        "order": 60,
        "steps": (
            ("Open the controlled starter", "Open Reports and choose Payment Instrument and Disbursement Register. Select the activity period and the approved native or mapped template version.", "The run pins one reproducible view of instrument activity during the period.", "The editable starter is not automatically the locally accepted COA/Treasury register.", "Open Reports", "reporting:workspace"),
            ("Check local applicability", "Confirm the instrument scope, status treatment, signatories, copies, recipients, deadlines, and the retained local acceptance evidence before requesting official approval.", "The report remains visibly pending until a named owner records the accepted requirement.", "Do not infer local acceptance from a public manual or another LGU's template.", "", ""),
            ("Witness the actual Treasury form", "Use Local form acceptance to link the activated register or Finance workbook and retain the blank/redacted reference. For an applicable LBP/LBA/LBR/LBE/LBAc form, an authorized preparer may begin with Use DBM starter, but must compare and locally resolve every candidate section before recording the actual signatory, copy, recipient, custody, deadline, paper, printer, overflow, and continuation rules. Perform or independently witness the applicable practical tests.", "Only a different reviewer can accept the exact checksummed form after every starter row is resolved and every current test passes; earlier failed attempts remain visible.", "A DBM starter is not automatically the Treasury's accepted form. Do not mark printer/form-stock testing not applicable when Treasury prints, signs, releases, or files paper; accepted changes use a successor and a fresh test cycle.", "Open Local form acceptance", "reporting:local_form_workspace"),
            ("Review control evidence", "Confirm every included instrument has complete issue identity and the applicable advice, release/claimant receipt, cancellation reason, or replacement lineage.", "The control status is reconciled with no missing retained evidence.", "Correct the source transaction through its governed route and generate a successor; never edit report evidence.", "Open Finance Queue", "vouchers:workspace"),
            ("Drill through exceptions", "Open each source case to compare the DV, check identity, current advice, bank response, claimant receipt, return/cancellation, and replacement history.", "Every reported status and amount is explainable from the shared voucher case.", "Do not use the register to bypass an open returned-instrument or Accounting posting decision.", "", ""),
            ("Review, export, and safeguard", "Have a different authorized user review the report. Download the output, control/source CSV, and reproduction receipt, then synchronize the complete GRAND export root.", "The same evidence and manifests can be copied safely without manual re-filing.", "Pilot fidelity or pending local applicability remains unavailable for official approval.", "", ""),
        ),
    },
    {
        "slug": "finance-bank-advice-submit-release",
        "version": 1,
        "title": "Submit bank advice and release acknowledged checks",
        "summary": "Send only an independently approved advice version, retain the bank transmission and response, and keep release blocked until acknowledgement.",
        "permission": "vouchers.submit_bank_advice",
        "patterns": ["vouchers:advice_*", "vouchers:case_*"],
        "order": 6,
        "steps": (
            ("Open the approved version", "Compare the advice number, bank account, check list, total, checksum, approval basis, and retained authority with the schedule you will transmit.", "Treasury submits the exact independently reviewed version.", "Do not submit a draft, returned version, or an edited copy outside its retained snapshot.", "Open Bank Advice", "vouchers:advice_workspace"),
            ("Record actual bank submission", "After transmitting the advice, enter the bank submission reference and where the transmission evidence is retained.", "GRAND distinguishes approval from the actual external handoff.", "A printed or downloaded schedule alone is not proof that the bank received it.", "", ""),
            ("Wait for acknowledgement", "Accounting records the bank's acknowledgement or documented return against the submitted version.", "Affected cases remain in the bank-advice queue until every active check has an acknowledged current version.", "Do not release a check because its advice was only approved or submitted.", "", ""),
            ("Correct a bank-returned version", "If the bank returns the advice, ask Accounting to prepare a reasoned successor from the same retained instruments and corrected evidence.", "The prior version remains visible and the checks return to Issued for re-advice.", "The successor may omit an affected item but cannot silently add an unrelated check.", "", ""),
            ("Release the acknowledged check", "At Treasury release, verify the exact instrument, claimant, receipt reference, and the acknowledged current advice before recording handover.", "The original issue, advice, acknowledgement, claimant receipt, and payment posting form one traceable chain.", "Never alter check particulars after issue; use cancellation/replacement or the returned-instrument route.", "Open Finance Queue", "vouchers:workspace"),
            ("Escalate a returned released check", "When the bank returns an already released check, record the policy-based exception and bank evidence. Wait for Accounting's reversal or no-entry decision before replacement.", "The replacement allowance opens only after Accounting completes the governed decision and selects Reissue.", "Do not resolve the exception manually while the Accounting review is open.", "Open Cash Position", "vouchers:cash_workspace"),
        ),
    },
    {
        "slug": "finance-treasury-cash-position",
        "version": 1,
        "title": "Maintain cash position and instrument ageing",
        "summary": "Prepare locally governed bank/fund cash controls, reserve approved cash at issue, and resolve unclaimed, stale, or returned instruments with retained evidence.",
        "permission": "vouchers.prepare_cash_position",
        "patterns": ["vouchers:cash_*", "vouchers:case_*"],
        "order": 5,
        "steps": (
            ("Start with the plain-language starter", "Download the Planning starter to discuss bank/fund routes, reserves, position age, and instrument thresholds with Treasury and Accounting. Copy accepted values into GRAND; the file is editable planning material, not an automatic official form.", "Each route has one clear locally reviewed rule.", "Use Observe first when acceptance or evidence is incomplete.", "Open Cash Position", "vouchers:cash_workspace"),
            ("Prepare and submit the policy", "Choose the active Finance setup, bank, fund, mode, reserve, thresholds, and effective dates. Cite the reviewed authority and where local acceptance is retained, then submit to a different Accounting reviewer.", "Only an Active policy can support cash positions or ageing classification.", "Do not hard-code a generic validity period when the applicable bank/local rule is unresolved.", "", ""),
            ("Prepare the cash position", "GRAND pins the latest reconciled bank/book balance. Add only confirmed later inflows and outflows, reviewed restricted cash, and the source schedule reference.", "Available cash equals reconciled book balance plus confirmed inflows, less confirmed outflows, other holds, the minimum reserve, and existing issued reservations.", "Budget availability is a separate upstream control and cannot substitute for cash availability.", "", ""),
            ("Use the modification allowance", "Before approval, replace a returned same-date schedule with a successor and explain the correction in Preparation note. Before any check exists, use the voucher's guided correction route for eligible DV fields and evidence.", "Prior cash and voucher evidence stays visible; issued instruments are never silently edited.", "After check issue, use cancellation/replacement or Accounting adjustment routes as applicable.", "", ""),
            ("Issue against the approved position", "At check issue, choose the obligation's fund. Observe mode records available context when possible; Enforce mode requires a current approved position and sufficient cash after all reservations.", "Each eligible check pins a reservation to the approved position.", "A cash pass does not override budget, posting, advice, claimant, or release controls.", "Open Finance Queue", "vouchers:workspace"),
            ("Classify ageing with evidence", "Use the ageing queue only after the policy threshold. Record follow-up evidence for unclaimed checks, block stale checks from release, and record bank evidence for returned released checks.", "The original issue/advice/release history remains unchanged and the exception stays open until resolved.", "Age alone does not cancel a check or release its cash reservation; cancellation/stop-payment and Accounting action must follow the accepted route.", "Open Cash Position", "vouchers:cash_workspace"),
            ("Resolve, export, and safeguard", "Record the claimant release, cancellation/replacement, bank acknowledgement, or Accounting correction that resolved the exception. Export when requested and copy or synchronize the complete GRAND export root.", "Cash policy, positions, reservations, exceptions, checksums, and manifests remain together under the TraceSync-ready department/user/category tree.", "Copy the whole export root rather than an isolated CSV when preserving evidence.", "", ""),
        ),
    },
    {
        "slug": "finance-treasury-remittance",
        "version": 3,
        "title": "Prepare and release withholding remittances",
        "summary": "Build one-fund agency schedules from posted withholding balances, use the pre-release modification allowance, and complete only after Accounting posts.",
        "permission": "vouchers.prepare_remittances",
        "patterns": ["vouchers:remittance_*"],
        "order": 10,
        "steps": (
            ("Start from posted balances", "Open Remittances, choose the active Finance setup, transaction group, receiving government agency, fund, payment account, date, method, and reviewed authority/evidence references.", "A controlled remittance number is reserved and only posted subsidiary balances for that transaction group are offered.", "Use one fund per batch and do not re-encode an unposted voucher deduction.", "Open Remittances", "vouchers:remittance_workspace"),
            ("Build the schedule", "Select each posted withholding balance and enter the amount supported by the reviewed return or schedule. GRAND reserves it against concurrent batches.", "The active line total equals the batch control total without exceeding availability.", "Separate agency, fund, or transaction groups into their proper batches.", "", ""),
            ("Use the modification allowance", "Before submission, or after Accounting returns the batch, use Revise. Enter a corrected amount or zero to remove and record the reason.", "The prior line and its successor remain visible in retained history.", "After approval the schedule is read-only; after actual release use Accounting correction routes rather than rewriting it.", "", ""),
            ("Submit for independent review", "Send the reconciled schedule to Accounting and wait for approval or a specific return reason.", "Accounting reviews the same checksum-backed batch; Treasury cannot self-approve through its normal role.", "Do not release a returned or merely submitted schedule.", "", ""),
            ("Record actual release once", "For an approved batch, record the bank/payment release reference and agency acknowledgement or official receipt when available.", "GRAND closes the modification window and creates a controlled JEV request.", "Do not repeat release while Accounting is posting or replacing a discarded draft.", "", ""),
            ("Record governed tax filing evidence", "For a homogeneous governed-tax batch, record the exact form, tax period, actual filing date/channel/reference, payment confirmation, and restricted evidence-custody reference. Choose the approved, reconciled GRAND return/remittance summary for that exact form and period; GRAND copies its report, template, control, and output checksums automatically.", "A checksum-backed draft with reconstructible GRAND report lineage is ready for independent Accounting verification.", "Use the advanced external-schedule fallback only when locally required, and record its reference, SHA-256, and plain-language reason. GRAND does not submit the return, calculate the deadline, or accept passwords and unnecessary taxpayer data.", "", ""),
            ("Correct or amend visibly", "Correct a Draft or Accounting-returned evidence record and resubmit it. If already verified, start an Amended successor and explain why.", "The verified prior version remains retained as Superseded while the new draft carries explicit amendment lineage.", "Never rewrite verified filing evidence or the released remittance schedule.", "", ""),
            ("Confirm completion and export", "Wait for Accounting to post the JEV, then export the register when needed. Copy or synchronize the complete GRAND export root with sibling manifests.", "The batch reads Remitted and posted; the subsidiary liability is reduced and portable evidence is retained.", "The CSV is controlled interchange, not automatically an official agency, COA, or local form.", "", ""),
        ),
    },
    {
        "slug": "finance-treasury-payment",
        "version": 2,
        "title": "Prepare, advise, and release a payment instrument",
        "summary": "Issue and release checks only through the shared case, with cancellation/replacement history and advice controls intact.",
        "permission": "vouchers.issue_payment_instruments",
        "patterns": ["vouchers:*"],
        "order": 20,
        "steps": (
            ("Confirm payment readiness", "Open a case in Treasury check preparation and verify its posted Accounting handoff, net amount, payee, payment account, and cash/payment prerequisites.", "The case is authorized for instrument preparation under the enabled pilot route.", "Never issue from an unposted or mismatched case.", "Open Finance Queue", "vouchers:workspace"),
            ("Register the physical check", "Record the controlled check number, amount, account, preparer, and issue evidence. Issued numbers are never silently reused.", "The case carries a traceable payment instrument.", "Issuance closes the convenience modification window for voucher fields.", "", ""),
            ("Handle exceptions visibly", "For spoilage or error before release, cancel with a reason and create a linked replacement; do not edit the issued instrument. The pinned local rule records either a JEV handoff or an explicit no-entry decision.", "The cancelled and replacement instruments and their accounting decisions remain in one history.", "Never reuse a cancelled physical check number or treat a no-entry decision as missing work.", "", ""),
            ("Release only after advice", "After the applicable accountant/bank advice is finalized, record the actual claimant, receipt reference, and release. If the pinned payment rule posts on release, the case moves temporarily to Accounting.", "The exact released instrument and amount become an immutable payment-event handoff.", "Do not repeat the release while Accounting is posting its JEV.", "", ""),
            ("Resume the same release queue", "After Accounting posts the event JEV, reopen the same case. GRAND returns it to release remaining advised checks or completes it when the last check is settled.", "Each partial release is posted once and the shared case preserves its place.", "Do not create a second voucher to continue a split payment.", "Open Finance Queue", "vouchers:workspace"),
            ("Export the portable payment register", "Use Export payment register when authorized. Copy or synchronize the complete GRAND export root so the CSV stays beside its checksum manifest under department/user/category/year/month.", "Check lineage, advice, claimant, receipt, cancellation, replacement, and posting status remain portable for safekeeping.", "The CSV is controlled interchange, not automatically an accepted official COA/local form.", "", ""),
        ),
    },
)


REQUESTING_GUIDES = REQUESTING_GUIDES + (
    {
        "slug": "finance-shadow-stakeholder-acceptance",
        "version": 4,
        "title": "Review and accept your office's shadow/UAT scope",
        "summary": "Use the floating guide while reviewing the exact enabled scope, role exercise, and comparison evidence assigned to you.",
        "permission": "",
        "patterns": ["finance:shadow_*", "finance:stakeholder_*", "finance:field_acceptance_*"],
        "order": 90,
        "steps": (
            ("Open your assigned cycle", "Open Shadow operation & cutover and choose the cycle assigned to you. Read the office, transaction, fund, and date scope before reviewing results.", "You can see the shared cycle without receiving Finance preparation or cutover authority.", "Do not accept work outside the written scope or assume another office's acceptance covers yours.", "Open Shadow operation", "finance:shadow_workspace"),
            ("Read the shared acceptance board", "Choose your assigned cycle in the Field Acceptance Board. Read the ten evidence checkpoints and the exact enabled scope, then open the cycle workspace for the records assigned to you.", "The board points to current governed evidence and refreshes when those source records change.", "Board percentages and tutorial checkmarks are coordination aids; neither is an approval or employee rating.", "Open Field Acceptance Board", "finance:field_acceptance_board"),
            ("Complete the role exercise", "Follow the department procedure with synthetic or properly redacted cases, including normal work, a return/correction, and the applicable exception route.", "You can complete your role without borrowed permissions or hidden manual steps.", "The personal checkmarks in this guide help you resume learning; supervisors do not use them as attendance, performance, or acceptance evidence.", "", ""),
            ("Submit observable exercise evidence", "Open the named role exercise, compare its procedure and expected result with what you actually performed, then reference the retained redacted observation sheet, output, or supervisor record.", "The result waits for the separately assigned witness; submitting it does not pass the exercise.", "Do not paste confidential case content or use this guide's private progress checkmarks as evidence.", "", ""),
            ("Complete a witnessed rerun when required", "If the witness returns the result, follow the exact correction or rerun request and submit the new actual result and evidence reference.", "The final passed record retains its owner, witness, checksum, and basis while the earlier return remains in audit history.", "The exercise owner cannot witness their own result.", "", ""),
            ("Compare expected and actual results", "Review the retained UAT script, control totals, outputs, printing/custody steps, and unresolved limitations for your exact scope.", "Each result is traceable to a named exercise and retained evidence reference.", "A technically successful screen is not proof that the business process, form, or local authority is accepted.", "", ""),
            ("Record your own decision", "Choose Accepted, Accepted with conditions, or Not accepted. Reference role-training evidence, the exact UAT scenarios, and the retained wet-signed or locally accepted attributable decision record; enter that copy's SHA-256.", "Your attributed decision, retained-record reference, and file lock cannot be overwritten.", "GRAND records a reference and checksum; it does not store a signature image or claim to create the signature. Conditional or rejected decisions block cutover.", "", ""),
            ("Export when evidence is requested", "Download the cycle evidence package when authorized. Preserve the complete TraceSync-ready GRAND export root so the JSON remains beside its checksum manifest.", "The portable copy contains comparisons, acceptance decisions, and the cutover state visible at export time.", "An exported file is evidence, not an authority decision by itself.", "", ""),
        ),
    },
)


ACCOUNTING_GUIDES = ACCOUNTING_GUIDES + (
    {
        "slug": "finance-discovery-decision-register",
        "version": 3,
        "title": "Record Finance findings and unresolved decisions",
        "summary": "Turn interviews and reviewed evidence into scoped, independently reviewed Finance decisions without silently inventing policy.",
        "permission": "finance.manage_finance_discovery",
        "patterns": ["finance:discovery_*", "finance:field_acceptance_*"],
        "order": 88,
        "steps": (
            ("Start from editable coverage prompts", "For a candidate shadow or parallel cycle, choose Add coverage starters, then assign one evidence owner, a different reviewer, and an optional review date. GRAND creates a whole-scope prompt plus step, field, balance, certification, signature, number, output, and exception prompts.", "Nine ordinary drafts make the minimum discovery areas visible without deciding their answers for the LGU; running the starter again creates only a missing current area.", "Every prompt starts Unresolved. Edit its wording and add more focused rows wherever the actual local process needs them.", "Add coverage starters", "finance:discovery_coverage_starters"),
            ("Work the items needing attention", "Filter by candidate cycle, phase, workflow state, or Needs attention. Use Current scope blockers for work preventing the named scope, Awaiting named reviewer for queued checks, Overdue open work for missed review dates, and Returned for correction for rework.", "The list and manager's department export use the same selected filters; overdue dates are marked in the row.", "A filter is a work aid only. It does not change, accept, return, or clear any evidence.", "Open Decisions & Evidence", "finance:discovery_workspace"),
            ("Add one focused question", "Create one stable DEC reference for a missing authority, disagreement, local procedure, form, balance, role, or exception. Choose its roadmap phase and optionally link the exact shadow cycle.", "The question is readable and narrow enough for one accountable decision.", "Do not combine unrelated offices, transaction types, years, forms, or actions into one broad block.", "Open Decisions & Evidence", "finance:discovery_workspace"),
            ("Use the evidence label literally", "Choose Observed in eGAPS, Official reference, LGU-confirmed, GRAND-implemented, or Unresolved according to what the retained evidence actually proves.", "The label, cited reference, custody location, and evidence still needed agree with one another.", "A public memo does not prove local applicability; a system screen does not prove hidden validation or authority.", "", ""),
            ("Name only the affected scope", "Write the exact transaction type, office, fiscal year, form, output, or action affected. Keep Block affected scope selected while an Unresolved finding remains.", "Staff can tell what must wait and what unrelated work may continue.", "Never use an unresolved question to freeze all Finance work when only a smaller scope is uncertain.", "", ""),
            ("Assign owner and reviewer", "Name the person responsible for preparing the evidence and a different person who can independently review the decision.", "The owner can correct and submit; only the named different reviewer can record or return the locked snapshot.", "Do not assign the same person to prepare and review their own decision.", "", ""),
            ("Reference an acceptance example", "For each coverage row, identify the retained blank or redacted example, replay result, control total, or the accepted explanation that no local case applies. Keep the protected artifact with its custodian.", "A reviewer can see what concrete example supports the LGU-confirmed label without GRAND storing confidential bytes.", "A whole-scope declaration cannot replace the detailed coverage rows and their examples.", "", ""),
            ("Submit a checksum-backed snapshot", "Review the coverage area, plain-language outcome, evidence references, acceptance example, custody, needed proof, scope, and blocker flag, then submit it.", "GRAND locks the submitted fields with a SHA-256 and records the action in append-only Finance audit history.", "Submission is not acceptance and does not create COA, DBM, BIR, bank, ordinance, or cutover authority.", "", ""),
            ("Review or return independently", "The named reviewer compares the cited retained evidence, then records the decision or returns it with the exact correction required.", "A recorded Unresolved decision remains visibly scope-blocking; a supported decision reflects only what its label and affected scope prove.", "A deadline or manager preference cannot convert missing evidence into a confirmed rule.", "", ""),
            ("Correct through the right route", "Edit Draft or Returned work. For a recorded decision, create a reasoned successor, update the evidence, and repeat independent review.", "When the successor is recorded, the predecessor becomes Superseded while both snapshots and audit events remain reconstructible.", "Do not overwrite or delete a recorded decision merely because the authority, form, or local practice changed.", "", ""),
            ("Export and safeguard", "Export one decision when its named reviewer needs it. To safeguard the department register, apply the Phase and Workflow state filters, then choose Export department register. Copy or synchronize the complete GRAND export root so every CSV remains beside its checksum manifest.", "Per-record files use department/user/finance-discovery-decisions/year/month; manager register files use department/user/finance-discovery-register/year/month.", "The filtered register is department-bounded. Every export is an evidence index, not the protected source file, an official form, a backup, or cutover authority.", "Open Decisions & Evidence", "finance:discovery_workspace"),
        ),
    },
    {
        "slug": "finance-shadow-cutover-manager",
        "version": 5,
        "title": "Run shadow reconciliation and prepare cutover evidence",
        "summary": "Plan a limited cycle, lock exact comparisons, collect separate office decisions, and keep authority and rollback explicit.",
        "permission": "finance.manage_shadow_operation",
        "patterns": ["finance:shadow_*", "finance:cutover_*", "finance:field_acceptance_*"],
        "order": 89,
        "steps": (
            ("Start with the Field Acceptance Board", "Choose the exact candidate cycle and review its ten evidence checkpoints. Use each plain-language next action to return to the governed cycle records; export the board when a coordinator or records custodian needs a portable status copy.", "The board reflects current source locks, plans, exercises, form lineage, field cycles, reconciliation, stakeholder decisions, and cutover authority without creating a second approval list.", "Do not report the percentage as phase acceptance. GRAND remains in shadow/UAT mode until the separately recorded cutover authority is Authorized for the exact scope and date.", "Open Field Acceptance Board", "finance:field_acceptance_board"),
            ("Define a limited cycle", "Name the exact offices, funds, transaction types, and dates. Reference where the locally authoritative, redacted/read-only comparison source is retained.", "A draft plan identifies what is and is not being compared without importing a production database.", "Public COA/DBM material or an eGAPS export does not prove local applicability by itself.", "Open Shadow operation", "finance:shadow_workspace"),
            ("Stage the safe comparison copy", "Upload a UTF-8 redacted CSV up to 5 MB. Confirm what was removed or masked. GRAND calculates the file lock, normalized headings, row count, and column-layout lock without importing its rows into Finance transactions.", "A retained v1 source record shows the safe inspection results and any sensitive-heading reminder.", "Never upload a live database, executable spreadsheet, credentials, or unrestricted production export.", "Open Shadow operation", "finance:shadow_workspace"),
            ("Replace before start when needed", "While the cycle is still Draft, stage the corrected copy and explain why. GRAND retains the earlier version and marks only the successor current.", "The replacement reason and both version locks remain reconstructible.", "After the cycle starts, source changes require a successor cycle rather than an overwritten file.", "", ""),
            ("Resolve changed headings independently", "When GRAND flags a layout change against the predecessor or prior draft version, ask a different reconciliation reviewer to name the added, removed, or renamed columns and record the safe mapping basis.", "Accepted drift opens the start gate; rejected or pending drift keeps it closed.", "Schema acceptance does not approve transaction content, official forms, or cutover authority.", "", ""),
            ("Approve the actual local cadence", "Prepare the cycle's calendar-day or working-day schedule, grace period, minimum reviewed-run count, enabled transaction types, and Critical/High/Medium/Low correction targets and escalation routes. Submit it to a different reconciliation reviewer.", "The approved checksum-backed plan opens the cycle start gate and pins the local rules used for defect due times.", "The editable starter values are not COA, DBM, or local requirements. Replace them with the retained locally accepted decision.", "", ""),
            ("Open and review each scheduled run", "Open the next due run, maintain the current exact comparisons, register every open difference, then snapshot and submit. A different reviewer accepts the exact snapshot as reconciled or reviewed with exceptions, or returns it.", "Each run retains its schedule, due time, controls, defects, counts, checksum, actors, and review basis.", "Reviewed with exceptions makes a defect visible; it does not close the defect or permit final cycle reconciliation by itself.", "", ""),
            ("Triage and escalate without hiding", "For each open comparison, choose severity independently, describe impact, and name its owner. GRAND applies the approved correction target and escalation route. Record actual escalation contacts and requested action when needed.", "The queue shows due and overdue work while every escalation remains attributable.", "A polished screen or small amount does not automatically make a control defect low severity.", "", ""),
            ("Verify correction independently", "The owner submits a plain-language correction and retained evidence reference. A different reconciliation reviewer verifies it, accepts it, or reopens it with a specific reason.", "Accepted resolution changes the current comparison to explained while preserving the original open run and defect history.", "Do not overwrite the earlier run snapshot or mark a defect resolved merely because work began.", "", ""),
            ("Run and compare controls", "Add case, batch, period, register, ledger, and report controls as applicable. GRAND calculates entered amount and count differences.", "Zero controls read Matched; every difference is explained or remains an owned blocking defect.", "Do not hide an open defect inside a narrative explanation merely to advance the gate.", "", ""),
            ("Lock for independent reconciliation", "Submit only after resolving open defects. GRAND pins the comparison payload and checksum; a different authorized reviewer accepts it or requires a successor cycle.", "The exact reviewed evidence is immutable and attributable.", "A returned submitted cycle is not reopened for editing; make the correction in a successor.", "", ""),
            ("Assign each stakeholder", "Create separate rows for requesting offices, Budget, Accounting, Treasury, IT, management, and audit. Name the person who will decide each exact scope.", "Each stakeholder records their own training/UAT references and decision.", "Personal Internal How-To progress stays private and never substitutes for training or UAT evidence.", "", ""),
            ("Approve the curriculum and support plan", "Reference the actual role curriculum register, floating or desk quick guides, supervisor runbook, support owner, operating hours, backup contact, and escalation procedure. Submit it to a different reconciliation reviewer.", "The checksum-backed approved plan becomes the local basis for scheduling readiness work.", "Keep the learning-privacy notice: personal guide progress is not attendance, competence, acceptance, or employee-evaluation evidence.", "", ""),
            ("Schedule the required exercises", "Create one role exercise for every named stakeholder and separate security/access, privacy, accessibility, performance, printing/custody, backup/restore, business-continuity, and incident/support exercises. Write human-followable steps and observable pass results.", "Every exercise pins its owner, different witness, due time, exact scope, and approved support route.", "These are configurable local exercise details, not invented COA, DBM, BIR, printer, or infrastructure requirements.", "", ""),
            ("Record the two-store recovery rehearsal", "For the backup/restore exercise, enter the exact copied GRAND backup-set ID and hashes, the separately retained manifest hash, off-host custody and preflight references, approved RPO/RTO, actual recovery times, both restored stores and migrations, reconciled control totals, one cross-store case, runtime-file checks, exceptions, and secure disposal reference.", "GRAND calculates actual RPO/RTO, seals the complete record with a checksum, and gives the witness one visible pass-or-rerun decision.", "A readable backup or passing preflight is not a restore. If either target or control is missed, record it honestly; the witness returns the exercise and the owner records a corrected rerun without erasing the earlier event.", "", ""),
            ("Witness results or require a rerun", "The assigned owner submits actual results and retained redacted evidence. Only the different assigned witness can pass the exercise or return it with the exact rerun needed.", "Passed evidence becomes immutable; returned evidence can be corrected without erasing the earlier audit event.", "A successful screen alone does not prove privacy, printing, recovery, continuity, performance, or incident readiness.", "", ""),
            ("Approve the field-cycle rule", "For the candidate cutover cycle, set the locally accepted minimum consecutive-cycle count, whether a controlled parallel run is mandatory, and the retained local authority, rules/forms note, and field-proof basis. Before submission, add every applicable current F10.2 Accepted form and explain where staff use that exact version.", "The checksum-backed plan pins each selected form's accepted snapshot, department, version, and reference/source/submission file locks for independent review.", "A narrative register reference cannot replace exact form selection. The starter minimum of two is editable; change it only from a retained local decision.", "", ""),
            ("Build the predecessor chain", "Add each independently reconciled field cycle from oldest to newest. Reference the retained field-execution packet and the rules, reports, and print layouts used; submission automatically pins the plan's exact accepted-form set into that row.", "The accepted rows form one uninterrupted predecessor chain ending at the candidate, include a parallel cycle when required, and all carry the same current form-set checksum.", "Synthetic UAT alone is not field execution. If a selected form is superseded or changed, readiness fails and the new form needs a successor cycle and fresh qualification plan.", "", ""),
            ("Prepare authority last", "After the field chain and all seven stakeholder kinds pass, select the independently passed recovery rehearsal for this exact cycle, then record the authority matrix, exact cutover date/scope, opening reconciliation, continuity evidence, rollback criteria, legacy retention plan, and retained signed authority record reference, checksum, and custodian.", "The decision permanently identifies the exact backup ID and recovery-evidence checksum. A different authorized user can record go/no-go; GRAND becomes authoritative only for an authorized exact scope/date.", "GRAND does not create or store the signature image. Do not treat configuration activation, pilot reconciliation, report agreement, or an unbound recovery narrative as implicit cutover.", "", ""),
            ("Rollback without erasing", "If a recorded criterion is triggered, the authorized role records the incident and operating direction against the same decision.", "The decision reads Rolled back while the original authorization and evidence remain reconstructible.", "Do not delete the pilot, stakeholder decisions, or original authority record.", "", ""),
        ),
    },
)


def _department_kind(department):
    identity = f"{department.slug or ''} {department.name or ''}".lower()
    if "budget" in identity:
        return "budget"
    if "treasur" in identity:
        return "treasury"
    if "account" in identity or "acctg" in identity or "finance" in identity:
        return "accounting"
    return ""


@transaction.atomic
def seed_finance_internal_howtos():
    counts = {"departments": 0, "guides_created": 0, "guides_preserved": 0, "guides_retired": 0}
    definitions = {"accounting": ACCOUNTING_GUIDES, "budget": BUDGET_GUIDES, "treasury": TREASURY_GUIDES}
    for department in Department.objects.all().order_by("pk"):
        kind = _department_kind(department)
        counts["departments"] += 1
        department_guides = REQUESTING_GUIDES + definitions.get(kind, ())
        for definition in department_guides:
            target_version = definition.get("version", 1)
            published = InternalHowTo.objects.filter(
                department=department,
                slug=definition["slug"],
                status=InternalHowTo.PUBLISHED,
            ).order_by("-version").first()
            if published and published.version >= target_version:
                counts["guides_preserved"] += 1
                continue
            target_retired = InternalHowTo.objects.filter(
                department=department,
                slug=definition["slug"],
                version=target_version,
                status=InternalHowTo.RETIRED,
            ).exists()
            if target_retired:
                counts["guides_preserved"] += 1
                continue
            guide, created = InternalHowTo.objects.update_or_create(
                department=department,
                slug=definition["slug"],
                version=target_version,
                defaults={
                    "title": definition["title"],
                    "summary": definition["summary"],
                    "required_permission": definition["permission"],
                    "page_patterns": definition["patterns"],
                    "sort_order": definition["order"],
                    "status": InternalHowTo.DRAFT,
                },
            )
            guide.steps.all().delete()
            InternalHowToStep.objects.bulk_create([
                InternalHowToStep(
                    how_to=guide,
                    position=position,
                    title=title,
                    instruction=instruction,
                    expected_result=expected,
                    caution=caution,
                    action_label=action_label,
                    action_route_name=action_route,
                )
                for position, (title, instruction, expected, caution, action_label, action_route)
                in enumerate(definition["steps"], start=1)
            ])
            if published:
                published.status = InternalHowTo.RETIRED
                published.save(update_fields=("status", "updated_at"))
                counts["guides_retired"] += 1
            guide.status = InternalHowTo.PUBLISHED
            guide.full_clean()
            guide.save(update_fields=("status", "updated_at"))
            counts["guides_created"] += 1 if created else 0
    return counts
