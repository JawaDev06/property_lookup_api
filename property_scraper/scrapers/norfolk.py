from __future__ import annotations
from property_scraper.common import parse_address, result_from_record, PropertyResult, clean_text
from property_scraper.http import HttpClient

# Norfolk official Socrata dataset. If the city rotates resource IDs, add new IDs here.
DATASETS = [
    "g7sg-tivf",  # Property Assessment and Sales FY25, observed official Norfolk Open Data resource
]
BASE = "https://data.norfolk.gov"


def _score(record: dict, p: dict) -> int:
    hay = " ".join(str(v) for v in record.values()).upper()
    score = 0
    if p["number"] and p["number"] in hay: score += 5
    for token in p["street_name"].split():
        if token and token in hay: score += 2
    if p["suffix"] and p["suffix"] in hay: score += 1
    return score


def scrape(address: str, city: str = "norfolk", headed: bool = False) -> PropertyResult:
    p = parse_address(address, city)
    client = HttpClient()
    q = f'{p["number"]} {p["street_name"]}'
    best = None
    best_source = ""
    errors = []
    for ds in DATASETS:
        try:
            rows = client.socrata(BASE, ds, {"$limit": 25, "$q": q})
            if not rows and p["street_name"]:
                rows = client.socrata(BASE, ds, {"$limit": 25, "$q": p["street_name"]})
            if rows:
                rows = sorted(rows, key=lambda r: _score(r, p), reverse=True)
                best = rows[0]
                best_source = f"{BASE}/resource/{ds}.json"
                break
        except Exception as e:
            errors.append(f"{ds}: {type(e).__name__} {e}")
    if not best:
        return PropertyResult(status="not_found", city=city, normalized_address=p["normalized"], source_url=BASE, notes="Norfolk open data returned no match. " + "; ".join(errors))
    res = result_from_record(best, city, best_source, p["normalized"], notes="Norfolk official open data match")
    return res
