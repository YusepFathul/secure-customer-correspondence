"""Secure Customer Correspondence (SCC).

Automated customer letter delivery by email with built-in data protection
controls and maker-checker governance.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "config" / "settings.json"
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "output"
LOG_DIR = PROJECT_ROOT / "logs"
REPORT_DIR = PROJECT_ROOT / "reports"

CONTROL_NAMES = {
    "DP-01": "Every customer on the send list has a letter",
    "DP-02": "No duplicate letters for one customer",
    "DP-03": "File name points to exactly one policy",
    "DP-04": "Letter content (policy, name, NIK) matches the recipient",
    "DP-05": "No orphan letter without an owner on the send list",
    "DP-06": "Customer email matches master data and has no domain typo",
    "DP-07": "Branch CC resolved from branch master and allowlisted",
    "DP-08": "One email = one customer + their own branch, no BCC",
    "DP-09": "Letters containing NIK are password-protected",
    "DP-10": "NIK never appears in file name, subject or email body",
    "DP-11": "Logs and reports store masked personal data only",
    "DP-12": "Sent only from the official mailbox, no credentials in code",
    "DP-13": "Attachment is byte-identical to the approved version",
}


@lru_cache(maxsize=1)
def settings() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
