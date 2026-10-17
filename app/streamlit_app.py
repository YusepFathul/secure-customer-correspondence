"""Secure Customer Correspondence - control room.

    streamlit run app/streamlit_app.py
"""

from __future__ import annotations

import json
import shutil
import sys
from email import policy as email_policy
from email.parser import BytesParser
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from scc import CONTROL_NAMES, DATA_DIR, REPORT_DIR, audit, pipeline, reporting, settings, synthetic  # noqa: E402
from scc.pii import mask_email  # noqa: E402

st.set_page_config(page_title="Secure Customer Correspondence", page_icon=":lock:", layout="wide")
CFG = settings()

STATUS_HELP = {
    "NEW": "Not validated yet",
    "VALIDATED": "Controls ran - waiting for the maker to submit",
    "SUBMITTED": "Waiting for checker approval",
    "APPROVED": "Approved - ready to send",
    "SENT": "Sent and monitored",
    "REJECTED": "Rejected by checker - fix and re-validate",
    "HALTED": "Stopped by kill switch - investigate before re-validating",
}

# ------------------------------------------------------------------ sidebar
st.sidebar.title("Secure Customer Correspondence")
st.sidebar.caption("Synthetic data - fictional insurer")

if not (DATA_DIR / "customers_master.csv").exists():
    st.info("No data yet.")
    if st.button("Generate synthetic data"):
        synthetic.generate()
        st.rerun()
    st.stop()

users = CFG["users"]["makers"] + CFG["users"]["checkers"]
user = st.sidebar.selectbox("Signed in as", users)
role = "maker" if user in CFG["users"]["makers"] else "checker"
st.sidebar.write(f"Role: **{role}**")

batches = pipeline.list_batches()
batch = st.sidebar.selectbox("Batch", batches, index=len(batches) - 1)
state = pipeline.load_state(batch)
st.sidebar.write(f"Status: **{state['status']}**")
st.sidebar.caption(STATUS_HELP.get(state["status"], ""))

page = st.sidebar.radio("Step", [
    "1. Validate batch",
    "2. Quarantine review",
    "3. Maker submit",
    "4. Checker approval",
    "5. Send",
    "6. Leakage proof",
    "7. Governance report",
])

if st.sidebar.button("Reset this batch", help="Clears the batch outputs so the workflow can be replayed"):
    shutil.rmtree(pipeline.batch_dir(batch), ignore_errors=True)
    audit.log(batch, user, "RESET", "OK", "Batch outputs cleared for replay")
    st.rerun()


def show_error(exc: Exception) -> None:
    st.error(str(exc))


# ------------------------------------------------------------------ 1. validate
if page.startswith("1"):
    st.header("Validate batch")
    st.write("Runs the pre-send controls on every letter and recipient, then password-locks the letters "
             "that pass. Nothing is sent at this step.")
    send, customers, _ = pipeline.load_inputs(batch)
    c1, c2, c3 = st.columns(3)
    c1.metric("Customers on send list", len(send))
    c2.metric("Letters in folder", len(list((DATA_DIR / "batches" / batch / "letters").glob("*.pdf"))))
    c3.metric("Branches", send["branch_code"].nunique())

    if st.button("Run validation", type="primary", disabled=state["status"] not in
                 ("NEW", "VALIDATED", "REJECTED", "HALTED")):
        with st.spinner("Checking letters, recipients and branch mailboxes ..."):
            try:
                pipeline.validate(batch, actor=user)
                st.rerun()
            except pipeline.WorkflowError as exc:
                show_error(exc)

    if "summary" in state:
        s = state["summary"]
        st.subheader("Result")
        a, b, c, d = st.columns(4)
        a.metric("Ready to send", s["ready"])
        b.metric("Held in quarantine", s["quarantined"])
        c.metric("Orphan letters held", s["orphan_letters"])
        d.metric("Processing time", f"{s['validation_seconds']} s")
        st.subheader("Controls")
        st.dataframe(pd.DataFrame([{"Control": k, "Check": v, "Severity": CFG["severity"][k]}
                                   for k, v in CONTROL_NAMES.items()]),
                     hide_index=True, width='stretch')

# ------------------------------------------------------------------ 2. quarantine
elif page.startswith("2"):
    st.header("Quarantine review")
    vpath = pipeline.batch_dir(batch) / "validation.csv"
    if not vpath.exists():
        st.info("Run validation first.")
        st.stop()
    val = pd.read_csv(vpath, dtype=str).fillna("")
    held = val[val["status"] == "QUARANTINE"]
    st.write(f"**{held['policy_no'].nunique()}** documents held. Personal data is masked on this screen.")
    by_control = held.groupby("control_id")["policy_no"].nunique().rename("documents held")
    st.bar_chart(by_control)
    pick = st.multiselect("Filter by control", sorted(held["control_id"].unique()))
    view = held[held["control_id"].isin(pick)] if pick else held
    st.dataframe(view[["policy_no", "letter_type", "branch_code", "control_id", "severity", "detail",
                       "letter_file"]], hide_index=True, width='stretch')
    st.caption("Held letters are copied (never moved) to the quarantine folder and are never sent.")

# ------------------------------------------------------------------ 3. maker
elif page.startswith("3"):
    st.header("Maker submit")
    if role != "maker":
        st.warning("Sign in as a maker to submit a batch.")
    if state["status"] != "VALIDATED":
        st.info(f"Batch status is {state['status']}. Only a VALIDATED batch can be submitted.")
    else:
        s = state["summary"]
        st.write(f"**{s['ready']}** emails are ready. **{s['quarantined']}** customers and "
                 f"**{s['orphan_letters']}** orphan letter(s) are held and will not be sent.")
        manifest = json.loads((pipeline.batch_dir(batch) / "manifest.json").read_text())
        preview = pd.DataFrame(manifest)[["policy_no", "letter_type", "to_email", "cc_email", "branch_code"]]
        preview["to_email"] = preview["to_email"].map(mask_email)
        st.dataframe(preview, hide_index=True, width='stretch', height=260)
        ok = st.checkbox("I have reviewed the held items and the emails to be sent")
        if st.button("Submit for approval", type="primary", disabled=not ok or role != "maker"):
            try:
                pipeline.submit(batch, user)
                st.success("Submitted. A checker must now approve.")
                st.rerun()
            except pipeline.WorkflowError as exc:
                show_error(exc)

# ------------------------------------------------------------------ 4. checker
elif page.startswith("4"):
    st.header("Checker approval")
    if state["status"] != "SUBMITTED":
        st.info(f"Batch status is {state['status']}. Only a SUBMITTED batch can be approved.")
    else:
        s = state["summary"]
        st.write(f"Submitted by **{state['maker']}**: {s['ready']} emails ready, {s['quarantined']} held "
                 f"({s['quarantine_rate']:.1%} quarantine rate).")
        if user == state["maker"]:
            st.error("Segregation of duties: you submitted this batch, so you cannot approve it.")
        col1, col2 = st.columns(2)
        if col1.button("Approve", type="primary"):
            try:
                pipeline.approve(batch, user)
                st.rerun()
            except pipeline.WorkflowError as exc:
                show_error(exc)
        reason = col2.text_input("Reason for rejection")
        if col2.button("Reject"):
            if not reason.strip():
                col2.error("Enter a reason first")
            else:
                try:
                    pipeline.reject(batch, user, reason)
                    st.rerun()
                except pipeline.WorkflowError as exc:
                    show_error(exc)

# ------------------------------------------------------------------ 5. send
elif page.startswith("5"):
    st.header("Send")
    st.write(f"Sender: `{CFG['sender']['official_mailbox']}` | Branch CC mode: `{CFG['branch_cc_mode']}` | "
             f"Transport: `{CFG['sender']['transport']}` (emails are written to a local outbox)")
    if state["status"] != "APPROVED":
        st.info(f"Batch status is {state['status']}. Only an APPROVED batch can be sent.")
    else:
        st.write(f"Approved by **{state['checker']}**. Before any email leaves, the system re-checks the sender "
                 "(DP-12) and that every attachment is byte-identical to the approved version (DP-13).")
        c1, c2 = st.columns(2)
        if c1.button("Dry run to QA mailbox"):
            r = pipeline.send(batch, user, dry_run=True)
            st.success(f"{r['sent']} emails routed to {CFG['dry_run_mailbox']}")
        if c2.button("Send to customers", type="primary", disabled="dry_run" not in state):
            try:
                r = pipeline.send(batch, user)
                if r["halted"]:
                    st.error("Kill switch triggered - batch halted. See the audit trail.")
                else:
                    pipeline.simulate_delivery(batch)
                    st.rerun()
            except pipeline.WorkflowError as exc:
                show_error(exc)
        if "dry_run" not in state:
            st.caption("Run a dry run first.")
    if state["status"] == "SENT":
        st.success(f"{state['sent']['emails']} emails sent in {state['sent'].get('send_seconds', '-')} s.")
        dpath = pipeline.batch_dir(batch) / "delivery_status.csv"
        if dpath.exists():
            d = pd.read_csv(dpath, dtype=str).fillna("")
            st.metric("Bounced - routed to branch follow-up", int((d["status"] == "BOUNCED").sum()))
            st.dataframe(d[d["status"] == "BOUNCED"], hide_index=True, width='stretch')

# ------------------------------------------------------------------ 6. leakage
elif page.startswith("6"):
    st.header("Leakage proof")
    if state["status"] != "SENT":
        st.info("Send the batch first.")
        st.stop()
    emails, matrix = reporting.verify_outbox(batch)
    ev = reporting.evaluate_controls(batch)
    a, b, c, d = st.columns(4)
    a.metric("Emails re-verified", len(emails))
    b.metric("Unsafe emails", int((~emails["safe"]).sum()))
    c.metric("Cross-branch exposures", int(matrix.values.sum() - matrix.values.diagonal().sum()))
    d.metric("Injected defects caught", f"{ev['caught']} / {ev['injected']}")
    st.write("Every email in the outbox is opened independently: the attachment must open with the *To* "
             "recipient's own password, contain only that recipient's policy and NIK, and be CC'd only to "
             "that recipient's branch.")
    st.subheader("Branch x data-owner matrix")
    st.dataframe(matrix, width='stretch')
    st.caption("Rows: branch mailbox that received the CC. Columns: branch that owns the customer's data. "
               "Anything off the diagonal would be a leak.")
    st.subheader("Inspect an email")
    emls = sorted((pipeline.batch_dir(batch) / "outbox").glob("*.eml"))
    pick = st.selectbox("Email", [e.name for e in emls])
    msg = BytesParser(policy=email_policy.default).parsebytes((pipeline.batch_dir(batch) / "outbox" / pick)
                                                              .read_bytes())
    st.code(f"From: {msg['From']}\nTo: {mask_email(str(msg['To']))}\nCc: {msg.get('Cc', '-')}\n"
            f"Subject: {msg['Subject']}\nAttachment: {[a.get_filename() for a in msg.iter_attachments()]}\n\n"
            f"{msg.get_body(preferencelist=('plain',)).get_content()}")

# ------------------------------------------------------------------ 7. governance
else:
    st.header("Governance report")
    if st.button("Rebuild monthly report"):
        with st.spinner("Building report ..."):
            reporting.build_report()
    kpi_path = REPORT_DIR / "kpi_summary.csv"
    if kpi_path.exists():
        k = pd.read_csv(kpi_path)
        st.dataframe(k, hide_index=True, width='stretch')
        for chart in ["chart_batch_outcome.png", "chart_exceptions_by_control.png",
                      "chart_leakage_matrix.png", "chart_as_is_vs_to_be.png"]:
            if (REPORT_DIR / chart).exists():
                st.image(str(REPORT_DIR / chart))
        md = REPORT_DIR / "management_summary.md"
        if md.exists():
            with st.expander("Management summary"):
                st.markdown(md.read_text())
        xlsx = REPORT_DIR / "monthly_control_report.xlsx"
        if xlsx.exists():
            st.download_button("Download Excel report", xlsx.read_bytes(), file_name=xlsx.name)
    st.subheader("Audit trail")
    log = audit.read(batch)
    st.dataframe(log.sort_values("ts", ascending=False), hide_index=True, width='stretch', height=320)
    st.caption("Personal data in the audit trail is masked (DP-11).")
