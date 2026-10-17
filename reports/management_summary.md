# Customer Correspondence - Monthly Control Report

Period: 2026-08 to 2026-10 (synthetic data)

## Headline

- 450 customers in scope; 411 letters sent, 39 held before sending.
- Unsafe emails sent: **0**. Cross-branch exposures: **0**.
- Control test: 42 of 42 injected defects caught; 0 reached a customer.
- 7 bounced emails routed to branches for follow-up.

## Most frequent exceptions

- DP-06 Customer email matches master data and has no domain typo: 7 documents held
- DP-07 Branch CC resolved from branch master and allowlisted: 6 documents held
- DP-03 File name points to exactly one policy: 6 documents held

## Batch detail

| Batch | Customers | Sent | Held | Quarantine rate | Maker | Checker |
|---|---|---|---|---|---|---|
| 2026-08 | 150 | 138 | 12 | 8.0% | dina.maker | sari.supervisor |
| 2026-09 | 150 | 136 | 14 | 9.3% | rizky.maker | budi.supervisor |
| 2026-10 | 150 | 137 | 13 | 8.7% | dina.maker | sari.supervisor |

## Recommendations

1. Fix email data at source: send-list emails that differ from master data are the top recipient risk; refresh the send list directly from master data instead of manual edits.
2. Remove the manual CC column from the send-list template; branch mailboxes are resolved from branch master data only.
3. Enforce the file-naming standard (letter type + policy number + period, no NIK) at the letter-generation step to remove DP-03 and DP-10 exceptions at the root.
