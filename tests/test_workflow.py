"""Governance and delivery: maker-checker, locking, integrity, sender control, leakage proof."""

import json

import pymupdf
import pytest

import scc.mailer as mailer
import scc.pipeline as pipeline
from scc import reporting


def prepare(env, maker="dina.maker", checker="sari.supervisor"):
    pipeline.validate(env.batch)
    pipeline.submit(env.batch, maker)
    pipeline.approve(env.batch, checker)


def test_maker_cannot_approve_own_batch(env):
    pipeline.validate(env.batch)
    pipeline.submit(env.batch, "dina.maker")
    with pytest.raises(pipeline.SegregationOfDutiesError):
        pipeline.approve(env.batch, "dina.maker")


def test_unknown_user_and_wrong_order_are_rejected(env):
    pipeline.validate(env.batch)
    with pytest.raises(pipeline.WorkflowError):
        pipeline.approve(env.batch, "sari.supervisor")  # not submitted yet
    with pytest.raises(pipeline.WorkflowError):
        pipeline.submit(env.batch, "intruder")
    with pytest.raises(pipeline.WorkflowError):
        pipeline.send(env.batch, "dina.maker")  # not approved


def test_locked_letter_needs_recipients_own_password(env):
    pipeline.validate(env.batch)
    locked = sorted((pipeline.batch_dir(env.batch) / "locked").glob("*.pdf"))
    assert locked
    with pymupdf.open(locked[0]) as doc:
        assert doc.needs_pass
        assert not doc.authenticate("01011900")


def test_attachment_changed_after_approval_halts_batch(env):
    prepare(env)
    locked = sorted((pipeline.batch_dir(env.batch) / "locked").glob("*.pdf"))[0]
    locked.write_bytes(locked.read_bytes() + b"%tampered")
    result = pipeline.send(env.batch, "dina.maker")
    assert result["halted"] and result["sent"] == 0
    assert pipeline.load_state(env.batch)["status"] == "HALTED"
    assert not list((pipeline.batch_dir(env.batch) / "outbox").glob("*.eml"))


def test_manifest_changed_after_submission_blocks_approval(env):
    pipeline.validate(env.batch)
    pipeline.submit(env.batch, "dina.maker")
    mf = pipeline.batch_dir(env.batch) / "manifest.json"
    data = json.loads(mf.read_text())
    data[0]["to_email"] = "attacker@gmail.example"
    mf.write_text(json.dumps(data))
    with pytest.raises(pipeline.WorkflowError):
        pipeline.approve(env.batch, "sari.supervisor")


def test_dry_run_goes_only_to_qa_mailbox(env):
    prepare(env)
    pipeline.send(env.batch, "dina.maker", dry_run=True)
    emls = list((pipeline.batch_dir(env.batch) / "outbox_dryrun").glob("*.eml"))
    assert len(emls) == len(env.customers)
    for e in emls:
        text = e.read_text(errors="ignore")
        assert "To: qa.notification@nusantaralife.example" in text
        assert "Cc:" not in text
    assert pipeline.load_state(env.batch)["status"] == "APPROVED"


def test_sent_emails_are_proven_leak_free(env):
    prepare(env)
    pipeline.send(env.batch, "dina.maker")
    emails, matrix = reporting.verify_outbox(env.batch)
    assert len(emails) == len(env.customers)
    assert emails["safe"].all()
    assert not emails["nik_in_subject_or_body"].any()
    off_diagonal = matrix.values.sum() - matrix.values.diagonal().sum()
    assert off_diagonal == 0


def test_no_raw_pii_in_logs_or_reports(env):
    prepare(env)
    pipeline.send(env.batch, "dina.maker")
    assert reporting.scan_outputs_for_pii() == []


def test_sender_control_rejects_external_mailbox(monkeypatch):
    cfg = json.loads(json.dumps(mailer.settings()))
    cfg["sender"]["official_mailbox"] = "someone@gmail.example"
    monkeypatch.setattr(mailer, "settings", lambda: cfg)
    assert mailer.check_sender()


def test_sender_control_passes_for_official_mailbox():
    assert mailer.check_sender() == []
