import re
from typing import Optional, Tuple

CITY_ALIASES = {
    "newport news": ["newport news", "nnva"],
    "hampton": ["hampton"],
    "norfolk": ["norfolk"],
    "portsmouth": ["portsmouth"],
    "chesapeake": ["chesapeake"],
    "suffolk": ["suffolk"],
    "virginia beach": ["virginia beach", "va beach", "vabeach"],
    "gloucester": ["gloucester"],
    "hayes": ["hayes"],
    "james city county": ["james city county", "jcc"],
    "williamsburg": ["williamsburg"],
    "yorktown": ["yorktown", "york county"],
    "poquoson": ["poquoson"],
}

SUFFIX_MAP = {
    "AVENUE": "AVE", "AVE": "AVE",
    "STREET": "ST", "ST": "ST",
    "ROAD": "RD", "RD": "RD",
    "DRIVE": "DR", "DR": "DR",
    "LANE": "LN", "LN": "LN",
    "COURT": "CT", "CT": "CT",
    "CIRCLE": "CIR", "CIR": "CIR",
    "PARKWAY": "PKWY", "PKWY": "PKWY",
    "BOULEVARD": "BLVD", "BLVD": "BLVD",
    "PLACE": "PL", "PL": "PL",
    "TERRACE": "TER", "TER": "TER",
    "TRAIL": "TRL", "TRL": "TRL",
    "WAY": "WAY",
}

NON_ADDRESS_PATTERNS = [
    r"^address$", r"^sold\b", r"windows:", r"roof:", r"hvac:", r"siding:", r"paint:",
    r"irs ror", r"demo", r"drywall", r"^notes?$"
]

def is_probable_address(value: str) -> bool:
    if not value:
        return False
    s = str(value).strip().lower()
    if any(re.search(p, s) for p in NON_ADDRESS_PATTERNS):
        return False
    return bool(re.match(r"^\s*\d+\s+[a-z0-9]", s))

def clean_text(value: str) -> str:
    s = str(value or "").replace("&", " AND ")
    s = re.sub(r"[,#].*$", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def detect_city(address: str) -> Tuple[Optional[str], str]:
    s = clean_text(address)
    lower = s.lower()
    found = None
    found_alias = None
    # Longest aliases first so Newport News beats News, James City County beats City.
    aliases = []
    for city, vals in CITY_ALIASES.items():
        for a in vals:
            aliases.append((city, a))
    for city, alias in sorted(aliases, key=lambda x: len(x[1]), reverse=True):
        if re.search(r"\b" + re.escape(alias) + r"\b", lower):
            found = city
            found_alias = alias
            break
    if found_alias:
        s = re.sub(r"\b" + re.escape(found_alias) + r"\b", "", s, flags=re.I)
        s = re.sub(r"\s+", " ", s).strip()
    return found, s

def normalize_street(street: str) -> str:
    s = clean_text(street).upper()
    s = re.sub(r"[^A-Z0-9\s]", " ", s)
    parts = [p for p in s.split() if p]
    out = []
    for p in parts:
        # do not normalize HAMPTON in HAMPTON ROADS when city removed incorrectly; city removal is word-based before this
        out.append(SUFFIX_MAP.get(p, p))
    return " ".join(out)

def parse_address(address: str):
    city, street = detect_city(address)
    normalized = normalize_street(street)
    return {"original": str(address or ""), "city": city, "street": street, "normalized": normalized}

def variants(normalized: str):
    vals = []
    if normalized:
        vals.append(normalized)
        tokens = normalized.split()
        if len(tokens) >= 3 and tokens[-1] in set(SUFFIX_MAP.values()):
            vals.append(" ".join(tokens[:-1]))
    # preserve order unique
    seen = set(); out=[]
    for v in vals:
        if v and v not in seen:
            out.append(v); seen.add(v)
    return out
