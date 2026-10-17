"""Export the numbers used by presentation/build_deck.js from the generated reports.

    python scripts/export_deck_data.py && node presentation/build_deck.js
"""

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
k = pd.read_csv(ROOT / "reports" / "kpi_summary.csv")
x = pd.read_excel(ROOT / "reports" / "monthly_control_report.xlsx", sheet_name=None)
bc, m = x["Exceptions by control"], x["Leakage matrix"]
batch_cols = [c for c in bc.columns if str(c).startswith("20")]

data = {
    "kpi": {c: int(k[c].sum()) for c in [
        "customers", "emails_sent", "quarantined", "orphan_letters", "injected_defects", "defects_caught",
        "defects_leaked", "false_positives", "unsafe_emails", "cross_branch_exposures", "bounced", "delivered"]},
    "machine_seconds_avg": round(float(k["machine_seconds"].mean()), 1),
    "as_is_min": float(k["as_is_hours_assumed"].mean() * 60),
    "to_be_min": float(k["to_be_minutes"].mean()),
    "batches": k[["batch_id", "customers", "emails_sent", "quarantined", "maker", "checker"]].to_dict("records"),
    "by_control": [{"id": r["control_id"], "n": int(sum(r[c] for c in batch_cols)), "sev": r["severity"]}
                   for _, r in bc.iterrows()],
    "matrix": {"rows": m.iloc[:, 0].tolist(), "cols": list(m.columns[1:]),
               "values": m.iloc[:, 1:].astype(int).values.tolist()},
}
(ROOT / "presentation" / "deck_data.json").write_text(json.dumps(data, indent=1))
print("wrote presentation/deck_data.json")
