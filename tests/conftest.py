"""Builds a small, isolated dataset for every test (never touches data/ or output/)."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from scc import audit, pipeline, reporting  # noqa: E402
from scc.letters import render_letter  # noqa: E402

BATCH = "2099-01"

CUSTOMERS = [
    # policy, name, nik, dob, email, branch
    ("7700000001", "Andi Santoso", "3171010101800001", "1980-01-01", "andi.santoso@gmail.example", "JKT"),
    ("7700000002", "Budi Wijaya", "3273024502850002", "1985-02-05", "budi.wijaya@yahoo.example", "BDG"),
    ("7700000003", "Citra Lestari", "3578034303900003", "1990-03-03", "citra.lestari@outlook.example", "SBY"),
    ("7700000004", "Dewi Kusuma", "3273044404880004", "1988-04-04", "dewi.kusuma@gmail.example", "BDG"),
    ("7700000005", "Eko Pratama", "1271050505750005", "1975-05-05", "eko.pratama@gmail.example", "MDN"),
]
BRANCHES = [("JKT", "Jakarta Head Office"), ("BDG", "Bandung"), ("SBY", "Surabaya"), ("MDN", "Medan")]


def payload(c, letter_type="MATURITY"):
    return {
        "letter_type": letter_type, "ref_no": f"NL/TST/{c[0][-4:]}", "letter_date": "05 January 2099",
        "name": c[1], "policy_no": c[0], "nik": c[2], "address": "Jl. Test No. 1",
        "branch_name": dict(BRANCHES)[c[5]], "due_date": "28 January 2099", "amount": "1.000.000",
        "account_masked": "****1234",
    }


@pytest.fixture
def env(tmp_path, monkeypatch):
    data, out, logs = tmp_path / "data", tmp_path / "output", tmp_path / "logs"
    for mod, attr, val in [
        (pipeline, "DATA_DIR", data), (pipeline, "OUTPUT_DIR", out),
        (reporting, "DATA_DIR", data), (reporting, "OUTPUT_DIR", out), (reporting, "LOG_DIR", logs),
        (reporting, "REPORT_DIR", tmp_path / "reports"),
        (audit, "LOG_DIR", logs), (audit, "AUDIT_PATH", logs / "audit_log.jsonl"),
    ]:
        monkeypatch.setattr(mod, attr, val)

    ldir = data / "batches" / BATCH / "letters"
    ldir.mkdir(parents=True)
    pd.DataFrame(CUSTOMERS, columns=["policy_no", "name", "nik", "dob", "email", "branch_code"]).assign(
        address="Jl. Test No. 1").to_csv(data / "customers_master.csv", index=False)
    pd.DataFrame([(c, n, f"branch.{c.lower()}@nusantaralife.example") for c, n in BRANCHES],
                 columns=["branch_code", "branch_name", "branch_email"]).to_csv(
        data / "branches_master.csv", index=False)

    send = pd.DataFrame([{
        "batch_id": BATCH, "policy_no": c[0], "customer_name": c[1], "email": c[4],
        "branch_code": c[5], "letter_type": "MATURITY", "cc_override": "",
    } for c in CUSTOMERS])
    for c in CUSTOMERS:
        render_letter(ldir / f"MATURITY_{c[0]}_209901.pdf", payload(c))

    class Env:
        root = tmp_path
        letters = ldir
        customers = CUSTOMERS
        batch = BATCH

        def save_send(self, df=None):
            (df if df is not None else send).to_excel(data / "batches" / BATCH / "send_list.xlsx", index=False)

        send_list = send

    e = Env()
    e.save_send()
    return e
