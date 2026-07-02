import importlib
from property_scraper.normalize import parse_address, is_probable_address
from property_scraper.models import PropertyResult
from config import SITES


def lookup_property(raw_address: str) -> PropertyResult:
    if not is_probable_address(raw_address):
        return PropertyResult(address=str(raw_address or ""), status="skipped", notes="Row does not look like a property address.")
    parsed = parse_address(raw_address)
    city = parsed.get("city")
    if not city:
        return PropertyResult(address=parsed["original"], status="city_not_detected", notes="Address must include city, e.g. '22 Kemper Ave Newport News'.")
    site = SITES.get(city)
    if not site:
        return PropertyResult(address=parsed["original"], city=city, status="city_not_supported", notes=f"No site configured for city: {city}")
    modname = site.get("module")
    try:
        module = importlib.import_module(f"property_scraper.scrapers.{modname}")
        result = module.lookup(parsed, site)
        result.city = result.city or city
        return result
    except Exception as e:
        return PropertyResult(address=parsed["original"], city=city, source_url=site.get("url"), status="error", notes=f"Router/module error: {e}")
