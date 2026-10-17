# Process Redesign: As-Is vs To-Be

## As-Is — manual

```mermaid
flowchart LR
    A[Export customer list] --> B[Match each PDF to a row by eye]
    B --> C[Type or copy customer email]
    C --> D[Type branch email in CC]
    D --> E[Attach PDF manually]
    E --> F[Send one by one]
    B -. risk: wrong file .-> X((Data leak))
    C -. risk: old or mistyped email .-> X
    D -. risk: wrong branch .-> X
    E -. risk: unprotected NIK .-> X
    F -. no record of who sent what .-> Y((No audit trail))
```

Pain points
- Every letter is handled by hand: matching, addressing, attaching, sending.
- Each manual step is a chance for a customer's NIK to reach the wrong person.
- No independent review before sending and no reliable record afterwards.

## To-Be — automated, controlled, governed

```mermaid
flowchart LR
    A[Send list from master data] --> B[Validate 13 controls]
    B -->|fail| Q[Quarantine - never sent]
    B -->|pass| L[Password-lock letter]
    L --> M[Maker reviews and submits]
    M --> C[Checker approves]
    C --> D[Dry run to QA mailbox]
    D --> S[Send: 1 email per customer, CC own branch]
    S --> V[Re-verify outbox + delivery monitoring]
    V --> R[Audit trail + monthly control report]
```

| | As-Is | To-Be |
|---|---|---|
| Effort per 150-letter batch | ~10 hours (assumption: 4 min per letter) | ~20 minutes (measured ~12 s processing + assumed 20 min review & approval) |
| Wrong-recipient protection | Staff attention | 13 automated controls + independent outbox verification |
| NIK protection | None | Password-locked attachment, NIK never in name/subject/body |
| Review before sending | Ad hoc | Mandatory maker-checker, system-enforced |
| Evidence | None | Audit trail, quarantine register, monthly report |

The As-Is time and the To-Be review time are **assumptions** for this simulation
(`config/settings.json`); replace them with a time study from the real process.
