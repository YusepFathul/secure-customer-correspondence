"""Append-only audit trail. Callers must pass masked values only (DP-11)."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pandas as pd

from . import LOG_DIR
from .pii import redact_niks

AUDIT_PATH = LOG_DIR / "audit_log.jsonl"


def log(batch_id: str, actor: str, action: str, result: str, detail: str = "",
        policy_no: str = "", control_id: str = "") -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "batch_id": batch_id,
        "actor": actor,
        "action": action,
        "policy_no": policy_no,
        "control_id": control_id,
        "result": result,
        "detail": redact_niks(detail),  # defence in depth for DP-11
    }
    with AUDIT_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def read(batch_id: str | None = None) -> pd.DataFrame:
    if not AUDIT_PATH.exists():
        return pd.DataFrame(columns=["ts", "batch_id", "actor", "action", "policy_no",
                                     "control_id", "result", "detail"])
    df = pd.read_json(AUDIT_PATH, lines=True, dtype={"policy_no": str, "batch_id": str})
    return df if batch_id is None else df[df["batch_id"] == batch_id]
