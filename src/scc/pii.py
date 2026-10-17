"""Personal data helpers: NIK validation, masking and detection."""

from __future__ import annotations

import difflib
import re

# Dukcapil province codes (first two digits of a NIK)
PROVINCE_CODES = {
    "11", "12", "13", "14", "15", "16", "17", "18", "19", "21",
    "31", "32", "33", "34", "35", "36", "51", "52", "53",
    "61", "62", "63", "64", "65", "71", "72", "73", "74", "75", "76",
    "81", "82", "91", "92", "93", "94", "95", "96", "97",
}

NIK_RE = re.compile(r"(?<!\d)(\d{16})(?!\d)")
# A NIK in full (16 digits) or in its masked form (4 digits + 8 '*' or 'x' + 4 digits)
NIK_LIKE_RE = re.compile(r"(?<![\dxX*])(\d{16}|\d{4}[xX*]{8}\d{4})(?![\dxX*])")
POLICY_RE = re.compile(r"(?<!\d)(\d{10})(?!\d)")
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")

COMMON_EMAIL_DOMAINS = [
    "gmail.com", "yahoo.com", "yahoo.co.id", "outlook.com", "hotmail.com",
    "icloud.com", "ymail.com", "live.com",
    # synthetic-data equivalents on the reserved .example TLD
    "gmail.example", "yahoo.example", "outlook.example",
]


def is_valid_nik(value: str) -> bool:
    """Structural NIK check: province code, birth day (+40 for female), month, serial."""
    if not re.fullmatch(r"\d{16}", value or ""):
        return False
    if value[:2] not in PROVINCE_CODES:
        return False
    day, month = int(value[6:8]), int(value[8:10])
    if day > 40:
        day -= 40
    return 1 <= day <= 31 and 1 <= month <= 12 and value[12:] != "0000"


def mask_nik(nik: str) -> str:
    nik = str(nik)
    if len(nik) != 16:
        return "*" * len(nik)
    return f"{nik[:4]}{'*' * 8}{nik[-4:]}"


def mask_name(name: str) -> str:
    """'Budi Wijaya' -> 'Budi W*****': first name kept, later names reduced to an initial."""
    parts = str(name).split()
    return " ".join([parts[0]] + [p[0] + "*" * (len(p) - 1) for p in parts[1:]])


def mask_street(street: str) -> str:
    """'Jl. Merdeka' -> 'Jl. M******'."""
    prefix, _, rest = str(street).partition(" ")
    return f"{prefix} {rest[0]}{'*' * (len(rest) - 1)}" if rest else "*" * len(prefix)


def mask_email(email: str) -> str:
    email = str(email).strip()
    if "@" not in email:
        return "***"
    user, domain = email.split("@", 1)
    return f"{user[:1]}***@{domain}"


def mask_policy(policy: str) -> str:
    policy = str(policy)
    return "*" * max(len(policy) - 4, 0) + policy[-4:]


def redact_niks(text: str) -> str:
    """Mask every 16-digit run (e.g. a NIK inside a file name) before it reaches a log or report."""
    return NIK_RE.sub(lambda m: mask_nik(m.group(1)), str(text))


def find_niks(text: str) -> list[str]:
    """Any 16-digit run is treated as a potential NIK (sensitive either way)."""
    return NIK_RE.findall(text or "")


def find_nik_like(text: str) -> list[str]:
    """Full or masked NIK patterns, e.g. inside a file name (DP-10)."""
    return NIK_LIKE_RE.findall(text or "")


def policy_candidates(text: str) -> list[str]:
    return POLICY_RE.findall(text or "")


def is_single_valid_email(value: str) -> bool:
    return bool(EMAIL_RE.match(str(value).strip()))


def domain_typo(email: str) -> str | None:
    """Return the domain it probably meant, if the domain looks like a typo of a common one."""
    if "@" not in str(email):
        return None
    domain = email.rsplit("@", 1)[1].lower().strip()
    if domain in COMMON_EMAIL_DOMAINS:
        return None
    close = difflib.get_close_matches(domain, COMMON_EMAIL_DOMAINS, n=1, cutoff=0.8)
    return close[0] if close else None


def normalize_name(name: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z ]", "", str(name).upper())).strip()
