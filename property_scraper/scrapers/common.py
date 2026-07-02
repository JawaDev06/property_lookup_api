import re
from typing import Optional
from bs4 import BeautifulSoup
from property_scraper.models import PropertyResult

MONEY_RE = re.compile(r"\$?\s*([0-9]{1,3}(?:,[0-9]{3})+(?:\.\d+)?|[0-9]+(?:\.\d+)?)")
NUM_RE = re.compile(r"([0-9]{1,3}(?:,[0-9]{3})+|[0-9]+(?:\.\d+)?)")
YEAR_RE = re.compile(r"\b(18\d{2}|19\d{2}|20\d{2})\b")

def clean_num(v):
    if v is None: return None
    try:
        return float(str(v).replace('$','').replace(',','').strip())
    except Exception:
        return None

def clean_int(v):
    n = clean_num(v)
    return int(n) if n is not None else None

def text_from_html(html: str) -> str:
    soup = BeautifulSoup(html or "", "lxml")
    return soup.get_text("\n", strip=True)

def find_after_label(text: str, labels):
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    for i, line in enumerate(lines):
        low = line.lower()
        for label in labels:
            if label.lower() in low:
                # same line
                tail = re.sub(re.escape(label), "", line, flags=re.I).strip(" :\t")
                if tail:
                    return tail
                # next non-empty line
                if i + 1 < len(lines):
                    return lines[i+1]
    return None

def parse_generic_fields(html: str, address: str, city: str, source_url: str) -> PropertyResult:
    text = text_from_html(html)
    r = PropertyResult(address=address, city=city, source_url=source_url, status="partial")
    val = find_after_label(text, ["Total Assessed", "Total Assessment", "Assessed Value", "Total Value", "Current Assessment"])
    if val:
        m = MONEY_RE.search(val); r.assessed_value = clean_num(m.group(1)) if m else None
    sqft = find_after_label(text, ["Living Area", "Building Area", "Finished Area", "Square Feet", "Sq Ft", "Total Living"])
    if sqft:
        m = NUM_RE.search(sqft); r.sqft = clean_num(m.group(1)) if m else None
        if r.sqft is not None and r.sqft < 200: r.sqft = None
    yb = find_after_label(text, ["Year Built", "Built"])
    if yb:
        m = YEAR_RE.search(yb); r.year_built = int(m.group(1)) if m else None
    beds = find_after_label(text, ["Bedrooms", "Beds", "Bed Rooms"])
    if beds:
        m = NUM_RE.search(beds); r.beds = clean_num(m.group(1)) if m else None
    baths = find_after_label(text, ["Total Baths", "Bathrooms", "Baths", "Full Baths"])
    if baths:
        m = NUM_RE.search(baths); r.baths = clean_num(m.group(1)) if m else None
    filled = [r.assessed_value, r.sqft, r.year_built, r.beds, r.baths]
    r.status = "complete" if all(x is not None for x in filled) else ("partial" if any(x is not None for x in filled) else "not_found")
    if r.status == "not_found":
        r.notes = "No parseable official fields found. Site may need a dedicated parser, API endpoint, or exported data feed."
    else:
        missing = []
        for name, val2 in [("assessed_value", r.assessed_value),("sqft", r.sqft),("year_built", r.year_built),("beds", r.beds),("baths", r.baths)]:
            if val2 is None: missing.append(name)
        r.notes = "Missing: " + ", ".join(missing) if missing else "OK"
    return r
