# RACI and Standard Operating Procedure

## Roles

| Role | Who | Responsibility |
|---|---|---|
| **Maker** | Correspondence staff | Prepares the batch, reviews quarantine, submits for approval, triggers the dry run and the send |
| **Checker** | Correspondence supervisor | Approves or rejects the batch; cannot approve a batch they submitted |
| **Branch** | Servicing branch | Receives CC of its own customers only; follows up bounced emails |
| **Data owner** | Policy administration | Keeps customer and branch master data correct; fixes data exceptions at source |
| **DPO / Compliance** | Data Protection Officer | Owns the incident playbook; reviews the monthly control report |
| **System** | This pipeline | Runs controls DP-01 to DP-13, locks letters, enforces the workflow, writes the audit trail |

## RACI

R = Responsible, A = Accountable, C = Consulted, I = Informed

| Activity | Maker | Checker | Branch | Data owner | DPO |
|---|---|---|---|---|---|
| Prepare send list and letters | R | A | | C | |
| Run validation and locking | R | A | | | |
| Resolve quarantined items | R | A | C | R (data fixes) | |
| Submit batch | R | I | | | |
| Approve / reject batch | I | R/A | | | |
| Dry run and send | R | A | I | | |
| Follow up bounced emails | I | A | R | C | |
| Monthly control report | R | A | I | I | C |
| Incident response | C | R | C | C | A |

## SOP — monthly correspondence batch

1. **Prepare.** Export the send list from master data (no manual email or CC edits). Generate letters
   using the naming standard `LETTERTYPE_POLICYNO_YYYYMM.pdf` — never include the NIK.
2. **Validate.** Run validation. The system checks every letter and recipient, password-locks the
   letters that pass and copies the rest to quarantine. If the quarantine rate exceeds 20% the batch
   is halted automatically.
3. **Review quarantine (maker).** Resolve each held item at its source (master data, letter
   generation). Held items are never sent from this batch; fixed items go in the next run.
4. **Submit (maker).** Confirm the review and submit. The batch manifest is fingerprinted at this
   moment; any later change requires a new submission.
5. **Approve (checker).** A different person reviews the summary and approves or rejects with a reason.
6. **Dry run (maker).** Send the whole batch to the QA mailbox and spot-check at least 5 emails.
7. **Send (maker).** The system re-checks the sender and the attachment fingerprints, then sends one
   email per customer with only the customer's own branch in CC.
8. **Monitor.** Bounced emails are routed to the branch for follow-up within 2 working days.
9. **Report.** At month end, publish the monthly control report and review it with the DPO.

## Retention

- Working copies (`locked/`, `quarantine/`, `outbox/`) are deleted 30 days after the batch is sent.
- The audit trail and reports are kept; they contain masked personal data only (DP-11).
