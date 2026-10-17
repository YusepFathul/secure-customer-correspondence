"""Render customer letters as PDF (reportlab) and read their key fields back (PyMuPDF)."""

from __future__ import annotations

import re
from pathlib import Path

import pymupdf
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from . import settings

BODY = {
    "MATURITY": [
        "We would like to inform you that your policy will reach its maturity date on {due_date}.",
        "The estimated maturity benefit is IDR {amount}. To receive the benefit, please make sure",
        "your bank account details registered with us are up to date.",
    ],
    "BENEFIT_PAYMENT": [
        "We confirm that the benefit payment for your policy of IDR {amount} has been processed",
        "on {due_date} to your registered bank account {account_masked}.",
        "Please allow up to three working days for the funds to appear in your account.",
    ],
    "REINSTATEMENT": [
        "Your policy has lapsed because the premium was not received. You can reinstate it by",
        "paying the outstanding premium of IDR {amount} before {due_date}.",
        "Once the payment is received, your coverage will be active again.",
    ],
}

FIELD_PATTERNS = {
    "policy_no": re.compile(r"Policy Number\s*:\s*(\d{10})"),
    "name": re.compile(r"Policyholder Name\s*:\s*(.+)"),
    "nik": re.compile(r"NIK\s*:\s*(\d{16})"),
}


def render_letter(path: Path, letter: dict) -> None:
    """letter keys: letter_type, ref_no, letter_date, name, policy_no, nik, address,
    branch_name, due_date, amount, account_masked"""
    cfg = settings()
    c = canvas.Canvas(str(path), pagesize=A4)
    w, h = A4
    x = 22 * mm
    y = h - 25 * mm

    # Watermark: every synthetic letter is visibly marked as an example
    c.saveState()
    c.setFillColorRGB(0.88, 0.88, 0.88)
    c.setFont("Helvetica-Bold", 96)
    c.translate(w / 2, h / 2)
    c.rotate(35)
    c.drawCentredString(0, -30, "EXAMPLE")
    c.restoreState()

    c.setFont("Helvetica-Bold", 15)
    c.drawString(x, y, cfg["company"]["short_name"])
    c.setFont("Helvetica", 8)
    c.drawString(x, y - 11, "EXAMPLE - fictional insurer, synthetic document for a portfolio project")
    c.drawRightString(w - x, y, f"Ref: {letter['ref_no']}")
    c.drawRightString(w - x, y - 11, f"Date: {letter['letter_date']}")
    c.line(x, y - 18, w - x, y - 18)

    y -= 45
    c.setFont("Helvetica-Bold", 13)
    c.drawString(x, y, cfg["letter_types"][letter["letter_type"]])

    y -= 28
    c.setFont("Helvetica", 10)
    for label, key in [
        ("Policyholder Name", "name"),
        ("Policy Number", "policy_no"),
        ("NIK", "nik"),
        ("Address", "address"),
        ("Servicing Branch", "branch_name"),
    ]:
        c.drawString(x, y, f"{label} : {letter[key]}")
        y -= 15

    y -= 15
    c.drawString(x, y, f"Dear {letter['name']},")
    y -= 20
    for line in BODY[letter["letter_type"]]:
        c.drawString(x, y, line.format(**letter))
        y -= 15

    y -= 15
    c.drawString(x, y, "If any of the information above is incorrect, please contact your servicing branch.")
    y -= 35
    c.drawString(x, y, "Sincerely,")
    y -= 15
    c.setFont("Helvetica-Bold", 10)
    c.drawString(x, y, "Customer Correspondence Team")

    c.setFont("Helvetica", 7)
    c.drawString(x, 15 * mm, "EXAMPLE ONLY - all names, NIK, numbers, addresses and emails are synthetic.")
    c.showPage()
    c.save()


def extract_text(path: Path, password: str | None = None) -> str:
    with pymupdf.open(path) as doc:
        if doc.needs_pass:
            if not password or not doc.authenticate(password):
                raise PermissionError(f"Cannot open {path.name}: password required")
        return "\n".join(page.get_text() for page in doc)


def read_fields(text: str) -> dict:
    out = {}
    for key, pattern in FIELD_PATTERNS.items():
        m = pattern.search(text)
        out[key] = m.group(1).strip() if m else None
    return out
