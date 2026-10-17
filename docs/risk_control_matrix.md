# Risk & Control Matrix — Customer Correspondence by Email

Scope: monthly customer letters (maturity, benefit payment, reinstatement) sent by email to the
policyholder with the servicing branch in CC. Letters contain personal data, including the NIK.

Rating: Likelihood (L) and Impact (I) on 1–5; inherent risk = L × I, before controls.

| Risk ID | Risk | L | I | Inherent | Control | Type | Automation | Evidence |
|---|---|---|---|---|---|---|---|---|
| R1 | A customer receives another customer's letter (files swapped or mis-generated) | 3 | 5 | 15 | **DP-04** policy, name and NIK in the letter must match the recipient | Preventive | Automated | `validation.csv`, audit log |
| R2 | Letter reaches the wrong person because the send-list email is stale or mistyped | 4 | 5 | 20 | **DP-06** send-list email must equal master data; domain typo check | Preventive | Automated | `validation.csv` |
| R3 | Branch receives data of a customer it does not service | 3 | 4 | 12 | **DP-07** CC resolved from branch master by the customer's master branch; manual CC rejected; allowlisted domain only | Preventive | Automated | `validation.csv`, leakage matrix |
| R4 | Several customers' data exposed in one email (multi-recipient, BCC) | 2 | 5 | 10 | **DP-08** one email = one customer + own branch; recipients field must be a single address | Preventive | Automated | Outbox verification |
| R5 | Customer not informed (letter missing) — regulatory and service risk | 3 | 3 | 9 | **DP-01** every customer on the send list has a letter | Detective | Automated | Quarantine register |
| R6 | Customer receives two different versions | 2 | 3 | 6 | **DP-02** no duplicate letters | Preventive | Automated | Quarantine register |
| R7 | Automated matching picks the wrong file | 2 | 5 | 10 | **DP-03** file name must point to exactly one policy; all referenced customers held | Preventive | Automated | Quarantine register |
| R8 | A letter without an owner on the list is sent by mistake | 2 | 5 | 10 | **DP-05** orphan letters held, never sent | Preventive | Automated | Quarantine register |
| R9 | Email is intercepted or forwarded and the NIK is read | 3 | 4 | 12 | **DP-09** letters with NIK are AES-256 password-locked (customer's date of birth) and verified | Preventive | Automated | Lock verification in audit log |
| R10 | NIK exposed outside the protected attachment | 2 | 4 | 8 | **DP-10** no NIK in file name, subject or body | Preventive | Automated | `validation.csv`, outbox verification |
| R11 | Logs and reports become a secondary source of leakage | 3 | 3 | 9 | **DP-11** masked data only; every run scans logs and reports for raw NIK, email and DOB | Detective | Automated | `reports/dp11_pii_scan.json` |
| R12 | Email sent from a personal or wrong mailbox; credentials leaked in code | 2 | 4 | 8 | **DP-12** official mailbox only; SMTP credentials from environment variables only | Preventive | Automated | Sender check in audit log |
| R13 | File altered after approval (error or tampering) | 1 | 5 | 5 | **DP-13** SHA-256 of each attachment compared with the approved manifest, before the batch and before each email; any mismatch halts the batch | Preventive | Automated | Audit log, state history |
| R14 | One person prepares and releases a batch without review | 3 | 4 | 12 | **Maker-checker**: maker submits, a different checker approves; manifest hash locked at submission | Preventive | System-enforced | State history, approval trail |
| R15 | A systemic error goes out at scale | 2 | 5 | 10 | **Kill switch**: halt if quarantine rate > 20%, any integrity failure, or 3 consecutive transport errors; dry run to QA mailbox first | Preventive | Automated | State history |
| R16 | Bounced emails are not followed up | 3 | 2 | 6 | **Delivery monitoring**: bounces routed to the branch for follow-up | Detective | Semi-automated | Bounce follow-up sheet |

## Control testing

Every batch is tested against deliberately injected defects (`data/ground_truth_defects.csv`).
Result across Aug–Oct 2026 (synthetic): **44 of 44 defects caught, 0 reached a customer, 0 false positives**.
The outbox is then re-verified independently (`reporting.verify_outbox`): each attachment must open with
the *To* recipient's own password and contain only that recipient's data.
