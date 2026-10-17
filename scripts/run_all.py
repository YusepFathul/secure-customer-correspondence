"""End-to-end run: generate synthetic data, then for each monthly batch
validate -> maker submit -> checker approve -> dry run -> send -> monitor,
and finally build the management report.

    python scripts/run_all.py
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from scc import LOG_DIR, OUTPUT_DIR, REPORT_DIR  # noqa: E402
from scc import pipeline, reporting, synthetic  # noqa: E402

MAKERS = ["dina.maker", "rizky.maker", "dina.maker"]
CHECKERS = ["sari.supervisor", "budi.supervisor", "sari.supervisor"]


def main() -> None:
    for d in (OUTPUT_DIR, LOG_DIR, REPORT_DIR):
        shutil.rmtree(d, ignore_errors=True)
    print("Generating synthetic data ...", synthetic.generate())

    for i, batch in enumerate(pipeline.list_batches()):
        summary = pipeline.validate(batch, actor="system")
        print(f"[{batch}] validated: {summary}")
        pipeline.submit(batch, MAKERS[i])
        try:  # Segregation of duties is enforced: the maker cannot approve
            pipeline.approve(batch, MAKERS[i])
        except pipeline.WorkflowError as exc:
            print(f"[{batch}] blocked as expected: {exc}")
        pipeline.approve(batch, CHECKERS[i])
        dry = pipeline.send(batch, MAKERS[i], dry_run=True)
        print(f"[{batch}] dry run: {dry['sent']} emails to QA mailbox")
        result = pipeline.send(batch, MAKERS[i])
        print(f"[{batch}] sent: {result}")
        pipeline.simulate_delivery(batch)

    out = reporting.build_report()
    print(out["kpis"].to_string(index=False))
    print("DP-11 raw PII found in logs/reports:", out["pii_hits"] or "none")


if __name__ == "__main__":
    main()
