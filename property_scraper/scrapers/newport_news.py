from __future__ import annotations
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re
from property_scraper.common import parse_address, PropertyResult, result_from_record, clean_text, variants
from property_scraper.http import HttpClient

URL = "https://assessment.nnva.gov/PT/search/commonsearch.aspx?mode=address"
BASE = "https://assessment.nnva.gov/PT/"


def _hidden_fields(soup):
    data = {}
    for inp in soup.find_all("input"):
        name = inp.get("name")
        if name:
            data[name] = inp.get("value", "")
    return data


def _record_from_html(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    rec = {}
    for tr in soup.find_all("tr"):
        cells = [clean_text(c.get_text(" ")) for c in tr.find_all(["td", "th"])]
        if len(cells) >= 2:
            rec[cells[0].strip(":")] = cells[1]
    for label in soup.find_all(["dt", "strong", "b", "label", "span"]):
        lab = clean_text(label.get_text(" "))
        if not lab or len(lab) > 70:
            continue
        nxt = label.find_next_sibling()
        if nxt:
            val = clean_text(nxt.get_text(" "))
            if val and len(val) < 120:
                rec.setdefault(lab.strip(":"), val)
    rec["page_text"] = clean_text(soup.get_text(" "))[:20000]
    return rec


def _agree_if_needed(client: HttpClient, resp):
    """Handle normal public-record disclaimer. This is not anti-bot evasion; it is the site terms gate."""
    html = resp.text
    if "ACCESS TERMS" not in html.upper() and "DISCLAIM" not in html.upper():
        return resp
    soup = BeautifulSoup(html, "html.parser")
    form = _hidden_fields(soup)
    # common ASP.NET agree buttons/links
    agree_target = None
    for a in soup.find_all("a", href=True):
        txt = clean_text(a.get_text(" ")).lower()
        if "agree" in txt:
            m = re.search(r"__doPostBack\('([^']+)'", a["href"])
            if m:
                agree_target = m.group(1)
                break
            return client.get(urljoin(resp.url, a["href"]))
    for inp in soup.find_all("input"):
        val = clean_text(inp.get("value", "")).lower()
        name = inp.get("name", "")
        if "agree" in val and name:
            form[name] = inp.get("value", "Agree")
            return client.post(resp.url, data=form)
    if agree_target:
        form["__EVENTTARGET"] = agree_target
        form["__EVENTARGUMENT"] = ""
        return client.post(resp.url, data=form)
    return resp


def _http_search(address: str, p: dict) -> PropertyResult | None:
    client = HttpClient()
    r = client.get(URL)
    r = _agree_if_needed(client, r)
    soup = BeautifulSoup(r.text, "html.parser")
    # If the system is down, report error instead of silent not_found.
    if "currently unavailable" in r.text.lower() or "maintenance" in r.text.lower():
        return PropertyResult(status="error", city="newport news", normalized_address=p["normalized"], source_url=r.url, notes="Newport News assessor site says it is unavailable/maintenance")
    form = _hidden_fields(soup)
    # Fill every address-looking text field because Tyler field IDs vary by version.
    for inp in soup.find_all("input"):
        name = inp.get("name", "")
        typ = (inp.get("type") or "text").lower()
        field_id = (inp.get("id") or name).lower()
        if typ in {"text", "search"}:
            if "street" in field_id and "number" not in field_id:
                form[name] = p["street_name"]
            elif "number" in field_id or "addr" in field_id or "address" in field_id:
                form[name] = p["number"] if "number" in field_id else p["normalized"]
    form.update({
        "inpNumber": p["number"],
        "inpStreet": p["street_name"],
        "inpStreetName": p["street_name"],
        "inpSuffix": p["suffix"],
        "btSearch": "Search",
        "__EVENTTARGET": form.get("__EVENTTARGET", ""),
        "__EVENTARGUMENT": form.get("__EVENTARGUMENT", ""),
    })
    post = client.post(r.url, data=form)
    html = post.text
    soup2 = BeautifulSoup(html, "html.parser")
    # Follow first detail link, avoiding navigation/footer links.
    for a in soup2.find_all("a", href=True):
        txt = clean_text(a.get_text(" ")).upper()
        href = a["href"]
        if p["number"] in txt or "PARCEL" in href.upper() or "SUMMARY" in href.upper() or "PROPERTY" in href.upper():
            if any(skip in href.lower() for skip in ["javascript:void", "home", "help"]):
                continue
            detail_url = urljoin(post.url, href)
            detail = client.get(detail_url)
            rec = _record_from_html(detail.text)
            return result_from_record(rec, "newport news", detail.url, p["normalized"], notes="Newport News assessor detail page")
    rec = _record_from_html(html)
    res = result_from_record(rec, "newport news", post.url, p["normalized"], notes="Newport News assessor search response")
    return res if res.status != "not_found" else None


def _browser_search(address: str, p: dict, headed: bool) -> PropertyResult:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        return PropertyResult(status="error", city="newport news", normalized_address=p["normalized"], source_url=URL, notes=f"Playwright unavailable for fallback: {e}")
    notes = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not headed)
        page = browser.new_page(viewport={"width": 1400, "height": 1000})
        try:
            page.goto(URL, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(1000)
            for label in ["Agree", "I Agree", "Accept"]:
                try:
                    loc = page.get_by_text(label, exact=False)
                    if loc.count() > 0 and loc.first.is_visible(timeout=1000):
                        loc.first.click(timeout=3000)
                        page.wait_for_timeout(1500)
                        break
                except Exception:
                    pass
            for q in variants(address, "newport news"):
                notes.append(f"tried:{q}")
                inputs = page.locator("input[type='text']:visible, input[type='search']:visible")
                if inputs.count() == 0:
                    continue
                # Prefer separate fields if present; otherwise fill the most likely field.
                filled = False
                for i in range(min(inputs.count(), 8)):
                    inp = inputs.nth(i)
                    try:
                        meta = ((inp.get_attribute("id") or "") + " " + (inp.get_attribute("name") or "") + " " + (inp.get_attribute("placeholder") or "")).lower()
                        if "number" in meta:
                            inp.fill(p["number"], timeout=2000); filled = True
                        elif "street" in meta:
                            inp.fill(p["street_name"], timeout=2000); filled = True
                        elif not filled:
                            inp.fill(q, timeout=2000); filled = True
                    except Exception:
                        pass
                page.keyboard.press("Enter")
                page.wait_for_timeout(3000)
                try:
                    page.locator(f"text=/{p['number']}/i").first.click(timeout=2500)
                    page.wait_for_timeout(3000)
                except Exception:
                    pass
                rec = _record_from_html(page.content())
                res = result_from_record(rec, "newport news", page.url, p["normalized"], notes="; ".join(notes[-3:]))
                if res.status != "not_found":
                    browser.close(); return res
        except Exception as e:
            browser.close()
            return PropertyResult(status="error", city="newport news", normalized_address=p["normalized"], source_url=URL, notes=f"Newport News browser fallback error: {type(e).__name__}: {e}; {'; '.join(notes)}")
        browser.close()
    return PropertyResult(status="not_found", city="newport news", normalized_address=p["normalized"], source_url=URL, notes="No Newport News assessor match. " + "; ".join(notes[:8]))


def scrape(address: str, city: str = "newport news", headed: bool = False) -> PropertyResult:
    p = parse_address(address, city)
    try:
        res = _http_search(address, p)
        if res and res.status != "not_found":
            return res
    except Exception as e:
        # Continue to browser fallback for layout drift.
        http_note = f"HTTP attempt failed: {type(e).__name__}: {e}. "
    else:
        http_note = "HTTP attempt returned no match. "
    res = _browser_search(address, p, headed)
    res.notes = http_note + res.notes
    return res
