from __future__ import annotations

from django.db import transaction

from ..models import Department, InternalHowTo, InternalHowToStep


ACCOUNTING_GUIDES = (
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
        "version": 2,
        "title": "Prepare and submit a journal entry",
        "summary": "Create manual JEVs only for supported events, or materialize a voucher JEV from its pinned posting rule, then send it to a different poster.",
        "permission": "accounting.prepare_journal_entries",
        "patterns": ["accounting:entry_*", "accounting:workspace"],
        "order": 60,
        "steps": (
            ("Choose the correct source route", "For a voucher handoff, review its event, recognition decision, recognition point, and pinned posting-rule title, then use Create GRAND JEV. Use New journal only for a separately supported manual event.", "The selected route preserves the source and policy lineage.", "Do not recreate a voucher or opening-balance JEV manually.", "Open Accounting", "accounting:workspace"),
            ("Create or inspect the draft", "For a manual event, choose the open period and fund and record its reference, date, and source. For a voucher event, let GRAND resolve the pinned account/amount instructions and verify the generated rule checksum.", "A department-scoped draft exists with its source evidence.", "A mapping error must be corrected in governed setup; do not substitute an unexplained account.", "", ""),
            ("Add controlled lines", "Add one positive debit or credit per line using active posting accounts and the correct responsibility center.", "The live totals are non-zero and equal.", "Do not use a manual journal to bypass a source-generated voucher or opening route.", "", ""),
            ("Submit for posting", "Review the source evidence and totals, then submit. The draft becomes read-only while under independent review.", "A different poster receives the entry in the posting queue.", "", "", ""),
        ),
    },
    {
        "slug": "finance-journal-post",
        "version": 2,
        "title": "Review, post, or return a JEV",
        "summary": "Independently review source lineage and balanced lines before they enter the immutable ledger.",
        "permission": "accounting.post_journal_entries",
        "patterns": ["accounting:entry_*", "accounting:workspace"],
        "order": 70,
        "steps": (
            ("Review the submitted entry", "Confirm the period/fund, source reference, description, accounts, centers, line details, and equal debit/credit totals. For a voucher JEV, compare its event, recognition decision, and pinned posting-rule checksum to the handoff.", "The entry agrees with its supporting evidence and immutable posting rule.", "Posting is an authoritative boundary; do not approve an unexplained mapping or a rule used at the wrong recognition point.", "Open Accounting", "accounting:workspace"),
            ("Return or post", "Return with a specific reason when correction is needed. Otherwise post once; source-generated voucher handoff then advances recoverably.", "The entry is either editable again by its preparer or immutable in the ledger.", "", "", ""),
            ("Correct after posting properly", "Use a linked reversing or adjusting entry with a mandatory reason rather than changing posted lines.", "The original and correction both remain traceable.", "", "", ""),
        ),
    },
    {
        "slug": "finance-dv-prepare",
        "version": 4,
        "title": "Prepare and route a disbursement voucher",
        "summary": "Continue the shared Budget–Accounting–Treasury case without re-encoding facts or bypassing wet-signature custody.",
        "permission": "vouchers.prepare_disbursement_voucher",
        "patterns": ["vouchers:*"],
        "order": 80,
        "steps": (
            ("Open your Accounting queue", "Select a case at Accounting preparation and review its claim-to-allocation control, relationship types, recognition/adjustment decision, Budget classification, claimant/payee, and documents.", "The shared case—not a copied transaction—is open with zero relationship difference.", "Current Voucher Workbench controls remain a controlled UAT slice until parent roadmap gates pass.", "Open Finance Queue", "vouchers:workspace"),
            ("Return before DV when relationships need correction", "If the claim, obligation allocation, or snapshot is wrong, return the same case to requesting-office payable preparation with a specific reason before creating a DV.", "The governed pre-DV modification window reopens without losing prior review history.", "After a DV exists, use the coordinated voucher/payment correction route instead.", "", ""),
            ("Prepare the DV", "Use governed setup values, reconcile gross/deductions/net, complete the applicable document checklist, and confirm the pinned template's form status and local comparison evidence.", "The DV is ready for its controlled print and signature route.", "A starter or pilot workbook is editable and preflighted, but it is not automatically a locally accepted official form.", "", ""),
            ("Prepare one signing file", "At the controlled signing-copy card, choose Prepare print-ready file. Download only the current version and compare its visible layout, paper size, names, totals, and signature labels before printing.", "GRAND pins the output checksum and automatically retains the same bytes and manifest in the TraceSync-ready export folder.", "Do not alter the generated signing file. Correct the governed source/template and create a reasoned replacement instead.", "", ""),
            ("Record what was actually printed", "Enter the number of copies and the printer, paper stock, tray, duplex, or margin setting actually used. Add a short alignment or quality note when useful.", "The current print version carries immutable operator, time, copy, and printer evidence.", "Do not claim that a file was printed until the physical copies were checked.", "", ""),
            ("Assemble the physical packet", "Count the documents and pages, describe the assembly, and create the linked TracePoint packet. GRAND builds the configured office/signatory checkpoints without copying voucher amounts into TracePoint.", "The exact signing version is linked to one custody item and its receiving route.", "The TracePoint record proves custody events; it does not replace the paper signatures or Finance record.", "", ""),
            ("Replace bad copies safely", "If the current copies are damaged, misaligned, or wrong, enter a specific replacement reason. Mark every earlier physical copy DO NOT SIGN, prepare the successor version, then repeat print recording and packet assembly.", "The earlier output and signing round are superseded while their evidence remains visible.", "Never reuse or silently discard a superseded signing copy.", "", ""),
            ("Record each returned signature", "After the linked packet returns, select the signer task and record the actual returned wet signature with a useful note. Repeat only for the current print version and signature round.", "When all current tasks are returned, the packet is marked returned and the case advances to Accounting validation.", "Do not record a digital approval or a signature expected later as if the paper were already returned.", "", ""),
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
        "version": 3,
        "title": "Prepare governed Finance setup",
        "summary": "Version master data, rules, signatories, numbering, and templates before transaction users depend on them.",
        "permission": "finance.manage_finance_configuration",
        "patterns": ["finance:*", "accounting:setup*"],
        "order": 10,
        "steps": (
            ("Work in a draft release", "Create or open the correct department and fiscal-year configuration release before changing controlled setup.", "Changes are isolated from active transaction policy.", "", "Open Finance Setup", "finance:workspace"),
            ("Define transaction variants and evidence", "Add each locally enabled transaction variant, then add its ordered required or conditional documentary rules. State the exact applicability condition and whether reviewed authority permits a waiver.", "Every enabled payable route has a typed, reviewable checklist before release activation.", "Do not infer local applicability or form acceptance from a public COA/DBM source alone.", "", ""),
            ("Describe each accounting event", "For recognition, liquidation, payment, remittance, or another enabled event, choose its exact recognition point and add ordered debit/credit instructions. Start from the editable recognition recipe when useful, then replace its warning with the locally reviewed authority and wording.", "Each transaction variant has a human-readable rule that produces a balanced JEV.", "A generated starter is not accepted policy and blocks submission until its authority note is replaced.", "", ""),
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
        "slug": "finance-treasury-payment",
        "title": "Prepare, advise, and release a payment instrument",
        "summary": "Issue and release checks only through the shared case, with cancellation/replacement history and advice controls intact.",
        "permission": "vouchers.issue_payment_instruments",
        "patterns": ["vouchers:*"],
        "order": 20,
        "steps": (
            ("Confirm payment readiness", "Open a case in Treasury check preparation and verify its posted Accounting handoff, net amount, payee, payment account, and cash/payment prerequisites.", "The case is authorized for instrument preparation under the enabled pilot route.", "Never issue from an unposted or mismatched case.", "Open Finance Queue", "vouchers:workspace"),
            ("Register the physical check", "Record the controlled check number, amount, account, preparer, and issue evidence. Issued numbers are never silently reused.", "The case carries a traceable payment instrument.", "Issuance closes the convenience modification window for voucher fields.", "", ""),
            ("Handle exceptions visibly", "For spoilage or error, cancel with a reason and create a linked replacement; do not edit the issued instrument.", "The cancelled and replacement instruments remain in one history.", "", "", ""),
            ("Release only after advice", "After the applicable accountant/bank advice is finalized, record actual release and acknowledgement to the authorized recipient.", "The case completes with advice and release evidence.", "", "", ""),
        ),
    },
)


def _department_kind(department):
    identity = f"{department.slug or ''} {department.name or ''}".lower()
    if "account" in identity or "acctg" in identity or "finance" in identity:
        return "accounting"
    if "budget" in identity:
        return "budget"
    if "treasur" in identity:
        return "treasury"
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
