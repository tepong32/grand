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
        "title": "Prepare and submit a journal entry",
        "summary": "Build a balanced JEV from controlled accounts and responsibility centers, then send it to a different poster.",
        "permission": "accounting.prepare_journal_entries",
        "patterns": ["accounting:entry_*", "accounting:workspace"],
        "order": 60,
        "steps": (
            ("Create the draft", "Choose the open accounting period and fund, record the JEV reference and date, and describe the source transaction clearly.", "A department-scoped draft journal is created.", "The entry date must fall inside the selected open period.", "Open Accounting", "accounting:workspace"),
            ("Add controlled lines", "Add one positive debit or credit per line using active posting accounts and the correct responsibility center.", "The live totals are non-zero and equal.", "Do not use a manual journal to bypass a source-generated voucher or opening route.", "", ""),
            ("Submit for posting", "Review the source evidence and totals, then submit. The draft becomes read-only while under independent review.", "A different poster receives the entry in the posting queue.", "", "", ""),
        ),
    },
    {
        "slug": "finance-journal-post",
        "title": "Review, post, or return a JEV",
        "summary": "Independently review source lineage and balanced lines before they enter the immutable ledger.",
        "permission": "accounting.post_journal_entries",
        "patterns": ["accounting:entry_*", "accounting:workspace"],
        "order": 70,
        "steps": (
            ("Review the submitted entry", "Confirm the period/fund, source reference, description, accounts, centers, line details, and equal debit/credit totals.", "The entry agrees with its supporting evidence and posting rule.", "Posting is an authoritative boundary; do not approve an unexplained mapping.", "Open Accounting", "accounting:workspace"),
            ("Return or post", "Return with a specific reason when correction is needed. Otherwise post once; source-generated voucher handoff then advances recoverably.", "The entry is either editable again by its preparer or immutable in the ledger.", "", "", ""),
            ("Correct after posting properly", "Use a linked reversing or adjusting entry with a mandatory reason rather than changing posted lines.", "The original and correction both remain traceable.", "", "", ""),
        ),
    },
    {
        "slug": "finance-dv-prepare",
        "title": "Prepare and route a disbursement voucher",
        "summary": "Continue the shared Budget–Accounting–Treasury case without re-encoding facts or bypassing wet-signature custody.",
        "permission": "vouchers.prepare_disbursement_voucher",
        "patterns": ["vouchers:*"],
        "order": 80,
        "steps": (
            ("Open your Accounting queue", "Select a case at Accounting preparation and review its Budget classification, obligation support, claimant/payee, and documents.", "The shared case—not a copied transaction—is open.", "Current Voucher Workbench controls remain a shadow/UAT slice until parent roadmap gates pass.", "Open Finance Queue", "vouchers:workspace"),
            ("Prepare the DV", "Use governed setup values, reconcile gross/deductions/net, and complete the applicable document checklist.", "The DV is ready for its controlled print and signature route.", "", "", ""),
            ("Track the physical route", "Record controlled printing, wet-signature rounds, and the required TracePoint custody linkage without representing paper signatures as digital signatures.", "The returned signed packet has traceable version and custody evidence.", "", "", ""),
        ),
    },
    {
        "slug": "finance-configure",
        "title": "Prepare governed Finance setup",
        "summary": "Version master data, rules, signatories, numbering, and templates before transaction users depend on them.",
        "permission": "finance.manage_finance_configuration",
        "patterns": ["finance:*", "accounting:setup*"],
        "order": 10,
        "steps": (
            ("Work in a draft release", "Create or open the correct department and fiscal-year configuration release before changing controlled setup.", "Changes are isolated from active transaction policy.", "", "Open Finance Setup", "finance:workspace"),
            ("Record authority and effectivity", "For each code/rule, enter the authority reference, effective dates, version, and locally confirmed scope.", "The release explains which authority and period it implements.", "An official source still requires applicability confirmation.", "", ""),
            ("Resolve readiness blockers", "Complete required funds/accounts, signatories, numbering, document rules, and accepted templates, then submit for independent approval.", "Readiness has no blocking items and an approver can review the release.", "", "", ""),
        ),
    },
)

BUDGET_GUIDES = (
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
            ("Check authority and evidence", "Confirm the locally required documents and the Budget authority represented by the current pilot allocation controls.", "The case is complete enough for Budget certification.", "The current workbench is not yet the full F3/F4 appropriation/allotment/obligation ledger.", "", ""),
            ("Certify or return", "Certify the supported allocation once, or return the case with a correction reason that the requesting office can act on.", "The shared case advances to Accounting or reopens visibly for correction.", "", "", ""),
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
    counts = {"departments": 0, "guides_created": 0, "guides_preserved": 0}
    definitions = {"accounting": ACCOUNTING_GUIDES, "budget": BUDGET_GUIDES, "treasury": TREASURY_GUIDES}
    for department in Department.objects.all().order_by("pk"):
        kind = _department_kind(department)
        if not kind:
            continue
        counts["departments"] += 1
        for definition in definitions[kind]:
            published = InternalHowTo.objects.filter(
                department=department,
                slug=definition["slug"],
                status=InternalHowTo.PUBLISHED,
            ).first()
            if published:
                counts["guides_preserved"] += 1
                continue
            retired = InternalHowTo.objects.filter(
                department=department,
                slug=definition["slug"],
                status=InternalHowTo.RETIRED,
            ).exists()
            if retired:
                counts["guides_preserved"] += 1
                continue
            guide, created = InternalHowTo.objects.update_or_create(
                department=department,
                slug=definition["slug"],
                version=1,
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
            guide.status = InternalHowTo.PUBLISHED
            guide.full_clean()
            guide.save(update_fields=("status", "updated_at"))
            counts["guides_created"] += 1 if created else 0
    return counts
