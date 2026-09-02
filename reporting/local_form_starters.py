"""Built-in, non-authoritative DBM form starters for the F10 local-form register."""

from __future__ import annotations


DBM_BOM_URL = (
    "https://www.dbm.gov.ph/wp-content/uploads/Issuances/2023/Local-Budget-Circular/"
    "Budget%20Operations%20Manual%20for%20LGUs%2C%202023%20Edition.pdf"
)

FAMILY_LABELS = {
    "LBP": "Budget preparation",
    "LBA": "Budget authorization",
    "LBR": "Budget review",
    "LBE": "Budget execution",
    "LBAc": "Budget accountability",
}


def section(
    label, requirement_type, fields, source, control, owner, print_rule,
    *, applicability="", rows="",
):
    return {
        "label": label,
        "requirement_type": requirement_type,
        "field_instructions": fields,
        "source_instructions": source,
        "control_instructions": control,
        "owner_instructions": owner,
        "print_instructions": print_rule,
        "applicability_instructions": applicability,
        "row_instructions": rows,
    }


def repeating(label, fields, source, control, owner, print_rule):
    return section(
        label, "repeating", fields, source, control, owner, print_rule,
        rows=(
            "Confirm the accepted rows per page, repeated headings, stable row order, "
            "and numbered continuation-page behavior from the current local form."
        ),
    )


def conditional(label, fields, source, control, owner, print_rule):
    return section(
        label, "conditional", fields, source, control, owner, print_rule,
        applicability=(
            "The named local process owner must record the retained fact and authority that "
            "makes this section applicable or not applicable."
        ),
    )


def form(key, family, number, title, manual_pages, pdf_pages, purpose, owner, sections):
    return {
        "key": key,
        "family": family,
        "family_label": FAMILY_LABELS[family],
        "form_number": number,
        "title": title,
        "manual_pages": manual_pages,
        "pdf_pages": pdf_pages,
        "purpose": purpose,
        "owner_note": owner,
        "sections": sections,
    }


LBP_FORMS = (
    form("lbp-form-1", "LBP", "LBP Form No. 1", "Budget of Expenditures and Sources of Financing", "59–61", "74–76", "Prepare the annual resource, expenditure, and financing program.", "Local Finance Committee and Local Accountant; approved by the LCE.", (
        section("Form identity and comparison periods", "required", "LGU, fund, budget year, and past/current/proposed period labels.", "Finance Setup and annual budget cycle.", "All columns use the same approved period basis.", "Local Finance Committee and Accounting.", "Repeat identity and period headings."),
        repeating("Receipts and available resources", "Beginning cash; regular and non-regular income; local/external sources; financing.", "Approved resource estimates and posted historical receipts.", "Section subtotals and total available resources cross-foot.", "Treasury, Accounting, and Budget.", "Preserve the account hierarchy and amount format."),
        repeating("Expenditures, financing, and certification", "Expense classes/objects; debt/financing; surplus or deficit; certification.", "Department proposals, debt records, and financing plan.", "Expenditures, financing, and budget balance reconcile.", "Local Finance Committee, Accounting, and LCE.", "Retain totals and wet-signature space."),
    )),
    form("lbp-form-2", "LBP", "LBP Form No. 2", "Programmed Appropriation and Obligation by Object of Expenditure", "62–63", "77–78", "Compare actual/current estimates with proposed appropriations by expense object.", "Department Head; reviewed by LBO; approved by LCE.", (
        repeating("Object-of-expenditure schedule", "LGU, department, object, account code, and past/current/proposed amounts.", "Department proposal and posted historical expenses.", "Period columns and account mapping use one accepted basis.", "Department and Budget.", "Repeat expense-class headings."),
        section("Expense-class totals and certification", "required", "PS, MOOE, FE, CO, special-purpose appropriations, totals, and signatures.", "Classified proposal totals and wet-signature route.", "Class totals reconcile to the department proposal.", "Department Head, LBO, and LCE.", "Keep totals and signature blocks together."),
    )),
    form("lbp-form-3", "LBP", "LBP Form No. 3", "Plantilla of Personnel", "64–66", "79–81", "Present current and proposed positions and compensation.", "HRMO; reviewed by LBO; approved by LCE.", (
        repeating("Position identity", "Old/new item number, position title, incumbent, vacancy, abolition, or reclassification.", "Approved plantilla and HR records.", "Each current/proposed item retains a stable row identity.", "HRMO and Budget.", "Do not split a position across pages."),
        repeating("Salary comparison", "Current rate/amount; proposed salary grade/step/rate/amount; increase or decrease.", "Approved compensation schedule and proposed PS.", "Increases, decreases, and total PS reconcile.", "HRMO and Budget.", "Use currency/count formats and repeated headings."),
        section("Plantilla certification", "required", "Prepared, reviewed, and approved names, titles, signatures, and dates.", "Wet-signature custody evidence.", "Never represent a paper signature as a digital signature.", "HRMO, LBO, and LCE.", "Preserve signature space."),
    )),
    form("lbp-form-4", "LBP", "LBP Form No. 4", "Mandate, Vision/Mission, Major Final Output, Performance Indicators and Targets by Department/Office", "89", "104", "Connect department mandates and targets to classified proposed resources.", "Department Head; reviewed by LFC; approved by LCE.", (
        section("Department identity and mandate", "required", "LGU, department, fiscal year, mandate, vision, mission, and organizational outcome.", "Department profile and proposal narrative.", "Use the exact approved narrative version.", "Department Head and LFC.", "Allow readable continuation without shrinking text."),
        repeating("PPA, MFO, indicators, and targets", "AIP reference, PPA, MFO, performance indicator, and target.", "Annual proposal and AIP mapping.", "Row count and AIP references reconcile.", "Department and Budget.", "Repeat headings and avoid split rows."),
        repeating("Classified resource requirements", "PS, MOOE, FE, CO, and total.", "Classified proposal amounts.", "Total equals PS plus MOOE plus FE plus CO.", "Budget.", "Use accounting amount format."),
        section("Review and approval", "required", "Prepared, reviewed, and approved names, titles, signatures, and dates.", "Wet-signature custody evidence.", "Never imply a digital signature.", "Department, LFC, and LCE.", "Preserve signature space."),
    )),
    form("lbp-form-5", "LBP", "LBP Form No. 5", "Statement of Indebtedness", "67", "82", "Disclose debt contracts, payments, amounts due, and principal balances.", "Certified by Local Accountant; noted by LCE.", (
        repeating("Debt identity", "Creditor, contract date, term, principal amount, and purpose.", "Approved debt and contract register.", "Instrument identity agrees with retained evidence.", "Accounting.", "Repeat headings; keep creditor and purpose readable."),
        repeating("Payments, amounts due, and balance", "Prior principal/interest/total payments; principal/interest due; ending balance; certification.", "Posted debt-service transactions and schedule.", "Opening principal less principal payments equals the balance; totals cross-foot.", "Local Accountant and LCE.", "Accounting format and signature space."),
    )),
    form("lbp-form-6", "LBP", "LBP Form No. 6", "Statement of Statutory and Contractual Obligations and Budgetary Requirements", "68", "83", "List locally applicable mandatory obligations and budgetary requirements.", "Certified by LFC; approved by LCE.", (
        repeating("Statutory, contractual, and budgetary requirements", "Requirement description, authority category, and amount.", "Approved policy, contract, personnel, debt, and budget rules.", "Section subtotals and overall total cross-foot.", "Local Finance Committee.", "Keep authority notes readable."),
        section("Committee certification and approval", "required", "Budget Officer, Treasurer, Accountant, and LCE signature blocks.", "Wet-signature custody evidence.", "Never imply a digital signature.", "LFC and LCE.", "Preserve totals and signature space."),
    )),
    form("lbp-form-7", "LBP", "LBP Form No. 7", "Statement of Fund Allocation by Sector", "69", "84", "Summarize appropriations by service sector.", "Certified by LBO; approved by LCE.", (
        repeating("Sector allocation", "Particular, account code, General Public/Social/Economic/Other Services, and total.", "Approved PPA and sector mapping.", "Row totals equal sector columns; sector totals equal appropriations.", "Budget.", "Repeat headings and sector labels."),
        section("Appropriation total and approval", "required", "Total appropriations, LBO certification, and LCE approval.", "Approved annual budget and wet-signature evidence.", "Form total equals the approved appropriation control.", "LBO and LCE.", "Accounting format and signature space."),
    )),
    form("lbp-form-8", "LBP", "LBP Form No. 8", "Statement of Funding Sources (Supplemental Budget)", "70", "85", "Certify the lawful funding source for a supplemental budget.", "Local Treasurer and/or Local Accountant depending on source.", (
        repeating("Supplemental funding sources", "Fund/special account, source particular, account classification, and amount.", "Supplemental funding evidence and accepted classifications.", "Source total equals available supplemental authority.", "Treasury and Accounting.", "Repeat headings and show source detail."),
        conditional("Source-dependent certification", "Treasurer and/or Accountant name, title, signature, and date.", "Funding-source authority and wet-signature evidence.", "Every source carries the required certification.", "Treasury and Accounting.", "Preserve conditional signature space."),
    )),
    form("lbp-form-9", "LBP", "LBP Form No. 9", "Statement of Supplemental Appropriation", "71", "86", "Allocate certified supplemental funding to approved purposes.", "Prepared by LBO; approved by LCE.", (
        repeating("Supplemental appropriation rows", "Implementing office, purpose/PPA, AIP reference, object, account code, and amount.", "Approved supplemental AIP and appropriation proposal.", "Amounts total to the certified supplemental source.", "Budget and implementing office.", "Repeat headings; do not split a PPA row."),
        section("Preparation and approval", "required", "LBO and LCE names, titles, signatures, and dates.", "Wet-signature custody evidence.", "Never imply a digital signature.", "LBO and LCE.", "Preserve totals and signature space."),
    )),
)


AUTHORIZATION_REVIEW_FORMS = (
    form("lba-form-1a", "LBA", "LBA Form No. 1A", "Checklist of Documentary and Signature Requirements for Annual Budgets", "109", "124", "Check the annual-budget enactment package and signatures.", "Budget and Sanggunian records; confirm locally.", (
        repeating("Annual-budget document checklist", "Document, required signatory, evidence reference, result, and remarks.", "Submitted annual-budget package.", "No required item is complete without exact evidence.", "Budget and Sanggunian records.", "Allow readable continuation."),
        conditional("Conditional annual-budget documents", "AIP/resolution, LEE operating budget, and other locally applicable items.", "Package profile and local decisions.", "Each item is satisfied or documented not applicable.", "Budget, LPDO, LEE, Sanggunian, and LCE.", "Keep remarks beside the related item."),
    )),
    form("lba-form-1b", "LBA", "LBA Form No. 1B", "Checklist of Documentary and Signature Requirements for Supplemental Budgets", "110–111", "125–126", "Check the supplemental-budget funding, enactment, AIP, and signatures.", "Treasury, Accounting, Budget, Sanggunian, and LCE; confirm locally.", (
        conditional("Funding and revenue documents", "Additional realized income, savings/reversion, new revenue measures, and authority.", "Supplemental funding and enacted authority evidence.", "Certified sources equal the proposed supplemental appropriation.", "Treasury, Accounting, and Sanggunian.", "Allow continuation and preserve signatories."),
        conditional("Supplemental AIP and approval", "Supplemental AIP, resolution, required signatories, and remarks.", "Supplemental AIP and enacted authority evidence.", "Every required document and signature is resolved.", "LPDO, LBO, Sanggunian, and LCE.", "Keep the checklist and signature labels readable."),
    )),
    form("lbr-form-1a", "LBR", "LBR Form No. 1A", "Checklist of Documentary and Signature Requirements for Review of Annual Budgets", "136", "151", "Record annual-budget review receipt, deadline, documents, signatures, and remarks.", "Reviewing authority; confirm locally.", (
        section("Review identity and deadline", "required", "Date received, deadline, LGU, class, budget title, and fund.", "Review submission and accepted calendar.", "Deadline comes from accepted authority, not a starter assumption.", "Reviewing authority.", "Repeat identity on continuation pages."),
        repeating("Annual review checklist", "Transmittal, message, ordinance, AIP, supporting document, signatory, and remark.", "Submitted annual-budget package.", "Missing or inconsistent items remain visible.", "Reviewing officer.", "Repeat headings and keep remarks readable."),
    )),
    form("lbr-form-1b", "LBR", "LBR Form No. 1B", "Checklist of Documentary and Signature Requirements for Review of Supplemental Budgets", "137–138", "152–153", "Record supplemental-budget review receipt, deadline, funding documents, signatures, and remarks.", "Reviewing authority; confirm locally.", (
        section("Review identity and deadline", "required", "Date received, deadline, LGU, class, budget title, and fund.", "Review submission and accepted calendar.", "Deadline comes from accepted authority.", "Reviewing authority.", "Repeat identity on continuation pages."),
        repeating("Supplemental review checklist", "Transmittal, ordinance, funds, new revenue, realignment/calamity, signatories, and remarks.", "Submitted supplemental-budget package.", "Every required item is evidenced or documented not applicable.", "Reviewing officer.", "Repeat headings and keep remarks readable."),
    )),
    form("lbr-form-2", "LBR", "LBR Form No. 2", "Summary of Findings and Recommended Review Actions", "139–152", "154–167", "Record detailed compliance findings and the resulting review action.", "Reviewing and approving authorities; confirm locally.", (
        section("Review identity", "required", "LGU, budget title, ordinance, reviewed amount, and package references.", "Review submission and enacted budget evidence.", "Identity agrees with the documentary checklist.", "Reviewing officer.", "Repeat identity across the multi-page form."),
        repeating("Findings and recommended actions", "Finding, compliant yes/no result, authority, evidence, and recommended action.", "Applicable review policies and submitted evidence.", "Every applicable finding has one attributable decision and action.", "Reviewing and subject officers.", "Repeat headings across the long form."),
        section("Overall review action", "required", "Operative/inoperative outcome, conditions, and prepared/reviewed/approved blocks.", "Completed findings and wet-signature evidence.", "Overall action agrees with unresolved findings.", "Reviewing and approving authorities.", "Keep outcome and signatures together."),
    )),
    form("lbr-form-2a", "LBR", "LBR Form No. 2A", "Total Personal Services Cost for Waived Items", "153", "168", "Itemize authority-backed PS costs that may be excluded from a limitation computation.", "Budget review, HR, and Accounting; confirm locally.", (
        repeating("Waived PS cost components", "Transferred hospital-service and other permitted salary, benefit, and contribution items.", "Personnel budget and accepted waiver authority.", "Subtotals and total waived PS cost cross-foot.", "Budget reviewer, HR, and Accounting.", "Preserve the official item hierarchy."),
        section("Waiver authority and total", "required", "LGU, waiver basis, subtotal/total, and reviewer evidence.", "Applicable waiver decision and review evidence.", "Only authority-backed amounts enter the total.", "Reviewing authority.", "Show the authority reference with the total."),
    )),
    form("lbr-form-2b", "LBR", "LBR Form No. 2B", "Determination on Personal Services Limitation Compliance", "154", "169", "Calculate and document compliance with the applicable PS limitation.", "Budget review and Accounting; confirm locally.", (
        section("Income and applicable limit", "required", "TIRS, accepted 45%/55% factor, and calculated PS limit.", "Posted preceding-year regular income and accepted LGU classification.", "The factor is explicit and the limit recalculates from TIRS.", "Budget review and Accounting.", "Use percentage and currency formats."),
        repeating("PS cost components", "Positions, salaries, compensation, benefits, contributions, and other authorized items.", "Plantilla and PS proposal.", "Components total to PS subject to limitation.", "Budget review, HR, and Accounting.", "Preserve component hierarchy."),
        section("Compliance conclusion", "required", "Total PS, waived items, adjusted PS, excess/margin, and decision evidence.", "Calculated schedule and Form 2A where applicable.", "Adjusted PS comparison reproduces the conclusion.", "Reviewing authority.", "Show the conclusion with supporting totals."),
    )),
)


def allotment_release_form(key, number, title, pages, pdf_pages, expense_class):
    return form(key, "LBE", number, title, pages, pdf_pages, f"Authorize and trace an allotment release for {expense_class}.", "LBO recommendation; LCE approval.", (
        section("Release identity and authority", "required", "Annual/supplemental/reenacted source, FY, LGU, fund, department, and purpose.", "Adopted budget and allotment plan.", "Source is active and applicable.", "Budget.", "Repeat identity on each page."),
        repeating("Appropriation and release rows", f"PPA code/description, account, authorized {expense_class} appropriation, later release, previous release, and this release.", "Appropriation and allotment movement registers.", "Later plus previous plus this release equals authorized appropriation.", "Budget.", "Repeat headings and use accounting format."),
        section("Amount, notes, recommendation, and approval", "required", "Total, amount in words, notes, recommendation, approval, ARO number/date/page.", "Approved movement and wet-signature evidence.", "Pinned movement and print checksum agree.", "Budget and LCE.", "Preserve totals, notes, and signature space."),
    ))


EXECUTION_FORMS = (
    allotment_release_form("lbe-form-1", "LBE Form No. 1", "Allotment Release Order for Personal Services", "178–179", "193–194", "Personal Services"),
    allotment_release_form("lbe-form-1a", "LBE Form No. 1A", "Allotment Release Order for Maintenance and Other Operating Expenses", "180–181", "195–196", "MOOE"),
    allotment_release_form("lbe-form-1b", "LBE Form No. 1B", "Allotment Release Order for Financial Expenses", "182–183", "197–198", "Financial Expenses"),
    allotment_release_form("lbe-form-1c", "LBE Form No. 1C", "Allotment Release Order for Capital Expenditures", "184–185", "199–200", "Capital Expenditures"),
    form("lbe-form-2", "LBE", "LBE Form No. 2", "Augmentation Form", "186", "201", "Move authority-backed savings to augment an existing item under the accepted rules.", "LBO prepares; Accountant certifies; LCE/Vice-LCE approves.", (
        section("Augmentation authority", "required", "FY, LGU, Executive/Sanggunian office, ordinance/general-provision reference.", "Approved augmentation authority and budget calendar.", "No augmentation proceeds without accepted authority.", "Budget and Sanggunian.", "Repeat authority on every page."),
        repeating("Source and use of funds", "From/to object of expenditure, expense class, and amount.", "Posted appropriation/allotment movements.", "Source equals use; savings and same-expense-class rules pass.", "Budget and Accounting.", "Keep source/use rows paired."),
        section("Preparation, certification, and approval", "required", "LBO, Accountant, and approving-authority names, signatures, and dates.", "Wet-signature custody evidence.", "Never imply a digital signature.", "Budget, Accounting, and approving authority.", "Preserve totals and signature space."),
    )),
    form("lbe-form-3", "LBE", "LBE Form No. 3", "Adjusted Receipts Program for Reenacted Appropriations", "187–188", "202–203", "Remove non-recurring prior-year sources from the receipts program for reenactment.", "Treasury, Budget, Accounting, and LCE; confirm locally.", (
        repeating("Adjusted receipt rows", "Income source/classification, preceding-year amount, non-recurring adjustment, and adjusted estimate.", "Posted prior-year receipts and reenactment decisions.", "Adjusted estimate equals preceding amount less adjustment.", "Treasury, Budget, and Accounting.", "Repeat headings and income hierarchy."),
        section("Totals and certification", "required", "Regular-income subtotals, adjusted total, and prepared/certified/approved route.", "Adjusted receipts program and wet-signature evidence.", "All section totals cross-foot.", "Treasury, Budget, Accounting, and LCE.", "Accounting format and signature space."),
    )),
    form("lbe-form-4", "LBE", "LBE Form No. 4", "Reenacted Appropriations of Annual and Supplemental Budgets", "189–190", "204–205", "Identify essential operating appropriations available under reenactment.", "Budget, Accounting, and LCE; confirm locally.", (
        repeating("Department expenditure program", "Department, mandate, vision, mission, outcome, expense class, and object rows.", "Preceding-year appropriation and department profile.", "Every included item has lawful reenactment authority.", "Department and Budget.", "Repeat identity and headings."),
        repeating("Adjustment and adjusted appropriation", "Preceding appropriation, essential-operating adjustment, adjusted appropriation, and certification.", "Reenactment adjustments and authority evidence.", "Adjusted amount equals source plus/minus approved adjustment.", "Budget, Accounting, and LCE.", "Accounting format and signature space."),
    )),
    form("lbe-form-5", "LBE", "LBE Form No. 5", "Summary of Financial and Physical Performance Targets", "191–192", "206–207", "Summarize the cost and physical target for each PPA and MFO.", "Prepared by LPDO/LBO/Treasurer; approved by LCE.", (
        repeating("Summary performance targets", "LGU, department, MFO, PPA, total cost, indicator, prior accomplishment, target, and remarks.", "Approved performance plan and budget.", "Total cost and targets reconcile to the detailed form.", "LPDO, Budget, and Treasury.", "Repeat headings; keep indicators readable."),
        section("Committee preparation and approval", "required", "LPDO, LBO, Treasurer, and LCE names, signatures, and dates.", "Wet-signature custody evidence.", "Never imply a digital signature.", "LFC and LCE.", "Preserve signature space."),
    )),
    form("lbe-form-5a", "LBE", "LBE Form No. 5A", "Detailed Financial and Physical Performance Targets", "193", "208", "Distribute financial allocations and physical targets by quarter.", "Department Head prepares; LCE approves.", (
        repeating("Detailed quarterly targets", "PPA/performance indicator; Q1–Q4 financial allocation; Q1–Q4 physical target.", "Approved performance and allotment plan.", "Quarterly values reconcile to the annual summary.", "Department and Budget.", "Keep quarter headings readable."),
        section("Department preparation and approval", "required", "LGU, department, MFO, Department Head, and LCE signature blocks.", "Wet-signature custody evidence.", "Never imply a digital signature.", "Department Head and LCE.", "Preserve identity and signature space."),
    )),
)


ACCOUNTABILITY_FORMS = (
    form("lbac-form-1", "LBAc", "LBAc Form No. 1", "Quarterly Report of Receipts", "205", "220", "Compare estimated and actual receipts and explain variances each quarter.", "Local Treasurer prepares; Local Accountant certifies.", (
        section("Report identity", "required", "Quarter ending, fiscal year, LGU, and fund.", "Pinned report parameters.", "Quarter agrees with the source ledger.", "Treasury.", "Repeat the report heading."),
        repeating("Estimated receipts", "Income account/title/code and previous/current/to-date estimates.", "Revenue estimates and classifications.", "Estimate roll-forward cross-foots.", "Treasury and Budget.", "Repeat headings."),
        repeating("Actual receipts and variance", "Three monthly actuals, to-date actual, variance amount/percent, and remarks.", "Posted receipt evidence.", "Variance handles zero estimates and reconciles to the ledger.", "Treasury and Accounting.", "Use accounting and percentage formats."),
        section("Preparation and certification", "required", "Treasurer and Accountant names, signatures, dates, and deadline note.", "Wet-signature/submission evidence.", "Never imply a digital signature.", "Treasury and Accounting.", "Preserve signature space."),
    )),
    form("lbac-form-2", "LBAc", "LBAc Form No. 2", "Quarterly Financial Report of Operations", "206–207", "221–222", "Report appropriations, allotments, obligations, and remaining balances by MFO/PPA.", "Certified by LBO.", (
        repeating("Appropriations", "MFO/PPA, implementing unit, continuing/current appropriations, and total.", "Appropriation registry.", "Continuing plus current equals total.", "Budget.", "Repeat headings."),
        repeating("Allotments and balance", "Previous/current/total releases and balance of appropriation.", "Posted allotment movements.", "Appropriation less allotment equals balance.", "Budget.", "Use accounting format."),
        repeating("Obligations and unobligated allotment", "Previous/current/total obligations, unobligated allotment, remarks, and certification.", "Certified obligation registry.", "Allotment less obligations equals unobligated balance.", "Budget.", "Use accounting format and preserve certification."),
    )),
    form("lbac-form-3", "LBAc", "LBAc Form No. 3", "Quarterly Physical Report of Operations", "208", "223", "Compare quarterly target and actual physical performance by PPA/MFO.", "Department/Office Head and LPDO; confirm local route.", (
        repeating("Quarterly targets", "PPA code, MFO, indicator, Q1–Q4 target, and total.", "Accepted performance plan.", "Quarterly targets sum to the total.", "Department and Budget.", "Repeat headings."),
        repeating("Actual performance and variance", "Q1–Q4 actual, total actual, as-of variance, remarks, and preparation blocks.", "Department accomplishment evidence.", "Actual and variance calculations reproduce.", "Department and LPDO.", "Keep remarks and signatures readable."),
    )),
    form("lbac-form-4", "LBAc", "LBAc Form No. 4", "Statement of Receipts and Expenditures", "209–210", "224–225", "Compare annual estimated and actual receipts/expenditures and explain variances.", "Treasurer and LBO prepare; Accountant certifies; LCE approves.", (
        repeating("Receipts", "Particular, account code, estimate, actual, variance amount/percent, and remarks.", "Posted receipts and approved estimates.", "Receipt subtotals and variances reconcile.", "Treasury and Accounting.", "Use accounting/percentage formats."),
        repeating("Expenditures", "Service/expense particular, account code, estimate, actual, variance, and remarks.", "Posted expenditure evidence.", "Expenditure subtotals and variances reconcile.", "Budget and Accounting.", "Repeat headings and amount formats."),
        section("Preparation, certification, and approval", "required", "Treasurer, LBO, Accountant, and LCE names, signatures, and dates.", "Wet-signature custody evidence.", "Never imply a digital signature.", "Budget, Treasury, Accounting, and LCE.", "Preserve signature space."),
    )),
    form("lbac-form-5", "LBAc", "LBAc Form No. 5", "Physical and Financial Performance Evaluation Form", "211", "226", "Evaluate physical accomplishment and financial absorptive capacity by PPA.", "Prepared by Local Finance Committee.", (
        repeating("Physical performance", "PPA code/description/MFO, target, actual, variance, and accomplishment percent.", "Performance target and accomplishment evidence.", "Physical variance and percentage reproduce.", "Department and Budget.", "Repeat headings."),
        repeating("Financial performance", "Allotment, obligations, variance, absorptive capacity, total, and committee preparation.", "Allotment and obligation registers.", "Financial variance and capacity reproduce.", "Local Finance Committee.", "Use accounting/percentage formats and signature space."),
    )),
    form("lbac-form-6", "LBAc", "LBAc Form No. 6", "Monitoring of Physical and Financial Accomplishments", "212–213", "227–228", "Monitor plan-linked physical and financial accomplishment across identified PPAs.", "Department, Budget, Accounting, and plan owners; confirm locally.", (
        repeating("Plan and target identity", "Plan/PPA, AIP reference, office, and AIP/annual-budget target.", "AIP, annual budget, and department records.", "AIP and annual-budget references reconcile.", "Department and Budget.", "Repeat plan headings."),
        repeating("Accomplishment and expenditure", "Actual accomplishment, AIP/annual-budget estimate, actual expenditure, and remarks.", "Accomplishment evidence and posted ledger.", "Amounts and accomplishments tie to retained sources.", "Department, Budget, and Accounting.", "Keep remarks readable."),
    )),
)


DBM_FORM_STARTERS = LBP_FORMS + AUTHORIZATION_REVIEW_FORMS + EXECUTION_FORMS + ACCOUNTABILITY_FORMS
DBM_FORM_STARTERS_BY_KEY = {item["key"]: item for item in DBM_FORM_STARTERS}

if len(DBM_FORM_STARTERS) != 31 or len(DBM_FORM_STARTERS_BY_KEY) != 31:
    raise RuntimeError("The built-in DBM local-form starter catalog must contain 31 unique forms.")
