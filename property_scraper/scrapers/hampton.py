from __future__ import annotations
from property_scraper.common import parse_address, result_from_record, PropertyResult
from property_scraper.http import HttpClient

# Hampton CivQuest is ArcGIS-backed. These candidates are tried without browser automation.
CANDIDATE_QUERY_URLS = [
    "https://webgis3.hampton.gov/arcgis/rest/services/CivQuest/MapServer/0/query",
    "https://webgis3.hampton.gov/arcgis/rest/services/CivQuest/MapServer/1/query",
    "https://webgis3.hampton.gov/arcgis/rest/services/RealEstate/MapServer/0/query",
    "https://webgis3.hampton.gov/arcgis/rest/services/RealEstate/MapServer/1/query",
]


def _query_layer(client: HttpClient, url: str, q: str):
    params = {
        "f": "json",
        "where": f"UPPER(SITE_ADDRESS) LIKE '%{q.upper()}%' OR UPPER(ADDRESS) LIKE '%{q.upper()}%'",
        "outFields": "*",
        "returnGeometry": "false",
        "resultRecordCount": 10,
    }
    r = client.get(url, params=params)
    if r.status_code != 200:
        return []
    data = r.json()
    feats = data.get("features", [])
    return [f.get("attributes", {}) for f in feats]


def _score(record: dict, p: dict) -> int:
    hay = " ".join(str(v) for v in record.values()).upper()
    score = 0
    if p["number"] and p["number"] in hay: score += 5
    for token in p["street_name"].split():
        if token and token in hay: score += 2
    return score


def scrape(address: str, city: str = "hampton", headed: bool = False) -> PropertyResult:
    p = parse_address(address, city)
    client = HttpClient()
    q = f'{p["number"]} {p["street_name"]}'
    errors = []
    for url in CANDIDATE_QUERY_URLS:
        try:
            rows = _query_layer(client, url, q)
            if rows:
                rows = sorted(rows, key=lambda r: _score(r, p), reverse=True)
                return result_from_record(rows[0], city, url, p["normalized"], notes="Hampton REST/ArcGIS candidate match")
        except Exception as e:
            errors.append(f"{url}: {type(e).__name__} {e}")
    return PropertyResult(status="not_found", city=city, normalized_address=p["normalized"], source_url="https://webgis3.hampton.gov/civquest/", notes="No Hampton REST match. " + "; ".join(errors[:3]))
