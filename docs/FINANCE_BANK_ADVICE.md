# Finance bank advice and returned instruments

Status: **F8.4 implemented synthetic control; exact local bank-advice form, submission practice, accounting treatment, and named-office acceptance remain required**.

## What GRAND now controls

F8.4 replaces the former single-case “finalized advice” flag with a retained, multi-case control:

- one advice version groups issued instruments for one bank account and one pinned Finance Setup release;
- every item retains the case, instrument UUID, check number, fund, amount, issue time, total, and snapshot checksum;
- Accounting prepares and independently reviews the version;
- Treasury records actual bank submission and its retained evidence;
- Accounting records the bank's acknowledgement or documented return; and
- Treasury release remains blocked until every active check in the case points to a current acknowledged version.

Internal approval, external submission, and bank acknowledgement are deliberately different states. Printing or exporting a schedule does not advance a voucher case.

## Familiar lifecycle and modification allowance

The lifecycle is:

```text
Draft -> For review -> Approved -> Submitted -> Acknowledged
                   \-> Review returned -> reasoned successor
                                      Submitted -> Bank returned -> reasoned successor
```

Before submission for review, the preparer may correct the draft. Once another person has reviewed it, GRAND never silently overwrites the retained version. A review- or bank-returned version is corrected through a successor with a required reason. The successor:

- retains the same bank account and Finance Setup release;
- may use only instruments already present in the returned version;
- may omit an instrument when the correction requires it;
- cannot import an unrelated check; and
- leaves the earlier items, decision, reason, checksum, actor, and event history visible.

After acknowledgement, the submitted snapshot is immutable. Check particulars are never edited in place after issue; pre-release errors use cancellation/replacement, while a returned released check uses the governed returned-instrument route below.

## Returned released instrument route

Treasury first classifies a released check as returned under an active cash policy and records the bank evidence. GRAND then reopens the completed shared case at **Accounting returned-instrument review** and pins:

- the original instrument and acknowledged advice;
- Treasury's exception and evidence;
- claimant release evidence; and
- the original payment posting request and JEV/no-entry decision.

Accounting may ask Treasury for a clarification, which creates a retained successor review. Accounting then records either **Reissue** or **Close without reissue**, the reviewed authority, and the decision basis.

The active Finance Setup payment-event rule governs the ledger step. The editable starter uses a `REVERSAL` at `PAYMENT_RETURN`: debit the mapped bank/cash account and credit the payable, reversing the original payment-release entry. If the locally approved rule says no entry is needed, GRAND retains that explicit decision instead. It never edits or deletes the original posted JEV.

Only after the reversal is posted or the governed no-entry decision completes does the case return to the exact Treasury stage. A replacement check is allowed only for a completed **Reissue** decision; creating it closes the returned review and its cash exception while retaining the old check.

## Roles, workspaces, and guidance

- **Accounting DV Preparer** prepares advice versions and submits them for review.
- **Accounting Reviewer** approves/returns advice, records the bank response, and decides returned released instruments.
- **Treasury Disbursement Officer** submits approved advice to the bank, releases only acknowledged checks, supplies returned-item clarification, and creates an authorized replacement.
- **Finance UAT Viewer** has read-only visibility.

The conservative Bank Advice workspace shows current and historical versions, instrument/case links, totals, evidence, state events, and open returned-item reviews. The existing floating `?` window supplies department- and permission-specific steps without taking the user away from the current page. Tutorial checkmarks remain private learning progress; they do not approve work, measure performance, or transfer to another employee.

## Editable starter and portable export

`docs/finance-starters/BANK_ADVICE_STARTER.csv` is a plain, macro-free discussion starter. The live download adds rows for the user's Finance Setup bank accounts where available. Both keep authority, local-applicability, submission, and response references visible so staff can adapt familiar practice without treating the starter as an approved official form.

Authorized exports include the advice version, item snapshots, totals, checksum, review/submission/response evidence, successor lineage, and event history. Formula-like CSV values are neutralized. The same bytes and a SHA-256 manifest are retained under:

```text
GRAND_EXPORT_ROOT/<department>/<user>/finance-bank-advice/<year>/<month>/
```

Copy or synchronize the complete export root with TraceSync so artifacts remain beside their manifests. The archive supports safekeeping; it does not replace database backups, Records retention, access control, or an accepted official signed copy.

## Public guidance and local boundary

The COA Government Accounting Manual for National Government Agencies defines cancelled, outstanding, and returned checks and treats bank reconciliation as settlement of book/bank differences ([GAM Chapter 21 definitions](https://coa.gov.ph/wp-content/uploads/abc-help/gam_b/br1.1.htm)). It describes preparation of the Report of Checks Issued and related daily reporting to Accounting ([GAM Chapter 21 method](https://coa.gov.ph/wp-content/uploads/abc-help/gam_b/br1.2.htm)) and chronological recording of released, unreleased, and cancelled checks with actual release dates ([GAM Chapter 6 disbursements](https://www.coa.gov.ph/wp-content/uploads/ABC-Help/GAM_A/g5.htm)). COA also identifies JEVs and bank/check reports as sources for financial reporting ([GAM financial-report source records](https://coa.gov.ph/wp-content/uploads/abc-help/gam_b/fr1.30.htm)).

DBM's Citizen's Charter identifies bank submission of the Advice of Checks Issued and Cancelled as a concrete external handoff in DBM practice ([DBM Citizen's Charter, 2022](https://www.dbm.gov.ph/wp-content/uploads/AboutDBM/Updated-DBM-Charter-as-of-March-2022_FINAL.pdf)). DBM's PFM reform roadmap also supports movement toward digital payment and advice mechanisms ([PFM Reforms Roadmap 2024–2028](https://www.dbm.gov.ph/wp-content/uploads/DBM%20Publications/PFM-Reforms/PFM_roadmap-110624.pdf)).

These sources support retained issue/cancellation registers, bank transmission evidence, acknowledgement gates, reconciliation evidence, and governed JEV treatment. They do **not** prove that an NGA form, deadline, signatory, copy count, bank channel, or accounting entry automatically applies to this LGU. GRAND therefore requires a local-applicability note and preserves unresolved form acceptance as an explicit rollout gate.

## Acceptance and replay still required

Official rollout still requires:

- the exact locally accepted advice/ACIC or successor template, bank channel, copies, signatories, deadlines, and acknowledgement evidence;
- confirmed Accounting/Treasury ownership and segregation for preparation, review, transmission, response recording, release, and returned-item decisions;
- locally approved entries or no-entry decisions for rejection, return, cancellation, replacement, stale, unreleased, and year-end cases;
- prior-period outstanding-item carry-forward into reconciliation and reporting;
- redacted replay from check issue through advice, bank acknowledgement or return, claimant release, payment JEV, returned-item reversal/reissue, bank reconciliation, and export; and
- named Treasury, Accounting, Budget, bank, local audit/COA, Records, IT/security, and approving-authority acceptance.

Passing software tests proves the synthetic controls behave as designed; it is not authorization for official production use.
