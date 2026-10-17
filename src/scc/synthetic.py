"""Generate fully synthetic master data, monthly send lists and PDF letters.

Realistic operational defects are injected on purpose and written to a
ground-truth file, so the controls can be proven to catch every one of them.
"""

from __future__ import annotations

import shutil
from datetime import date, timedelta

import numpy as np
import pandas as pd

from . import DATA_DIR, settings
from .letters import render_letter

BRANCHES = [
    # code, name, province code used for NIK
    ("JKT", "Jakarta Head Office", "31"),
    ("BDG", "Bandung", "32"),
    ("SBY", "Surabaya", "35"),
    ("MDN", "Medan", "12"),
    ("MKS", "Makassar", "73"),
    ("YGY", "Yogyakarta", "34"),
]

FIRST = ["Andi", "Budi", "Citra", "Dewi", "Eko", "Fajar", "Gita", "Hendra", "Indah", "Joko",
         "Kartika", "Lestari", "Maya", "Nanda", "Oki", "Putri", "Rizky", "Sari", "Taufik", "Utami",
         "Vina", "Wahyu", "Yuni", "Zaki", "Agus", "Bayu", "Dimas", "Fitri", "Gilang", "Hana",
         "Irfan", "Laras", "Mega", "Nur", "Rina", "Surya", "Tika", "Wulan", "Yoga", "Rahmat"]
LAST = ["Santoso", "Wijaya", "Saputra", "Lestari", "Pratama", "Hidayat", "Nugroho", "Kusuma",
        "Siregar", "Nasution", "Harahap", "Wibowo", "Setiawan", "Gunawan", "Rahayu", "Purnomo",
        "Halim", "Susanto", "Hakim", "Permana", "Syahputra", "Utomo", "Firmansyah", "Ramadhan",
        "Simanjuntak", "Sitompul", "Tanjung", "Daeng", "Pane", "Marpaung"]
STREETS = ["Jl. Merdeka", "Jl. Sudirman", "Jl. Diponegoro", "Jl. Gatot Subroto", "Jl. Ahmad Yani",
           "Jl. Pahlawan", "Jl. Veteran", "Jl. Pemuda", "Jl. Kartini", "Jl. Cendana"]
# Every address uses the reserved .example TLD (RFC 2606): it can never be delivered to a real person
DOMAINS = ["gmail.example", "yahoo.example", "outlook.example", "gmail.example", "gmail.example"]

BATCHES = ["2026-08", "2026-09", "2026-10"]
BATCH_SIZE = 150
N_CUSTOMERS = 900
SEED = 20261017

DEFECTS = {
    # name: expected control
    "SWAPPED_CONTENT": "DP-04",
    "NIK_MISMATCH": "DP-04",
    "MISSING_LETTER": "DP-01",
    "DUPLICATE_LETTER": "DP-02",
    "AMBIGUOUS_FILENAME": "DP-03",
    "ORPHAN_LETTER": "DP-05",
    "STALE_EMAIL": "DP-06",
    "EMAIL_DOMAIN_TYPO": "DP-06",
    "WRONG_BRANCH_CODE": "DP-07",
    "EXTERNAL_CC_OVERRIDE": "DP-07",
    "MULTI_RECIPIENT": "DP-08",
    "NIK_IN_FILENAME": "DP-10",
}


def _nik(rng, province: str, dob: date, female: bool) -> str:
    city = f"{rng.integers(1, 30):02d}"
    district = f"{rng.integers(1, 40):02d}"
    day = dob.day + (40 if female else 0)
    serial = f"{rng.integers(1, 9999):04d}"
    return f"{province}{city}{district}{day:02d}{dob.month:02d}{dob.year % 100:02d}{serial}"


def build_master(rng) -> tuple[pd.DataFrame, pd.DataFrame]:
    domain = settings()["company"]["domain"]
    branches = pd.DataFrame(
        [{"branch_code": c, "branch_name": n, "branch_email": f"branch.{c.lower()}@{domain}"}
         for c, n, _ in BRANCHES]
    )
    rows, used_policies, used_emails = [], set(), set()
    for _ in range(N_CUSTOMERS):
        code, bname, prov = BRANCHES[rng.integers(0, len(BRANCHES))]
        first, last = FIRST[rng.integers(0, len(FIRST))], LAST[rng.integers(0, len(LAST))]
        female = bool(rng.integers(0, 2))
        dob = date(1960, 1, 1) + timedelta(days=int(rng.integers(0, 365 * 40)))
        policy = f"77{rng.integers(0, 10**8):08d}"
        while policy in used_policies:
            policy = f"77{rng.integers(0, 10**8):08d}"
        used_policies.add(policy)
        email = f"{first.lower()}.{last.lower()}{rng.integers(1, 999)}@{DOMAINS[rng.integers(0, len(DOMAINS))]}"
        while email in used_emails:
            email = f"{first.lower()}.{last.lower()}{rng.integers(1, 9999)}@gmail.example"
        used_emails.add(email)
        rows.append({
            "policy_no": policy,
            "name": f"{first} {last}",
            "nik": _nik(rng, prov, dob, female),
            "dob": dob.isoformat(),
            "email": email,
            "branch_code": code,
            "address": f"{STREETS[rng.integers(0, len(STREETS))]} No. {rng.integers(1, 200)}, {bname}",
        })
    return pd.DataFrame(rows), branches


def _letter_payload(cust: pd.Series, branches: pd.DataFrame, letter_type: str, batch: str, rng) -> dict:
    bname = branches.set_index("branch_code").loc[cust["branch_code"], "branch_name"]
    y, m = map(int, batch.split("-"))
    return {
        "letter_type": letter_type,
        "ref_no": f"NL/{letter_type[:3]}/{batch.replace('-', '')}/{cust['policy_no'][-6:]}",
        "letter_date": date(y, m, 5).strftime("%d %B %Y"),
        "name": cust["name"],
        "policy_no": cust["policy_no"],
        "nik": cust["nik"],
        "address": cust["address"],
        "branch_name": bname,
        "due_date": date(y, m, 28).strftime("%d %B %Y"),
        "amount": f"{int(rng.integers(5, 400)) * 250_000:,}".replace(",", "."),
        "account_masked": f"****{rng.integers(1000, 9999)}",
    }


def _filename(letter_type: str, policy: str, batch: str) -> str:
    return f"{letter_type}_{policy}_{batch.replace('-', '')}.pdf"


def generate(clean: bool = True) -> dict:
    rng = np.random.default_rng(SEED)
    if clean and DATA_DIR.exists():
        shutil.rmtree(DATA_DIR)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    customers, branches = build_master(rng)
    customers.to_csv(DATA_DIR / "customers_master.csv", index=False)
    branches.to_csv(DATA_DIR / "branches_master.csv", index=False)
    cust_by_policy = customers.set_index("policy_no")
    letter_types = list(settings()["letter_types"])

    truth = []
    for batch in BATCHES:
        bdir = DATA_DIR / "batches" / batch
        ldir = bdir / "letters"
        ldir.mkdir(parents=True, exist_ok=True)

        sample = customers.sample(BATCH_SIZE + 1, random_state=int(rng.integers(0, 1_000_000)))
        orphan_cust = sample.iloc[-1]
        sample = sample.iloc[:-1].copy()
        send = pd.DataFrame({
            "batch_id": batch,
            "policy_no": sample["policy_no"].values,
            "customer_name": sample["name"].values,
            "email": sample["email"].values,
            "branch_code": sample["branch_code"].values,
            "letter_type": [letter_types[i] for i in rng.integers(0, 3, len(sample))],
            "cc_override": "",
        })

        # Pick distinct rows for each defect; 1-2 occurrences per defect per batch
        idx = list(rng.permutation(len(send)))
        plan: dict[str, list[int]] = {}
        for defect in DEFECTS:
            if defect == "ORPHAN_LETTER":
                continue
            k = int(rng.integers(1, 3)) if defect in ("SWAPPED_CONTENT", "STALE_EMAIL", "MISSING_LETTER") else 1
            plan[defect] = [idx.pop() for _ in range(k)]
        ambiguous_partner = idx.pop()
        swap_sources = [idx.pop() for _ in plan["SWAPPED_CONTENT"]]

        def add_truth(i_or_policy, defect, control=None):
            policy = i_or_policy if isinstance(i_or_policy, str) else send.at[i_or_policy, "policy_no"]
            truth.append({"batch_id": batch, "policy_no": policy, "defect": defect,
                          "expected_control": control or DEFECTS[defect]})

        # --- send-list defects
        for i in plan["STALE_EMAIL"]:
            old = send.at[i, "email"]
            send.at[i, "email"] = old.replace("@", ".old@")
            add_truth(i, "STALE_EMAIL")
        for i in plan["EMAIL_DOMAIN_TYPO"]:
            typo = send.at[i, "email"].split("@")[0] + "@gmial.example"
            send.at[i, "email"] = typo  # keyed in wrongly on the send list
            add_truth(i, "EMAIL_DOMAIN_TYPO")
        for i in plan["WRONG_BRANCH_CODE"]:
            current = send.at[i, "branch_code"]
            send.at[i, "branch_code"] = next(c for c, _, _ in BRANCHES if c != current)
            add_truth(i, "WRONG_BRANCH_CODE")
        for i in plan["EXTERNAL_CC_OVERRIDE"]:
            send.at[i, "cc_override"] = f"{send.at[i, 'branch_code'].lower()}.staff@gmail.example"
            add_truth(i, "EXTERNAL_CC_OVERRIDE")
        for i in plan["MULTI_RECIPIENT"]:
            other = customers.sample(1, random_state=int(rng.integers(0, 10**6))).iloc[0]["email"]
            send.at[i, "email"] = f"{send.at[i, 'email']}; {other}"
            add_truth(i, "MULTI_RECIPIENT")

        # --- letters
        skip = set(plan["MISSING_LETTER"])
        for i in skip:
            add_truth(i, "MISSING_LETTER")
        for i, row in send.iterrows():
            if i in skip:
                continue
            cust = cust_by_policy.loc[row["policy_no"]].copy()
            cust["policy_no"] = row["policy_no"]
            payload = _letter_payload(cust, branches, row["letter_type"], batch, rng)
            fname = _filename(row["letter_type"], row["policy_no"], batch)

            if i in plan["SWAPPED_CONTENT"]:
                src = send.at[swap_sources[plan["SWAPPED_CONTENT"].index(i)], "policy_no"]
                other = cust_by_policy.loc[src].copy()
                other["policy_no"] = src
                payload = _letter_payload(other, branches, row["letter_type"], batch, rng)
                add_truth(i, "SWAPPED_CONTENT")
            if i in plan["NIK_MISMATCH"]:
                payload["nik"] = customers.sample(1, random_state=int(rng.integers(0, 10**6))).iloc[0]["nik"]
                add_truth(i, "NIK_MISMATCH")
            if i in plan["AMBIGUOUS_FILENAME"]:
                partner = send.at[ambiguous_partner, "policy_no"]
                fname = f"{row['letter_type']}_{row['policy_no']}_REF{partner}_{batch.replace('-', '')}.pdf"
                add_truth(i, "AMBIGUOUS_FILENAME")
                add_truth(partner, "AMBIGUOUS_FILENAME_PARTNER_HELD", "DP-03")
            if i in plan["NIK_IN_FILENAME"]:
                fname = f"{row['letter_type']}_{row['policy_no']}_{cust['nik']}_{batch.replace('-', '')}.pdf"
                add_truth(i, "NIK_IN_FILENAME")

            render_letter(ldir / fname, payload)
            if i in plan["DUPLICATE_LETTER"]:
                render_letter(ldir / fname.replace(".pdf", "_revised.pdf"), payload)
                add_truth(i, "DUPLICATE_LETTER")

        # Orphan: a letter for a customer who is NOT on this month's send list
        o = orphan_cust.copy()
        render_letter(ldir / _filename("MATURITY", o["policy_no"], batch),
                      _letter_payload(o, branches, "MATURITY", batch, rng))
        add_truth(o["policy_no"], "ORPHAN_LETTER")

        send.to_excel(bdir / "send_list.xlsx", index=False)

    gt = pd.DataFrame(truth)
    gt.to_csv(DATA_DIR / "ground_truth_defects.csv", index=False)
    return {"customers": len(customers), "batches": BATCHES, "defects": len(gt)}


if __name__ == "__main__":
    print(generate())
