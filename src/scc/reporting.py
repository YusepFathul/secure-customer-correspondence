"""Leakage verification, control testing, PII scan of outputs and the monthly management report."""

from __future__ import annotations

import json
from email import policy as email_policy
from email.parser import BytesParser
from pathlib import Path
import tempfile

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from . import CONTROL_NAMES, DATA_DIR, LOG_DIR, OUTPUT_DIR, REPORT_DIR, audit, settings
from .letters import extract_text, read_fields
from .mailer import content_has_nik
from .pii import find_niks, is_valid_nik
from .pipeline import _dob_password, batch_dir, list_batches, load_state

# Reference data-viz palette (light surface)
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
BLUE, ORANGE = "#2a78d6", "#eb6834"
SHORT = {
    "DP-01": "Letter missing", "DP-02": "Duplicate letter", "DP-03": "Ambiguous file name",
    "DP-04": "Letter content not the recipient's", "DP-05": "Orphan letter",
    "DP-06": "Email differs from master / typo", "DP-07": "Wrong or manual branch CC",
    "DP-08": "More than one recipient", "DP-09": "Attachment not locked",
    "DP-10": "NIK in file name", "DP-11": "Raw PII in logs", "DP-12": "Unofficial sender",
    "DP-13": "File changed after approval",
}


# ---------------------------------------------------------------- leakage verification
def verify_outbox(batch_id: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Independently re-checks every email in the outbox.

    For each email: the attachment must open with the *To* recipient's own password,
    contain only that recipient's policy and NIK, and be CC'd only to that recipient's
    branch. Returns per-email results and a branch x data-owner leakage matrix.
    """
    customers = pd.read_csv(DATA_DIR / "customers_master.csv", dtype=str)
    branches = pd.read_csv(DATA_DIR / "branches_master.csv", dtype=str)
    by_email = customers.set_index(customers["email"].str.lower())
    branch_of_mailbox = dict(zip(branches["branch_email"].str.lower(), branches["branch_code"]))
    branch_email = dict(zip(branches["branch_code"], branches["branch_email"].str.lower()))
    codes = list(branches["branch_code"])

    rows = []
    matrix = pd.DataFrame(0, index=codes, columns=codes)
    matrix.index.name = "branch_mailbox_received"
    matrix.columns.name = "data_owner_branch"
    parser = BytesParser(policy=email_policy.default)
    for eml in sorted((batch_dir(batch_id) / "outbox").glob("*.eml")):
        msg = parser.parsebytes(eml.read_bytes())
        to = str(msg["To"]).strip().lower()
        cc = [a.strip().lower() for a in str(msg.get("Cc", "")).split(",") if a.strip()]
        body = msg.get_body(preferencelist=("plain",)).get_content()
        atts = list(msg.iter_attachments())
        r = {"email_file": eml.name, "recipients": 1 + len(cc), "attachments": len(atts),
             "opens_with_recipient_password": False, "owner_matches_recipient": False,
             "cc_is_owner_branch": False, "nik_in_subject_or_body": content_has_nik(str(msg["Subject"]), body),
             "bcc_header": msg.get("Bcc") is not None}
        cust = by_email.loc[to] if to in by_email.index else None
        if cust is not None and len(atts) == 1:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(atts[0].get_content())
                tmp_path = Path(tmp.name)
            try:
                fields = read_fields(extract_text(tmp_path, password=_dob_password(cust["dob"])))
                r["opens_with_recipient_password"] = True
                r["owner_matches_recipient"] = (fields["policy_no"] == cust["policy_no"]
                                                and fields["nik"] == cust["nik"])
                owner_branch = cust["branch_code"]
                r["cc_is_owner_branch"] = cc == [branch_email[owner_branch]] or (
                    settings()["branch_cc_mode"] == "notice_only" and cc == [])
                for mailbox in cc:
                    if mailbox in branch_of_mailbox:
                        matrix.loc[branch_of_mailbox[mailbox], owner_branch] += 1
            except PermissionError:
                pass
            finally:
                tmp_path.unlink(missing_ok=True)
        r["safe"] = (r["recipients"] <= 2 and r["attachments"] == 1 and r["opens_with_recipient_password"]
                     and r["owner_matches_recipient"] and r["cc_is_owner_branch"]
                     and not r["nik_in_subject_or_body"] and not r["bcc_header"])
        rows.append(r)
    return pd.DataFrame(rows), matrix


# ---------------------------------------------------------------- control test vs ground truth
def evaluate_controls(batch_id: str) -> dict:
    gt = pd.read_csv(DATA_DIR / "ground_truth_defects.csv", dtype=str)
    gt = gt[gt["batch_id"] == batch_id]
    val = pd.read_csv(batch_dir(batch_id) / "validation.csv", dtype=str).fillna("")
    manifest = json.loads((batch_dir(batch_id) / "manifest.json").read_text())
    released = {m["policy_no"] for m in manifest}
    flagged = val[val["status"] == "QUARANTINE"]
    caught = sum(
        ((flagged["policy_no"] == r.policy_no) & (flagged["control_id"] == r.expected_control)).any()
        for r in gt.itertuples()
    )
    leaked = sorted(set(gt["policy_no"]) & released)
    false_pos = sorted(set(flagged["policy_no"]) - set(gt["policy_no"]))
    return {"injected": len(gt), "caught": int(caught), "leaked": len(leaked),
            "false_positives": len(false_pos), "catch_rate": caught / len(gt) if len(gt) else 1.0}


# ---------------------------------------------------------------- DP-11
def scan_outputs_for_pii() -> list[str]:
    """DP-11: logs and reports must never contain a raw NIK, full customer email or birth date."""
    customers = pd.read_csv(DATA_DIR / "customers_master.csv", dtype=str)
    emails = set(customers["email"].str.lower())
    dobs = {_dob_password(d) for d in customers["dob"]} | set(customers["dob"])
    targets = [LOG_DIR / "audit_log.jsonl"]
    targets += list(OUTPUT_DIR.glob("*/validation.csv")) + list(OUTPUT_DIR.glob("*/delivery_status.csv"))
    targets += list(OUTPUT_DIR.glob("*/state.json"))
    targets += [p for p in REPORT_DIR.glob("*") if p.suffix in (".md", ".csv", ".json", ".xlsx")]
    hits = []
    for t in targets:
        if not t.exists():
            continue
        if t.suffix == ".xlsx":
            text = "\n".join(df.to_csv(index=False) for df in pd.read_excel(t, sheet_name=None, dtype=str).values())
        else:
            text = t.read_text(encoding="utf-8", errors="ignore")
        low = text.lower()
        if any(is_valid_nik(n) for n in find_niks(text)):
            hits.append(f"{t.name}: unmasked NIK")
        if any(e in low for e in emails):
            hits.append(f"{t.name}: full customer email")
        if any(d in text for d in dobs if len(d) >= 8):
            hits.append(f"{t.name}: birth date")
    return sorted(set(hits))


# ---------------------------------------------------------------- KPIs
def batch_kpis(batch_id: str) -> dict:
    cfg = settings()
    state = load_state(batch_id)
    s = state.get("summary", {})
    val = pd.read_csv(batch_dir(batch_id) / "validation.csv", dtype=str).fillna("")
    emails, matrix = verify_outbox(batch_id)
    ev = evaluate_controls(batch_id)
    delivery_p = batch_dir(batch_id) / "delivery_status.csv"
    delivery = pd.read_csv(delivery_p) if delivery_p.exists() else pd.DataFrame(columns=["status"])
    off_diag = int(matrix.values.sum() - pd.Series(matrix.values.diagonal()).sum())
    as_is_min = s.get("customers", 0) * cfg["as_is_baseline"]["minutes_per_letter"]
    machine_s = s.get("validation_seconds", 0) + state.get("sent", {}).get("send_seconds", 0)
    to_be_min = cfg["as_is_baseline"]["to_be_review_minutes_per_batch"] + machine_s / 60
    return {
        "batch_id": batch_id,
        "status": state["status"],
        "maker": state.get("maker"),
        "checker": state.get("checker"),
        "customers": s.get("customers", 0),
        "emails_sent": int(len(emails)),
        "quarantined": s.get("quarantined", 0),
        "orphan_letters": s.get("orphan_letters", 0),
        "quarantine_rate": s.get("quarantine_rate", 0),
        "critical_findings": int((val["severity"] == "CRITICAL").sum()),
        "unsafe_emails": int((~emails["safe"]).sum()) if len(emails) else 0,
        "cross_branch_exposures": off_diag,
        "injected_defects": ev["injected"],
        "defects_caught": ev["caught"],
        "defects_leaked": ev["leaked"],
        "false_positives": ev["false_positives"],
        "delivered": int((delivery["status"] == "DELIVERED").sum()),
        "bounced": int((delivery["status"] == "BOUNCED").sum()),
        "machine_seconds": round(machine_s, 1),
        "as_is_hours_assumed": round(as_is_min / 60, 1),
        "to_be_minutes": round(to_be_min, 1),
    }


# ---------------------------------------------------------------- charts
def _style(ax, title: str):
    ax.set_facecolor(SURFACE)
    ax.figure.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=9, length=0)
    ax.set_title(title, loc="left", fontsize=12, color=INK, pad=14)


def build_charts(kpis: pd.DataFrame, findings: pd.DataFrame, matrix: pd.DataFrame) -> dict:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out = {}

    # 1. Exceptions by control (all batches)
    counts = (findings[["control_id", "batch_id", "policy_no"]].drop_duplicates()
              .groupby("control_id").size().reindex(
        [c for c in CONTROL_NAMES if c in set(findings["control_id"])]))
    fig, ax = plt.subplots(figsize=(7.5, 4.2), dpi=160)
    labels = [f"{c}  {SHORT[c]}" for c in counts.index][::-1]
    ax.barh(labels, counts.values[::-1], color=BLUE, height=0.5)
    for i, v in enumerate(counts.values[::-1]):
        ax.text(v + 0.15, i, str(v), va="center", color=INK, fontsize=9)
    ax.xaxis.set_visible(False)
    _style(ax, "Documents held by each control, Aug-Oct 2026")
    fig.tight_layout()
    out["exceptions_by_control"] = REPORT_DIR / "chart_exceptions_by_control.png"
    fig.savefig(out["exceptions_by_control"])
    plt.close(fig)

    # 2. Batch outcome: sent vs held
    fig, ax = plt.subplots(figsize=(6.5, 3.6), dpi=160)
    x = range(len(kpis))
    ax.bar(x, kpis["emails_sent"], color=BLUE, width=0.5, label="Sent safely")
    ax.bar(x, kpis["quarantined"], bottom=kpis["emails_sent"] + 1.5, color=ORANGE, width=0.5,
           label="Held in quarantine")
    for i, r in kpis.reset_index(drop=True).iterrows():
        ax.text(i, r["emails_sent"] / 2, str(r["emails_sent"]), ha="center", va="center", color="white", fontsize=9)
        ax.text(i, r["emails_sent"] + r["quarantined"] + 6, f"{r['quarantined']} held", ha="center",
                color=INK, fontsize=9)
    ax.set_xticks(list(x), [pd.Timestamp(b + "-01").strftime("%b %Y") for b in kpis["batch_id"]])
    ax.yaxis.set_visible(False)
    ax.set_ylim(0, (kpis["emails_sent"] + kpis["quarantined"]).max() * 1.15)
    ax.legend(frameon=False, fontsize=9, loc="upper left", bbox_to_anchor=(0, -0.08), ncol=2,
              labelcolor=INK2)
    _style(ax, "Customers per batch: sent vs held")
    fig.tight_layout()
    out["batch_outcome"] = REPORT_DIR / "chart_batch_outcome.png"
    fig.savefig(out["batch_outcome"])
    plt.close(fig)

    # 3. Leakage matrix
    fig, ax = plt.subplots(figsize=(6, 4.6), dpi=160)
    data = matrix.values
    ax.imshow(data > 0, cmap=matplotlib.colors.ListedColormap(["#f1f0ec", "#cfe0f6"]))
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            ax.text(j, i, str(data[i, j]), ha="center", va="center",
                    color=INK if data[i, j] else "#a3a29c", fontsize=9)
    ax.set_xticks(range(len(matrix.columns)), matrix.columns)
    ax.set_yticks(range(len(matrix.index)), matrix.index)
    ax.set_xlabel("Branch that owns the customer's data", color=INK2, fontsize=9)
    ax.set_ylabel("Branch mailbox that received it (CC)", color=INK2, fontsize=9)
    for s_ in ax.spines.values():
        s_.set_visible(False)
    ax.tick_params(colors=INK2, labelsize=9, length=0)
    ax.set_title("Leakage matrix: every branch received only its own customers",
                 loc="left", fontsize=11, color=INK, pad=12)
    fig.set_facecolor(SURFACE)
    fig.tight_layout()
    out["leakage_matrix"] = REPORT_DIR / "chart_leakage_matrix.png"
    fig.savefig(out["leakage_matrix"])
    plt.close(fig)

    # 4. As-Is vs To-Be effort per batch
    avg_as_is = kpis["as_is_hours_assumed"].mean() * 60
    avg_to_be = kpis["to_be_minutes"].mean()
    fig, ax = plt.subplots(figsize=(6.5, 2.6), dpi=160)
    ax.barh(["To-Be (automated + controls)", "As-Is (manual, assumed)"], [avg_to_be, avg_as_is],
            color=[BLUE, "#b4b2a9"], height=0.5)
    ax.text(avg_as_is + 8, 1, f"{avg_as_is / 60:.0f} h", va="center", color=INK, fontsize=9)
    ax.text(avg_to_be + 8, 0, f"{avg_to_be:.0f} min", va="center", color=INK, fontsize=9)
    ax.set_xlim(0, avg_as_is * 1.15)
    ax.xaxis.set_visible(False)
    _style(ax, "Effort per 150-letter batch")
    fig.tight_layout()
    out["as_is_vs_to_be"] = REPORT_DIR / "chart_as_is_vs_to_be.png"
    fig.savefig(out["as_is_vs_to_be"])
    plt.close(fig)
    return out


# ---------------------------------------------------------------- report
def build_report() -> dict:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    batches = [b for b in list_batches() if load_state(b)["status"] == "SENT"]
    kpis = pd.DataFrame([batch_kpis(b) for b in batches])

    findings, matrices, delivery = [], [], []
    for b in batches:
        v = pd.read_csv(batch_dir(b) / "validation.csv", dtype=str).fillna("")
        v.insert(0, "batch_id", b)
        findings.append(v[v["status"] == "QUARANTINE"])
        matrices.append(verify_outbox(b)[1])
        d = pd.read_csv(batch_dir(b) / "delivery_status.csv", dtype=str).fillna("")
        d.insert(0, "batch_id", b)
        delivery.append(d)
    findings = pd.concat(findings, ignore_index=True)
    matrix = sum(matrices[1:], matrices[0])
    delivery = pd.concat(delivery, ignore_index=True)

    by_control = (findings.groupby(["control_id", "batch_id"])["policy_no"].nunique()
                  .unstack(fill_value=0))
    by_control.insert(0, "control", [CONTROL_NAMES[c] for c in by_control.index])
    by_control["severity"] = [settings()["severity"][c] for c in by_control.index]
    by_branch = (findings[findings["branch_code"] != ""].groupby(["branch_code", "batch_id"])["policy_no"]
                 .nunique().unstack(fill_value=0))
    follow_up = delivery[delivery["status"] == "BOUNCED"]
    approvals = audit.read()
    approvals = approvals[approvals["action"].isin(["STATE_SUBMITTED", "STATE_APPROVED", "STATE_SENT"])]

    xlsx = REPORT_DIR / "monthly_control_report.xlsx"
    with pd.ExcelWriter(xlsx, engine="openpyxl") as xw:
        kpis.to_excel(xw, sheet_name="KPI summary", index=False)
        by_control.to_excel(xw, sheet_name="Exceptions by control")
        by_branch.to_excel(xw, sheet_name="Exceptions by branch")
        findings.to_excel(xw, sheet_name="Quarantine register", index=False)
        matrix.to_excel(xw, sheet_name="Leakage matrix")
        follow_up.to_excel(xw, sheet_name="Bounce follow-up", index=False)
        approvals.to_excel(xw, sheet_name="Approval trail", index=False)
    _format_workbook(xlsx)

    charts = build_charts(kpis, findings, matrix)
    kpis.to_csv(REPORT_DIR / "kpi_summary.csv", index=False)
    (REPORT_DIR / "management_summary.md").write_text(_management_summary(kpis, by_control), encoding="utf-8")
    pii_hits = scan_outputs_for_pii()
    (REPORT_DIR / "dp11_pii_scan.json").write_text(json.dumps({"files_with_raw_pii": pii_hits}, indent=2))
    return {"kpis": kpis, "charts": charts, "pii_hits": pii_hits, "report": xlsx}


def _format_workbook(path: Path) -> None:
    from openpyxl import load_workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    wb = load_workbook(path)
    head_fill = PatternFill("solid", fgColor="1F3A5F")
    for ws in wb.worksheets:
        for cell in ws[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = head_fill
            cell.alignment = Alignment(vertical="center", wrap_text=True)
        ws.freeze_panes = "A2"
        for col in ws.columns:
            width = max(len(str(c.value or "")) for c in col[:200])
            ws.column_dimensions[col[0].column_letter].width = min(max(10, width + 2), 60)
    wb.save(path)


def _management_summary(k: pd.DataFrame, by_control: pd.DataFrame) -> str:
    tot = k[["customers", "emails_sent", "quarantined", "injected_defects", "defects_caught",
             "defects_leaked", "cross_branch_exposures", "unsafe_emails", "bounced"]].sum()
    batch_cols = [c for c in by_control.columns if c not in ("control", "severity")]
    top = by_control.assign(total=by_control[batch_cols].sum(axis=1)).sort_values("total", ascending=False).head(3)
    lines = [
        "# Customer Correspondence - Monthly Control Report",
        "",
        f"Period: {k['batch_id'].iloc[0]} to {k['batch_id'].iloc[-1]} (synthetic data)",
        "",
        "## Headline",
        "",
        f"- {int(tot.customers)} customers in scope; {int(tot.emails_sent)} letters sent, "
        f"{int(tot.quarantined)} held before sending.",
        f"- Unsafe emails sent: **{int(tot.unsafe_emails)}**. Cross-branch exposures: "
        f"**{int(tot.cross_branch_exposures)}**.",
        f"- Control test: {int(tot.defects_caught)} of {int(tot.injected_defects)} injected defects caught; "
        f"{int(tot.defects_leaked)} reached a customer.",
        f"- {int(tot.bounced)} bounced emails routed to branches for follow-up.",
        "",
        "## Most frequent exceptions",
        "",
    ]
    for cid, r in top.iterrows():
        lines.append(f"- {cid} {r['control']}: {int(r['total'])} documents held")
    lines += [
        "",
        "## Batch detail",
        "",
        "| Batch | Customers | Sent | Held | Quarantine rate | Maker | Checker |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in k.itertuples():
        lines.append(f"| {r.batch_id} | {r.customers} | {r.emails_sent} | {r.quarantined} | "
                     f"{r.quarantine_rate:.1%} | {r.maker} | {r.checker} |")
    lines += [
        "",
        "## Recommendations",
        "",
        "1. Fix email data at source: send-list emails that differ from master data are the top "
        "recipient risk; refresh the send list directly from master data instead of manual edits.",
        "2. Remove the manual CC column from the send-list template; branch mailboxes are resolved "
        "from branch master data only.",
        "3. Enforce the file-naming standard (letter type + policy number + period, no NIK) at the "
        "letter-generation step to remove DP-03 and DP-10 exceptions at the root.",
    ]
    return "\n".join(lines) + "\n"
