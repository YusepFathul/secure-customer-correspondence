"""Each test injects one real-world mistake and checks the right control holds the letter."""

from conftest import payload
from scc.controls import validate_batch
from scc.letters import render_letter
import scc.pipeline as pipeline


def run(env):
    send, customers, branches = pipeline.load_inputs(env.batch)
    results, orphans = validate_batch(send, customers, branches, env.letters)
    return {r.policy_no: r for r in results}, orphans


def controls(result):
    return {f.control_id for f in result.findings}


def test_clean_batch_is_ready(env):
    results, orphans = run(env)
    assert all(r.status == "READY" for r in results.values())
    assert orphans == []


def test_swapped_letter_is_held(env):
    c1, c2 = env.customers[0], env.customers[1]
    render_letter(env.letters / f"MATURITY_{c1[0]}_209901.pdf", payload(c2))  # c1's file, c2's content
    results, _ = run(env)
    assert "DP-04" in controls(results[c1[0]])


def test_foreign_nik_is_held(env):
    c1 = env.customers[0]
    p = payload(c1)
    p["nik"] = env.customers[3][2]
    render_letter(env.letters / f"MATURITY_{c1[0]}_209901.pdf", p)
    results, _ = run(env)
    assert "DP-04" in controls(results[c1[0]])


def test_missing_duplicate_and_orphan(env):
    c1, c2 = env.customers[0], env.customers[1]
    (env.letters / f"MATURITY_{c1[0]}_209901.pdf").unlink()
    render_letter(env.letters / f"MATURITY_{c2[0]}_209901_v2.pdf", payload(c2))
    render_letter(env.letters / "MATURITY_7799999999_209901.pdf", payload(c2) | {"policy_no": "7799999999"})
    results, orphans = run(env)
    assert "DP-01" in controls(results[c1[0]])
    assert "DP-02" in controls(results[c2[0]])
    assert [o["control_id"] for o in orphans] == ["DP-05"]


def test_ambiguous_file_name_holds_both_customers(env):
    c1, c2 = env.customers[0], env.customers[1]
    (env.letters / f"MATURITY_{c1[0]}_209901.pdf").rename(env.letters / f"MATURITY_{c1[0]}_REF{c2[0]}.pdf")
    results, _ = run(env)
    assert "DP-03" in controls(results[c1[0]])
    assert "DP-03" in controls(results[c2[0]])


def test_recipient_and_branch_mistakes(env):
    send = env.send_list.copy()
    send.loc[0, "email"] = "customer.0001.old@gmail.example"                                   # stale email
    send.loc[1, "branch_code"] = "SBY"                                             # wrong branch
    send.loc[2, "cc_override"] = "sby.staff@gmail.example"                             # manual external CC
    send.loc[3, "email"] = "customer.0004@gmail.example; customer.0099@gmail.example"         # two recipients
    send.loc[4, "email"] = "customer.0005@gmial.example"                                 # domain typo
    env.save_send(send)
    results, _ = run(env)
    c = env.customers
    assert "DP-06" in controls(results[c[0][0]])
    assert "DP-07" in controls(results[c[1][0]])
    assert "DP-07" in controls(results[c[2][0]])
    assert "DP-08" in controls(results[c[3][0]])
    assert "DP-06" in controls(results[c[4][0]])


def test_branch_cc_always_comes_from_master(env):
    results, _ = run(env)
    for c in env.customers:
        assert results[c[0]].cc_email == f"branch.{c[5].lower()}@nusantaralife.example"


def test_nik_in_file_name_is_held(env):
    c1 = env.customers[0]
    (env.letters / f"MATURITY_{c1[0]}_209901.pdf").rename(env.letters / f"MATURITY_{c1[0]}_NIK{c1[2].replace('*', 'x')}.pdf")
    results, _ = run(env)
    assert "DP-10" in controls(results[c1[0]])
