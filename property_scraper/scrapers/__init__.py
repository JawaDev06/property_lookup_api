from __future__ import annotations
from property_scraper.common import PropertyResult
from . import norfolk, hampton, generic_browser, gloucester, newport_news

ROUTES = {
    "norfolk": norfolk.scrape,
    "hampton": hampton.scrape,
    "gloucester": gloucester.scrape,
    "hayes": gloucester.scrape,
    "newport news": newport_news.scrape,
    # browser modules with dedicated URLs but generic extraction
    "chesapeake": generic_browser.scrape,
    "portsmouth": generic_browser.scrape,
    "suffolk": generic_browser.scrape,
    "virginia beach": generic_browser.scrape,
    "james city county": generic_browser.scrape,
    "williamsburg": generic_browser.scrape,
    "poquoson": generic_browser.scrape,
    "yorktown": generic_browser.scrape,
}

def scrape_property(address: str, city: str | None = None, *, headed: bool = False) -> PropertyResult:
    if not city:
        from property_scraper.common import detect_city
        city = detect_city(address)
    if not city:
        return PropertyResult(status="city_not_detected", notes="Could not detect city from address", normalized_address=address)
    fn = ROUTES.get(city)
    if not fn:
        return PropertyResult(status="city_not_supported", city=city, notes=f"No scraper module for city: {city}", normalized_address=address)
    try:
        return fn(address, city=city, headed=headed)
    except Exception as e:
        return PropertyResult(status="error", city=city, notes=f"{type(e).__name__}: {e}", normalized_address=address)
