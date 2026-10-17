"""Email construction and transport.

The default transport writes RFC 822 .eml files to a local outbox, so the whole
flow can be demonstrated and audited without sending a single real email.
"""

from __future__ import annotations

import hashlib
import json
import os
import smtplib
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from pathlib import Path

from . import CONFIG_PATH, settings
from .pii import find_niks, mask_policy


class SenderControlError(RuntimeError):
    """DP-12 failure: the batch must not be sent from this configuration."""


def check_sender() -> list[str]:
    """DP-12: official mailbox only, on the company domain, credentials from environment only."""
    cfg = settings()
    problems = []
    sender = cfg["sender"]["official_mailbox"].lower()
    if not sender.endswith("@" + cfg["company"]["domain"].lower()):
        problems.append("Sender mailbox is not on the company domain")
    raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    smtp_env = raw["sender"].get("smtp_env", {})
    if any(not str(v).startswith("SCC_") for v in smtp_env.values()):
        problems.append("SMTP settings must reference environment variable names, not literal values")
    def walk(d):
        for k, v in d.items():
            if isinstance(v, dict):
                yield from walk(v)
            else:
                yield k, v
    if any("pass" in k.lower() and not str(v).startswith("SCC_") for k, v in walk(raw["sender"])):
        problems.append("A literal password appears in the sender configuration")
    if cfg["sender"]["transport"] == "smtp":
        missing = [v for v in smtp_env.values() if not os.environ.get(v)]
        if missing:
            problems.append(f"Missing SMTP environment variables: {', '.join(missing)}")
    return problems


def content_has_nik(*texts: str) -> bool:
    """DP-10 at email level: no 16-digit number may appear in subject or body."""
    return any(find_niks(t) for t in texts)


def build_customer_email(*, name: str, to_email: str, cc_email: str | None, letter_title: str,
                         policy_no: str, attachment: Path, batch_id: str) -> EmailMessage:
    cfg = settings()
    msg = EmailMessage()
    msg["From"] = formataddr((cfg["sender"]["display_name"], cfg["sender"]["official_mailbox"]))
    msg["To"] = to_email
    if cc_email:
        msg["Cc"] = cc_email
    msg["Subject"] = f"{cfg['company']['short_name']} - {letter_title} - Policy {mask_policy(policy_no)}"
    msg["Message-ID"] = make_msgid(domain=cfg["company"]["domain"])
    msg["X-SCC-Batch"] = batch_id
    msg["X-SCC-Key"] = hashlib.sha256(f"{batch_id}:{policy_no}".encode()).hexdigest()[:16]
    msg.set_content(
        f"Dear {name},\n\n"
        f"Please find attached your {letter_title} for policy {mask_policy(policy_no)}.\n\n"
        "For your security the attachment is password-protected. "
        "The password is your date of birth in DDMMYYYY format.\n\n"
        "If you are not the intended recipient, please delete this email and let us know.\n\n"
        f"Customer Correspondence Team\n{cfg['company']['name']}\n"
    )
    msg.add_attachment(attachment.read_bytes(), maintype="application", subtype="pdf",
                       filename=attachment.name)
    return msg


def build_branch_notice(*, branch_email: str, letter_title: str, policy_no: str,
                        batch_id: str) -> EmailMessage:
    """Used when branch_cc_mode = notice_only: branch is informed, but receives no personal data."""
    cfg = settings()
    msg = EmailMessage()
    msg["From"] = formataddr((cfg["sender"]["display_name"], cfg["sender"]["official_mailbox"]))
    msg["To"] = branch_email
    msg["Subject"] = f"[Branch notice] {letter_title} sent - Policy {mask_policy(policy_no)}"
    msg["Message-ID"] = make_msgid(domain=cfg["company"]["domain"])
    msg["X-SCC-Batch"] = batch_id
    msg.set_content(
        f"A {letter_title} for policy {mask_policy(policy_no)} serviced by your branch was sent "
        "to the policyholder's registered email. No attachment is included in this notice.\n"
    )
    return msg


class OutboxTransport:
    def __init__(self, folder: Path):
        self.folder = folder
        self.folder.mkdir(parents=True, exist_ok=True)
        self.count = len(list(self.folder.glob("*.eml")))

    def send(self, msg: EmailMessage) -> str:
        self.count += 1
        key = msg.get("X-SCC-Key") or hashlib.sha256(str(msg["Message-ID"]).encode()).hexdigest()[:16]
        path = self.folder / f"{self.count:04d}_{key}.eml"
        path.write_bytes(bytes(msg))
        return path.name


class SMTPTransport:
    """Real sending. Credentials come only from environment variables (DP-12)."""

    def __init__(self):
        env = settings()["sender"]["smtp_env"]
        self.host = os.environ[env["host"]]
        self.port = int(os.environ.get(env["port"], "587"))
        self.user = os.environ[env["user"]]
        self.password = os.environ[env["password"]]

    def send(self, msg: EmailMessage) -> str:
        with smtplib.SMTP(self.host, self.port, timeout=30) as smtp:
            smtp.starttls()
            smtp.login(self.user, self.password)
            smtp.send_message(msg)
        return str(msg["Message-ID"])
