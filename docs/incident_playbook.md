# Incident Playbook — Misdirected Customer Correspondence

Use when a letter or email containing personal data reached someone other than the intended
customer or their servicing branch.

## First hour — contain

1. **Stop the batch.** Set the batch to HALTED (kill switch) so nothing else is sent.
2. **Identify scope** from the audit trail: batch, policy numbers, recipients, time sent.
3. **Request deletion** from the unintended recipient in writing and ask for confirmation.
4. **Preserve evidence**: keep the `.eml`, the manifest, the state history and the audit log.

## Within 24 hours — assess and escalate

5. **Notify the DPO / Compliance** with the scope and the data involved (NIK, policy data, amounts).
6. **Assess the risk to the customer**: was the attachment opened? (It is password-locked, which
   lowers the likelihood of exposure, but does not remove the obligation to assess.)
7. **Decide on notification** together with the DPO.

## Within 3 × 24 hours — notify

8. Under **UU PDP (Law No. 27 of 2022), Article 46**, a failure of personal data protection must be
   notified in writing to the affected data subject and to the supervising institution no later than
   3 × 24 hours. The notification states what data was exposed, when and how, and the steps taken.

## Afterwards — fix the root cause

9. **Root cause analysis**: which control failed or was bypassed, and why.
10. **Add or strengthen a control** and a test case that reproduces the incident.
11. **Report** the incident and its fix in the next monthly control report.

| Step | Owner | Deadline |
|---|---|---|
| Stop batch, identify scope | Maker + Checker | 1 hour |
| Request deletion | Checker | 1 hour |
| Escalate to DPO | Checker | 24 hours |
| Notify customer and supervising institution | DPO | 3 × 24 hours |
| Root cause and new control | Process Improvement | 10 working days |
