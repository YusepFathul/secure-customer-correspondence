"""Batch workflow: validate -> lock -> maker submit -> checker approve -> send -> monitor.

State is kept on disk per batch, so every step can be run from the CLI or the
Streamlit app and is fully reproducible.
"""

from __future__ import annotations

import json
import os
import secrets
import shutil
import time
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pymupdf

from . import DATA_DIR, OUTPUT_DIR, audit, settings
from .controls import results_frame, sha256, validate_batch
from .letters import extract_text, read_fields
from .mailer import (
    OutboxTransport,
    SMTPTransport,
    build_branch_notice,
    build_customer_email,
    check_sender,
    content_has_nik,
)
from .pii import mask_email


class WorkflowError(RuntimeError):
    pass


class SegregationOfDutiesError(WorkflowError):
    pass


# ---------------------------------------------------------------- paths & state
def batch_dir(batch_id: str) -> Path:
    return OUTPUT_DIR / batch_id


def list_batches() -> list[str]:
    root = DATA_DIR / "batches"
    return sorted(p.name for p in root.iterdir() if p.is_dir()) if root.exists() else []


def load_state(batch_id: str) -> dict:
    p = batch_dir(batch_id) / "state.json"
    if p.exists():
        return json.loads(p.read_text())
    return {"batch_id": batch_id, "status": "NEW", "history": []}


def _save_state(state: dict) -> None:
    d = batch_dir(state["batch_id"])
    d.mkdir(parents=True, exist_ok=True)
    (d / "state.json").write_text(json.dumps(state, indent=2))


def _transition(state: dict, status: str, actor: str, note: str = "") -> None:
    state["status"] = status
    state["history"].append({
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": status, "actor": actor, "note": note,
    })
    _save_state(state)
    audit.log(state["batch_id"], actor, f"STATE_{status}", "OK", note)


def load_inputs(batch_id: str):
    customers = pd.read_csv(DATA_DIR / "customers_master.csv", dtype=str)
    branches = pd.read_csv(DATA_DIR / "branches_master.csv", dtype=str)
    send = pd.read_excel(DATA_DIR / "batches" / batch_id / "send_list.xlsx", dtype=str).fillna("")
    return send, customers, branches


def _role(user: str) -> str | None:
    users = settings()["users"]
    if user in users["makers"]:
        return "maker"
    if user in users["checkers"]:
        return "checker"
    return None


# ---------------------------------------------------------------- step 1-2: validate + lock
def _dob_password(dob_iso: str) -> str:
    return date.fromisoformat(dob_iso).strftime("%d%m%Y")


def _lock_pdf(src: Path, dst: Path, user_pw: str) -> None:
    owner_pw = os.environ.get(settings()["owner_password_env"]) or secrets.token_urlsafe(24)
    with pymupdf.open(src) as doc:
        doc.save(dst, encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw=owner_pw, user_pw=user_pw,
                 permissions=int(pymupdf.PDF_PERM_PRINT | pymupdf.PDF_PERM_ACCESSIBILITY))


def _verify_lock(path: Path, user_pw: str, expected: dict) -> str | None:
    """DP-09: the file must refuse to open without a password and open with the recipient's own."""
    with pymupdf.open(path) as doc:
        if not doc.needs_pass:
            return "Attachment is not password-protected"
    try:
        fields = read_fields(extract_text(path, password=user_pw))
    except PermissionError:
        return "Attachment does not open with the recipient's password"
    if fields["policy_no"] != expected["policy_no"] or fields["nik"] != expected["nik"]:
        return "Locked attachment content changed during locking"
    return None


def validate(batch_id: str, actor: str = "system") -> dict:
    t0 = time.perf_counter()
    state = load_state(batch_id)
    if state["status"] not in ("NEW", "VALIDATED", "REJECTED", "HALTED"):
        raise WorkflowError(f"Batch {batch_id} is {state['status']}; it cannot be re-validated")

    out = batch_dir(batch_id)
    for sub in ("quarantine", "locked", "outbox", "outbox_dryrun"):
        shutil.rmtree(out / sub, ignore_errors=True)
    for f in ("manifest.json", "delivery_status.csv"):
        (out / f).unlink(missing_ok=True)
    (out / "quarantine").mkdir(parents=True)
    (out / "locked").mkdir(parents=True)

    send, customers, branches = load_inputs(batch_id)
    letter_dir = DATA_DIR / "batches" / batch_id / "letters"
    results, orphans = validate_batch(send, customers, branches, letter_dir)
    master = customers.set_index("policy_no")
    titles = settings()["letter_types"]

    manifest = []
    lock_failures = 0
    for r in results:
        if r.status == "READY":
            cust = master.loc[r.policy_no]
            pw = _dob_password(cust["dob"])
            dst = out / "locked" / r.letter_file
            _lock_pdf(letter_dir / r.letter_file, dst, pw)
            problem = _verify_lock(dst, pw, {"policy_no": r.policy_no, "nik": cust["nik"]})
            if problem:
                from .controls import Finding
                r.findings.append(Finding("DP-09", problem))
                dst.unlink(missing_ok=True)
                lock_failures += 1
            else:
                manifest.append({
                    "policy_no": r.policy_no,
                    "letter_type": r.letter_type,
                    "letter_title": titles[r.letter_type],
                    "name": cust["name"],
                    "to_email": r.to_email,
                    "cc_email": r.cc_email,
                    "branch_code": r.branch_code_master,
                    "attachment": dst.name,
                    "sha256": sha256(dst),
                })
        for fd in r.findings:
            audit.log(batch_id, actor, "VALIDATE", "FAIL", fd.detail, r.policy_no, fd.control_id)
        if r.status == "READY":
            audit.log(batch_id, actor, "VALIDATE", "PASS", "All pre-send controls passed", r.policy_no)

    # Every letter that is not cleared for sending is copied to quarantine (copy, never move:
    # the source folder stays untouched). This covers held, duplicate, ambiguous and orphan files.
    released = {m["attachment"] for m in manifest}
    for p in letter_dir.glob("*.pdf"):
        if p.name not in released:
            shutil.copy2(p, out / "quarantine" / p.name)
    for o in orphans:
        audit.log(batch_id, actor, "VALIDATE", "FAIL", o["detail"], o["policy_no"] or "", "DP-05")

    frame = results_frame(results, orphans)
    frame.to_csv(out / "validation.csv", index=False)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))

    n_customers = len(results)
    n_ready = len(manifest)
    q_rate = 1 - n_ready / n_customers if n_customers else 0
    elapsed = time.perf_counter() - t0
    summary = {
        "customers": n_customers,
        "ready": n_ready,
        "quarantined": n_customers - n_ready,
        "orphan_letters": len(orphans),
        "quarantine_rate": round(q_rate, 4),
        "lock_failures": lock_failures,
        "validation_seconds": round(elapsed, 2),
    }
    state["summary"] = summary
    state["maker"] = state["checker"] = None
    ks = settings()["kill_switch"]
    if q_rate > ks["max_quarantine_rate"]:
        _transition(state, "HALTED", actor,
                    f"Kill switch: quarantine rate {q_rate:.1%} above {ks['max_quarantine_rate']:.0%}")
    else:
        _transition(state, "VALIDATED", actor, f"{n_ready} ready, {n_customers - n_ready} quarantined")
    return summary


# ---------------------------------------------------------------- step 3-4: maker / checker
def _manifest_hash(batch_id: str) -> str:
    return sha256(batch_dir(batch_id) / "manifest.json")


def submit(batch_id: str, maker: str) -> None:
    state = load_state(batch_id)
    if _role(maker) != "maker":
        raise WorkflowError(f"{maker} is not authorised as a maker")
    if state["status"] != "VALIDATED":
        raise WorkflowError(f"Only a VALIDATED batch can be submitted (current: {state['status']})")
    state["maker"] = maker
    state["manifest_hash"] = _manifest_hash(batch_id)
    _transition(state, "SUBMITTED", maker, f"{state['summary']['ready']} emails submitted for approval")


def approve(batch_id: str, checker: str) -> None:
    state = load_state(batch_id)
    if checker == state.get("maker"):  # checked first: holds even for users with both roles
        audit.log(batch_id, checker, "APPROVE", "BLOCKED", "Maker tried to approve own batch")
        raise SegregationOfDutiesError("The maker cannot approve their own batch")
    if _role(checker) != "checker":
        raise WorkflowError(f"{checker} is not authorised as a checker")
    if state["status"] != "SUBMITTED":
        raise WorkflowError(f"Only a SUBMITTED batch can be approved (current: {state['status']})")
    if _manifest_hash(batch_id) != state["manifest_hash"]:
        raise WorkflowError("Manifest changed after submission - resubmit required")
    state["checker"] = checker
    _transition(state, "APPROVED", checker, "Batch approved for sending")


def reject(batch_id: str, checker: str, reason: str) -> None:
    state = load_state(batch_id)
    if _role(checker) != "checker":
        raise WorkflowError(f"{checker} is not authorised as a checker")
    if state["status"] != "SUBMITTED":
        raise WorkflowError("Only a SUBMITTED batch can be rejected")
    _transition(state, "REJECTED", checker, reason)


# ---------------------------------------------------------------- step 5: send
def _integrity_failures(batch_id: str, manifest: list[dict]) -> list[str]:
    locked = batch_dir(batch_id) / "locked"
    bad = []
    for m in manifest:
        p = locked / m["attachment"]
        if not p.exists() or sha256(p) != m["sha256"]:
            bad.append(m["policy_no"])
    return bad


def send(batch_id: str, actor: str, dry_run: bool = False) -> dict:
    cfg = settings()
    state = load_state(batch_id)
    if state["status"] != "APPROVED":
        raise WorkflowError(f"Batch must be APPROVED before sending (current: {state['status']})")
    if _manifest_hash(batch_id) != state["manifest_hash"]:
        _transition(state, "HALTED", actor, "Manifest changed after approval")
        raise WorkflowError("Manifest changed after approval - batch halted")

    problems = check_sender()  # DP-12
    if problems:
        audit.log(batch_id, actor, "SEND", "BLOCKED", "; ".join(problems), control_id="DP-12")
        raise WorkflowError("Sender control failed: " + "; ".join(problems))

    manifest = json.loads((batch_dir(batch_id) / "manifest.json").read_text())
    bad = _integrity_failures(batch_id, manifest)  # DP-13 before anything leaves
    if len(bad) > cfg["kill_switch"]["max_integrity_failures"]:
        for pol in bad:
            audit.log(batch_id, actor, "SEND", "BLOCKED", "Attachment differs from approved version",
                      pol, "DP-13")
        _transition(state, "HALTED", actor, f"Kill switch: {len(bad)} attachment(s) changed after approval")
        return {"sent": 0, "halted": True, "integrity_failures": len(bad)}

    t0 = time.perf_counter()
    folder = batch_dir(batch_id) / ("outbox_dryrun" if dry_run else "outbox")
    transport = (OutboxTransport(folder) if dry_run or cfg["sender"]["transport"] == "outbox"
                 else SMTPTransport())
    cc_mode = cfg["branch_cc_mode"]
    locked = batch_dir(batch_id) / "locked"
    sent, errors, consecutive = 0, 0, 0
    for m in manifest:
        att = locked / m["attachment"]
        if sha256(att) != m["sha256"]:  # DP-13 again, at the last mile
            audit.log(batch_id, actor, "SEND", "BLOCKED", "Last-mile hash mismatch", m["policy_no"], "DP-13")
            continue
        to_email = cfg["dry_run_mailbox"] if dry_run else m["to_email"]
        cc_email = None if dry_run else (m["cc_email"] if cc_mode == "cc" else None)
        msg = build_customer_email(name=m["name"], to_email=to_email, cc_email=cc_email,
                                   letter_title=m["letter_title"], policy_no=m["policy_no"],
                                   attachment=att, batch_id=batch_id)
        body = msg.get_body(preferencelist=("plain",)).get_content()
        if content_has_nik(msg["Subject"], body):  # DP-10 at email level
            audit.log(batch_id, actor, "SEND", "BLOCKED", "NIK found in subject/body", m["policy_no"], "DP-10")
            continue
        try:
            ref = transport.send(msg)
            if cc_mode == "notice_only" and not dry_run:
                transport.send(build_branch_notice(branch_email=m["cc_email"], letter_title=m["letter_title"],
                                                   policy_no=m["policy_no"], batch_id=batch_id))
            sent += 1
            consecutive = 0
            audit.log(batch_id, actor, "SEND_DRYRUN" if dry_run else "SEND", "OK",
                      f"to {mask_email(to_email)} cc {cc_email or '-'} ref {ref}", m["policy_no"])
        except Exception as exc:  # transport error
            errors += 1
            consecutive += 1
            audit.log(batch_id, actor, "SEND", "ERROR", type(exc).__name__, m["policy_no"])
            if consecutive >= cfg["kill_switch"]["max_consecutive_transport_errors"]:
                _transition(state, "HALTED", actor, "Kill switch: repeated transport errors")
                return {"sent": sent, "halted": True, "errors": errors}

    if dry_run:
        state["dry_run"] = {"emails": sent, "mailbox": cfg["dry_run_mailbox"],
                            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        _save_state(state)
        audit.log(batch_id, actor, "DRY_RUN", "OK", f"{sent} emails routed to QA mailbox")
    else:
        state["sent"] = {"emails": sent, "errors": errors,
                         "send_seconds": round(time.perf_counter() - t0, 2)}
        _transition(state, "SENT", actor, f"{sent} emails sent, {errors} transport errors")
    return {"sent": sent, "halted": False, "errors": errors, "dry_run": dry_run}


# ---------------------------------------------------------------- step 6: monitor
BOUNCE_REASONS = ["Mailbox full", "User unknown", "Domain not found"]


def simulate_delivery(batch_id: str, seed: int = 7) -> pd.DataFrame:
    """Simulated delivery feedback (a real deployment would read bounce/DSN messages)."""
    state = load_state(batch_id)
    if state["status"] != "SENT":
        raise WorkflowError("Delivery can only be monitored after sending")
    manifest = json.loads((batch_dir(batch_id) / "manifest.json").read_text())
    rng = np.random.default_rng(seed + int(batch_id.replace("-", "")))
    rows = []
    for m in manifest:
        bounced = rng.random() < 0.02
        rows.append({
            "policy_no": m["policy_no"],
            "branch_code": m["branch_code"],
            "to_email_masked": mask_email(m["to_email"]),
            "status": "BOUNCED" if bounced else "DELIVERED",
            "reason": BOUNCE_REASONS[int(rng.integers(0, 3))] if bounced else "",
            "follow_up": "Branch to confirm current email with customer" if bounced else "",
        })
    df = pd.DataFrame(rows)
    df.to_csv(batch_dir(batch_id) / "delivery_status.csv", index=False)
    for _, r in df[df.status == "BOUNCED"].iterrows():
        audit.log(batch_id, "system", "DELIVERY", "BOUNCED", r["reason"], r["policy_no"])
    audit.log(batch_id, "system", "DELIVERY", "OK",
              f"{(df.status == 'DELIVERED').sum()} delivered, {(df.status == 'BOUNCED').sum()} bounced")
    return df
