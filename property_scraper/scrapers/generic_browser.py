from __future__ import annotations
from bs4 import BeautifulSoup
from property_scraper.common import parse_address, variants, PropertyResult, result_from_record, clean_text

URLS = {
    "chesapeake": "https://chesapeake.civ.quest",
    "portsmouth": "http://data.portsmouthva.gov/assessor/data/realestatesearch.aspx",
    "suffolk": "https://property.spatialest.com/va/suffolk#/",
    "virginia beach": "https://propertysearch.virginiabeach.gov/#/",
    "james city county": "https://property.jamescitycountyva.gov/JamesCity/",
    "williamsburg": "https://property.spatialest.com/va/williamsburg#/",
    "poquoson": "https://www.geoplan.app/poquoson/",
    "yorktown": "https://maps.yorkcounty.gov",
}


def _record_from_page_text(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    rec = {}
    for tr in soup.find_all("tr"):
        cells = [clean_text(c.get_text(" ")) for c in tr.find_all(["td", "th"])]
        if len(cells) >= 2:
            rec[cells[0].strip(":")] = cells[1]
    # Generic definition lists/cards
    for label in soup.find_all(["dt", "strong", "b", "label", "span", "div"]):
        lab = clean_text(label.get_text(" "))
        if not lab or len(lab) > 60:
            continue
        nxt = label.find_next_sibling()
        if nxt:
            val = clean_text(nxt.get_text(" "))
            if val and len(val) < 120:
                rec.setdefault(lab.strip(":"), val)
    text = clean_text(soup.get_text(" "))
    rec["page_text"] = text[:20000]
    return rec


def _accept_terms(page):
    for label in ["Accept", "I Agree", "Agree", "Continue", "Enter", "OK", "Yes"]:
        try:
            btn = page.get_by_role("button", name=label, exact=False)
            if btn.count() > 0 and btn.first.is_visible(timeout=500):
                btn.first.click(timeout=2500)
                page.wait_for_timeout(1200)
                return
        except Exception:
            pass
        try:
            link = page.get_by_role("link", name=label, exact=False)
            if link.count() > 0 and link.first.is_visible(timeout=500):
                link.first.click(timeout=2500)
                page.wait_for_timeout(1200)
                return
        except Exception:
            pass


def _visible_inputs(page):
    selectors = [
        "input[type='search']:visible",
        "input[placeholder*='Search' i]:visible",
        "input[aria-label*='Search' i]:visible",
        "input[name*='search' i]:visible",
        "input[id*='search' i]:visible",
        "input[type='text']:visible",
        "textarea:visible",
    ]
    for sel in selectors:
        loc = page.locator(sel)
        try:
            if loc.count() > 0:
                return loc
        except Exception:
            continue
    return page.locator("input:visible")


def _search_once(page, q: str, p: dict) -> bool:
    inputs = _visible_inputs(page)
    if inputs.count() == 0:
        return False
    # Try first few visible inputs, not hidden Google translate fields.
    for i in range(min(inputs.count(), 5)):
        inp = inputs.nth(i)
        try:
            if not inp.is_visible(timeout=500):
                continue
            inp.click(timeout=1500)
            inp.fill(q, timeout=5000)
            page.keyboard.press("Enter")
            page.wait_for_timeout(3500)
            return True
        except Exception:
            continue
    return False


def _click_likely_result(page, p: dict):
    candidates = [
        f"text=/{p['number']}.*{p['street_name'].split()[0] if p['street_name'] else ''}/i",
        f"text=/{p['number']}/i",
    ]
    for sel in candidates:
        try:
            loc = page.locator(sel)
            if loc.count() > 0 and loc.first.is_visible(timeout=500):
                loc.first.click(timeout=2500)
                page.wait_for_timeout(3000)
                return
        except Exception:
            pass


def scrape(address: str, city: str, headed: bool = False) -> PropertyResult:
    p = parse_address(address, city)
    url = URLS.get(city, "")
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        return PropertyResult(status="error", city=city, normalized_address=p["normalized"], source_url=url, notes=f"Playwright unavailable: {e}")
    notes = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not headed)
        page = browser.new_page(viewport={"width": 1400, "height": 1000})
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(2500)
            _accept_terms(page)
            for q in variants(address, city):
                notes.append(f"tried:{q}")
                if not _search_once(page, q, p):
                    continue
                _click_likely_result(page, p)
                html = page.content()
                rec = _record_from_page_text(html)
                res = result_from_record(rec, city, page.url, p["normalized"], notes="; ".join(notes[-3:]))
                if res.status != "not_found":
                    browser.close()
                    return res
                # reload before next attempt on sticky single-page apps
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_timeout(1500)
                    _accept_terms(page)
                except Exception:
                    pass
        except Exception as e:
            browser.close()
            return PropertyResult(status="error", city=city, normalized_address=p["normalized"], source_url=url, notes=f"Browser lookup error: {type(e).__name__}: {e}; {'; '.join(notes)}")
        browser.close()
    return PropertyResult(status="not_found", city=city, normalized_address=p["normalized"], source_url=url, notes="No browser match. " + "; ".join(notes[:10]))
