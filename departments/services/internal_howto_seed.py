from __future__ import annotations

from django.db import transaction

from ..models import Department, InternalHowTo, InternalHowToStep


ACCOUNTING_GUIDES = (
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
        "version": 1,
        "title": "Prepare a monthly bank reconciliation",
        "summary": "Stage the bank statement, match posted journals, document timing items, and submit only a zero-difference adjusted-balance schedule.",
        "permission": "accounting.prepare_bank_reconciliation",
        "patterns": ["accounting:bank_reconciliation_*"],
        "order": 50,
        "steps": (
            ("Create the monthly control", "Choose one mapped bank account and fund, enter the statement period/receipt date, and copy the independently checked opening, closing, row, deposit, and withdrawal controls.", "A draft identifies one bank account, one fund, and one monthly statement.", "Use the bank-account code adopted in Finance Setup; do not enter a replacement COA account.", "Open Bank Reconciliation", "accounting:bank_reconciliation_workspace"),
            ("Stage the bank CSV", "Upload the UTF-8 starter CSV. GRAND checks each date, one-sided amount, optional running balance, declared totals, closing equation, and SHA-256 source checksum.", "The statement becomes Validated only when every source control agrees.", "Before submission you may restage a corrected source, but must explain the replacement; prior versions remain retained.", "Open Bank Reconciliation", "accounting:bank_reconciliation_workspace"),
            ("Match only posted book evidence", "Run unique exact matching, then review remaining same-amount candidates manually against bank references, checks, transfers, and posted JEVs.", "Every bank row points to one posted bank-account journal line with the same amount and direction.", "A bank charge, credit memo, or book error with no posted line requires an authorized JEV or correction before the BRS can close.", "Open Accounting", "accounting:workspace"),
            ("Explain ledger-only timing items", "For each posted bank line absent from the statement, record the check/deposit evidence, reason, and expected clearance date.", "Deposits in transit and outstanding checks are explicit and feed the adjusted-balance calculation.", "Classification is not an adjustment and does not hide an unexplained difference.", "", ""),
            ("Reach zero and submit", "Confirm adjusted bank balance equals the posted GL book balance, every statement row is matched, and every ledger-only line is classified; then submit to a different reviewer.", "The BRS is read-only under independent review with a checksum-backed snapshot.", "Do not force agreement with a balancing line or approve your own preparation.", "", ""),
            ("Export portable evidence", "After review, export the controlled CSV when needed. GRAND archives the same bytes and manifest inside the department/user/category TraceSync-ready folder tree.", "The statement, matches, timing items, control totals, and checksums remain portable.", "Use the locally accepted signed BRS template for official submission until its exact layout is confirmed and configured.", "", ""),
        ),
    },
    {
        "slug": "finance-bank-reconciliation-review",
        "version": 1,
        "title": "Review a bank reconciliation independently",
        "summary": "Review the statement, posted GL, reconciling items, and adjusted-balance result before closing the monthly control.",
        "permission": "accounting.approve_bank_reconciliation",
        "patterns": ["accounting:bank_reconciliation_*"],
        "order": 51,
        "steps": (
            ("Confirm independent assignment", "Verify that you did not create or submit this reconciliation and that the bank account, fund, period, and department are correct.", "The maker/checker separation is clear.", "Do not review through the preparer's account.", "Open Bank Reconciliation", "accounting:bank_reconciliation_workspace"),
            ("Compare statement and matches", "Review the checksummed current statement version and trace every bank row to its posted JEV, payment, remittance, deposit, debit memo, or credit memo evidence.", "No statement-only transaction remains unrecognized in the books.", "GRAND's exact checks do not replace review of the bank's source document.", "", ""),
            ("Review timing items and equation", "Check each outstanding check or deposit in transit against its evidence and expected clearance date, then confirm adjusted bank and GL book balances are equal.", "The unexplained difference is exactly zero.", "Bank charges, credits, and book errors normally require a JEV, not timing-item classification.", "", ""),
            ("Approve or return", "Record the signed BRS, GL comparison, bank statement, and supporting-schedule reference when approving; otherwise return a specific correction instruction.", "Approval creates an immutable reconciliation checksum; return reopens the reasoned correction window.", "Official submission copies and deadlines remain subject to locally accepted COA/LGU practice.", "", ""),
        ),
    },
    {
        "slug": "finance-remittance-accounting",
        "version": 1,
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
        "version": 4,
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
        "version": 1,
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
