from __future__ import annotations
from bs4 import BeautifulSoup
from urllib.parse import urlencode, urljoin
from property_scraper.common import parse_address, PropertyResult, result_from_record, clean_text
from property_scraper.http import HttpClient

BASE = "https://gis.vgsi.com/gloucesterva/"
SEARCH = urljoin(BASE, "Search.aspx")


def _table_to_record(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    rec = {}
    for tr in soup.find_all("tr"):
        cells = [clean_text(c.get_text(" ")) for c in tr.find_all(["td", "th"])]
        if len(cells) >= 2:
            rec[cells[0].strip(":")] = cells[1]
    text = clean_text(soup.get_text(" "))
    rec["page_text"] = text[:12000]
    return rec


def scrape(address: str, city: str = "gloucester", headed: bool = False) -> PropertyResult:
    p = parse_address(address, city)
    client = HttpClient()
    # VGSI supports search.aspx?SearchType=Location&Street=... on many installs; fallback to simple text search.
    queries = [p["normalized"], f'{p["number"]} {p["street_name"]}', p["street_name"]]
    for q in queries:
        try:
            r = client.get(SEARCH, params={"SearchType": "Location", "Street": q})
            if r.status_code >= 400:
                continue
            soup = BeautifulSoup(r.text, "html.parser")
            link = None
            for a in soup.find_all("a", href=True):
                if "Parcel.aspx" in a["href"]:
                    link = urljoin(BASE, a["href"])
                    break
            if link:
                pr = client.get(link)
                rec = _table_to_record(pr.text)
                return result_from_record(rec, city, link, p["normalized"], notes="Gloucester VGSI parcel page")
            # Sometimes direct parcel table appears
            rec = _table_to_record(r.text)
            res = result_from_record(rec, city, r.url, p["normalized"], notes="Gloucester VGSI search page")
            if res.status != "not_found":
                return res
        except Exception:
            continue
    return PropertyResult(status="not_found", city=city, normalized_address=p["normalized"], source_url=SEARCH, notes="No Gloucester/VGSI match")
