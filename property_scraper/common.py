from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any, Optional
import re

CITY_ALIASES = {
    "newport news": ["newport news", "newportnews"],
    "hampton": ["hampton"],
    "james city county": ["james city county", "jcc", "williamsburg jcc"],
    "williamsburg": ["williamsburg"],
    "poquoson": ["poquoson"],
    "yorktown": ["yorktown", "york county"],
    "gloucester": ["gloucester", "hayes"],
    "hayes": ["hayes"],
    "chesapeake": ["chesapeake"],
    "norfolk": ["norfolk"],
    "portsmouth": ["portsmouth"],
    "suffolk": ["suffolk"],
    "virginia beach": ["virginia beach", "va beach", "vabeach"],
}
SUPPORTED_CITIES = tuple(CITY_ALIASES.keys())

SUFFIX_MAP = {
    "STREET": "ST", "ST": "ST", "AVENUE": "AVE", "AVE": "AVE", "ROAD": "RD", "RD": "RD",
    "DRIVE": "DR", "DR": "DR", "LANE": "LN", "LN": "LN", "COURT": "CT", "CT": "CT",
    "CIRCLE": "CIR", "CIR": "CIR", "BOULEVARD": "BLVD", "BLVD": "BLVD", "PARKWAY": "PKWY", "PKWY": "PKWY",
    "PLACE": "PL", "PL": "PL", "TERRACE": "TER", "TER": "TER", "WAY": "WAY", "TRAIL": "TRL", "TRL": "TRL",
    "HIGHWAY": "HWY", "HWY": "HWY", "TURNPIKE": "TPKE", "TPKE": "TPKE", "PIKE": "PIKE", "COVE": "CV", "CV": "CV",
}
SUFFIXES = set(SUFFIX_MAP.keys()) | set(SUFFIX_MAP.values())
NON_ADDRESS_PAT = re.compile(r"\b(windows?|roof|siding|hvac|kit:|bath floor|paint|lights|doors|demo|drywall|sold\b|irs|ror)\b", re.I)

@dataclass
class PropertyResult:
    status: str = "not_found"
    assessed_value: Optional[float] = None
    sqft: Optional[float] = None
    year_built: Optional[int] = None
    beds: Optional[float] = None
    baths: Optional[float] = None
    source_url: str = ""
    notes: str = ""
    city: Optional[str] = None
    normalized_address: str = ""
    raw: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    s = str(value).replace("\xa0", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def is_probable_address(s: str) -> bool:
    s = clean_text(s)
    if not s or s.lower() == "address":
        return False
    if NON_ADDRESS_PAT.search(s):
        return False
    return bool(re.match(r"^\s*\d{1,6}\b", s))


def detect_city(address: str) -> Optional[str]:
    low = clean_text(address).lower()
    choices = []
    for city, aliases in CITY_ALIASES.items():
        for alias in aliases:
            choices.append((len(alias), city, alias))
    for _, city, alias in sorted(choices, reverse=True):
        if re.search(rf"\b{re.escape(alias)}\b", low):
            if city == "hayes":
                return "gloucester"
            return city
    return None


def strip_city(address: str, city: Optional[str]) -> str:
    """Remove city only when it appears as a trailing locality, not when it is part of a street name.

    Example fixed from v9: "225 Hampton Roads Ave Hampton" now keeps "Hampton Roads Ave".
    """
    s = clean_text(address)
    s = re.sub(r"\bVA\b|\bVIRGINIA\b|,", " ", s, flags=re.I)
    s = clean_text(s)
    if not city:
        return s
    aliases = CITY_ALIASES.get(city, []) + (["hayes"] if city == "gloucester" else [])
    for alias in sorted(aliases, key=len, reverse=True):
        # remove only as terminal words, optionally followed by state/zip already stripped
        s2 = re.sub(rf"\s+{re.escape(alias)}\s*$", "", s, flags=re.I)
        if s2 != s:
            return clean_text(s2)
    return s


def parse_address(address: str, city: Optional[str] = None) -> dict[str, Any]:
    raw = clean_text(address)
    city = city or detect_city(raw)
    s = strip_city(raw, city).upper()
    # If two addresses are in one cell, use the first one; log normalized result in col U.
    if " AND " in s or "&" in s:
        s = re.split(r"\s+(?:AND|&)\s+", s, maxsplit=1)[0]
    s = re.sub(r"[^A-Z0-9\s#.-]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    m = re.match(r"^(\d+[A-Z]?)\s+(.+)$", s)
    number = m.group(1) if m else ""
    street_full = m.group(2) if m else s
    unit = ""
    street_full = re.sub(r"\b(APT|UNIT|STE|SUITE|#)\s*([A-Z0-9-]+)\b", lambda x: "", street_full).strip()
    words = street_full.split()
    suffix = ""
    if words and words[-1] in SUFFIXES:
        suffix = SUFFIX_MAP.get(words[-1], words[-1])
        street_name = " ".join(words[:-1])
    else:
        street_name = street_full
    normalized = clean_text(f"{number} {street_name} {suffix}".upper())
    return {"raw": raw, "city": city, "number": number, "street_name": street_name, "suffix": suffix, "normalized": normalized, "unit": unit}


def variants(address: str, city: Optional[str] = None) -> list[str]:
    p = parse_address(address, city)
    number, name, suffix = p["number"], p["street_name"], p["suffix"]
    out = []
    def add(x: str):
        x = clean_text(x.upper())
        if x and x not in out:
            out.append(x)
    add(f"{number} {name} {suffix}")
    long_by_short = {v: k for k, v in SUFFIX_MAP.items() if len(k) > len(v)}
    if suffix in long_by_short:
        add(f"{number} {name} {long_by_short[suffix]}")
    add(f"{number} {name}")
    if city:
        add(f"{number} {name} {suffix} {city}")
        add(f"{number} {name} {city}")
    return out


def num(value: Any) -> Optional[float]:
    s = clean_text(value)
    if not s:
        return None
    m = re.search(r"-?\d[\d,]*(?:\.\d+)?", s)
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


def money(value: Any) -> Optional[float]:
    return num(value)


def year(value: Any) -> Optional[int]:
    s = clean_text(value)
    m = re.search(r"\b(18\d{2}|19\d{2}|20\d{2})\b", s)
    return int(m.group(1)) if m else None


def _normalize_key(k: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(k).lower()).strip()


def choose_first(record: dict[str, Any], names: list[str]) -> Any:
    # Prefer structured columns over page_text and exact/near-exact field names.
    items = [(k, v) for k, v in record.items() if _normalize_key(k) != "page text"]
    norm = [(_normalize_key(k), v) for k, v in items]
    for want in names:
        w = _normalize_key(want)
        for k, v in norm:
            if k == w:
                return v
        for k, v in norm:
            if w in k:
                return v
    return None


def _regex_after(text: str, labels: list[str], money_mode=False, integer=False) -> Optional[float | int]:
    if not text:
        return None
    for label in labels:
        pat = rf"{label}[^$0-9]{{0,80}}(\$?\s*[0-9][0-9,]*(?:\.\d+)?)"
        m = re.search(pat, text, flags=re.I)
        if m:
            val = num(m.group(1))
            if val is not None:
                return int(val) if integer else val
    return None


def result_from_record(record: dict[str, Any], city: str, source_url: str, normalized: str, notes: str = "") -> PropertyResult:
    text = clean_text(record.get("page_text", ""))
    assessed = money(choose_first(record, [
        "total assessed value", "current total value", "current total assessed", "total assessment",
        "assessment", "assessed", "total value", "land and building", "appraised value", "value total", "value"
    ]))
    sqft = num(choose_first(record, [
        "living area", "finished living area", "heated area", "residential area", "building square feet",
        "building sqft", "total living area", "sqft", "square feet", "gross living area", "improvement area"
    ]))
    yr = year(choose_first(record, ["year built", "built year", "yr built", "actual year built", "effective year built", "year"] ))
    beds = num(choose_first(record, ["bedrooms", "beds", "br", "bedroom count"] ))
    baths = num(choose_first(record, ["bathrooms", "baths", "bath", "bath count", "total baths"] ))

    # Fallback from page text for browser pages where labels are not table cells.
    if assessed is None:
        assessed = _regex_after(text, ["Total Assessed Value", "Total Assessment", "Current Total Value", "Assessed Value", "Total Value"])
    if sqft is None:
        sqft = _regex_after(text, ["Living Area", "Finished Area", "Building Square Feet", "Square Feet", "Sq Ft", "Gross Living Area"])
    if yr is None:
        yy = _regex_after(text, ["Year Built", "Built"], integer=True)
        yr = int(yy) if yy and 1800 <= int(yy) <= 2100 else None
    if beds is None:
        beds = _regex_after(text, ["Bedrooms", "Beds", "BR"])
    if baths is None:
        baths = _regex_after(text, ["Bathrooms", "Baths", "Total Baths"])

    # Guardrails: old versions sometimes parsed parcel counts or rows as sqft.
    if sqft is not None and sqft < 100:
        sqft = None
    if beds is not None and beds > 20:
        beds = None
    if baths is not None and baths > 20:
        baths = None
    if assessed is not None and assessed < 1000:
        assessed = None

    status = "complete" if all(v is not None for v in [assessed, sqft, yr, beds, baths]) else "partial"
    if not any(v is not None for v in [assessed, sqft, yr, beds, baths]):
        status = "not_found"
    return PropertyResult(status=status, assessed_value=assessed, sqft=sqft, year_built=yr, beds=beds, baths=baths, source_url=source_url, notes=notes, city=city, normalized_address=normalized, raw=record)
