"""Pre-send validation controls DP-01 .. DP-08 and DP-10.

DP-09, DP-12 and DP-13 run at lock/send time (see pipeline.py and mailer.py);
DP-11 is verified over every output file (see reporting.scan_outputs_for_pii).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from . import CONTROL_NAMES, settings
from .letters import extract_text, read_fields
from .pii import (
    domain_typo,
    find_nik_like,
    is_single_valid_email,
    mask_email,
    mask_nik,
    policy_candidates,
    redact_niks,
)


@dataclass
class Finding:
    control_id: str
    detail: str

    @property
    def severity(self) -> str:
        return settings()["severity"][self.control_id]


@dataclass
class RowResult:
    policy_no: str
    letter_type: str
    branch_code_master: str | None
    to_email: str | None
    cc_email: str | None
    letter_file: str | None
    findings: list[Finding] = field(default_factory=list)

    @property
    def status(self) -> str:
        return "READY" if not self.findings else "QUARANTINE"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory_letters(letter_dir: Path, send_policies: set[str]) -> pd.DataFrame:
    rows = []
    for p in sorted(letter_dir.glob("*.pdf")):
        cands = policy_candidates(p.stem)
        matched = sorted(set(cands) & send_policies)
        rows.append({
            "file": p.name,
            "path": str(p),
            "candidates": cands,
            "matched": matched,
            "sha256": sha256(p),
        })
    return pd.DataFrame(rows)


def validate_batch(send_list: pd.DataFrame, customers: pd.DataFrame,
                   branches: pd.DataFrame, letter_dir: Path) -> tuple[list[RowResult], list[dict]]:
    """Returns per-customer results and a list of orphan letters (DP-05)."""
    cfg = settings()
    allow_domain = cfg["branch_email_allowlist_domain"].lower()
    master = customers.set_index("policy_no")
    branch_email = branches.set_index("branch_code")["branch_email"].to_dict()
    send_policies = set(send_list["policy_no"])

    inv = inventory_letters(letter_dir, send_policies)
    by_policy: dict[str, list[dict]] = {p: [] for p in send_policies}
    ambiguous_refs: dict[str, list[str]] = {}
    orphans: list[dict] = []
    for _, doc in inv.iterrows():
        if len(doc["matched"]) == 1:
            by_policy[doc["matched"][0]].append(doc.to_dict())
        elif len(doc["matched"]) > 1:
            for pol in doc["matched"]:
                ambiguous_refs.setdefault(pol, []).append(doc["file"])
        else:
            orphans.append({
                "file": doc["file"],
                "policy_no": doc["candidates"][0] if doc["candidates"] else None,
                "control_id": "DP-05",
                "detail": "Letter has no owner on this send list - held, never sent",
            })

    results: list[RowResult] = []
    for _, row in send_list.iterrows():
        pol = row["policy_no"]
        cust = master.loc[pol] if pol in master.index else None
        res = RowResult(
            policy_no=pol,
            letter_type=row["letter_type"],
            branch_code_master=None if cust is None else cust["branch_code"],
            to_email=None,
            cc_email=None,
            letter_file=None,
        )
        f = res.findings
        if cust is None:
            f.append(Finding("DP-06", "Policy not found in customer master"))
            results.append(res)
            continue

        # --- DP-01 / DP-02 / DP-03: exactly one unambiguous letter
        docs = by_policy.get(pol, [])
        if pol in ambiguous_refs:
            f.append(Finding("DP-03", f"Referenced by ambiguous file name(s): {', '.join(ambiguous_refs[pol])}"))
        if not docs and pol not in ambiguous_refs:
            f.append(Finding("DP-01", "No letter found for this customer"))
        if len(docs) > 1:
            f.append(Finding("DP-02", f"{len(docs)} letters found: {', '.join(d['file'] for d in docs)}"))

        # --- DP-04 / DP-10 on the letter itself
        if len(docs) == 1:
            doc = docs[0]
            res.letter_file = doc["file"]
            fields = read_fields(extract_text(Path(doc["path"])))
            if fields["policy_no"] != pol:
                f.append(Finding("DP-04", f"Letter shows policy {fields['policy_no']} instead of {pol}"))
            if (fields["name"] or "").strip().upper() != str(cust["name"]).strip().upper():
                f.append(Finding("DP-04", "Policyholder name in letter does not match recipient"))
            if fields["nik"] != cust["nik"]:
                shown = mask_nik(fields["nik"]) if fields["nik"] else "none"  # already masked; masking again is a no-op
                f.append(Finding("DP-04", f"NIK in letter ({shown}) does not belong to recipient"))
            if find_nik_like(doc["file"]):
                f.append(Finding("DP-10", "File name contains a NIK"))

        # --- DP-08 / DP-06: exactly one valid recipient, equal to master
        raw_email = str(row["email"]).strip()
        if not is_single_valid_email(raw_email):
            f.append(Finding("DP-08", "Email field holds more than one / an invalid address"))
        else:
            if raw_email.lower() != str(cust["email"]).lower():
                f.append(Finding("DP-06", f"Send-list email {mask_email(raw_email)} differs from master "
                                          f"{mask_email(cust['email'])}"))
            suggestion = domain_typo(raw_email)
            if suggestion:
                f.append(Finding("DP-06", f"Email domain looks like a typo of {suggestion}"))
            res.to_email = cust["email"]

        # --- DP-07: branch CC always resolved from branch master by the customer's master branch
        if str(row["branch_code"]) != cust["branch_code"]:
            f.append(Finding("DP-07", f"Send-list branch {row['branch_code']} differs from master "
                                      f"branch {cust['branch_code']}"))
        resolved_cc = branch_email.get(cust["branch_code"])
        override = str(row.get("cc_override") or "").strip()
        if override and override.lower() != str(resolved_cc).lower():
            f.append(Finding("DP-07", f"Manual CC {mask_email(override)} is not the customer's branch mailbox"))
        if not resolved_cc or not resolved_cc.lower().endswith("@" + allow_domain):
            f.append(Finding("DP-07", "Branch mailbox missing or outside the allowlisted domain"))
        res.cc_email = resolved_cc

        results.append(res)
    return results, orphans


def results_frame(results: list[RowResult], orphans: list[dict]) -> pd.DataFrame:
    """Flat, masked view: one row per finding (or one READY row per customer)."""
    rows = []
    for r in results:
        base = {
            "policy_no": r.policy_no,
            "letter_type": r.letter_type,
            "branch_code": r.branch_code_master,
            "to_email_masked": mask_email(r.to_email) if r.to_email else "",
            "cc_email": r.cc_email or "",
            "letter_file": redact_niks(r.letter_file or ""),
            "status": r.status,
        }
        if not r.findings:
            rows.append({**base, "control_id": "", "control": "", "severity": "", "detail": ""})
        for fd in r.findings:
            rows.append({**base, "control_id": fd.control_id, "control": CONTROL_NAMES[fd.control_id],
                         "severity": fd.severity, "detail": redact_niks(fd.detail)})
    for o in orphans:
        rows.append({
            "policy_no": o["policy_no"], "letter_type": "", "branch_code": "", "to_email_masked": "",
            "cc_email": "", "letter_file": redact_niks(o["file"]), "status": "QUARANTINE",
            "control_id": "DP-05", "control": CONTROL_NAMES["DP-05"],
            "severity": settings()["severity"]["DP-05"], "detail": o["detail"],
        })
    return pd.DataFrame(rows)
