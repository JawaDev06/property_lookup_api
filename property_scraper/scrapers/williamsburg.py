import httpx
from urllib.parse import urlencode
from property_scraper.models import PropertyResult
from property_scraper.scrapers.common import parse_generic_fields


def lookup(parsed, site):
    """Generic safe lookup module.

    This does NOT bypass anti-bot systems. It tries official URLs/API-like endpoints
    only. For production reliability, replace this with a dedicated parser once the
    official endpoint/search form for this locality is confirmed.
    """
    url = site.get("url")
    city = parsed.get("city")
    if not url:
        return PropertyResult(address=parsed["original"], city=city, status="source_not_configured", notes="No source URL configured.")
    try:
        # Most parcel sites do not support this directly, but this gives diagnostics and keeps the job from crashing.
        with httpx.Client(timeout=30, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()
        result = parse_generic_fields(resp.text, parsed["original"], city, str(resp.url))
        if result.status == "not_found":
            result.notes += " Dedicated search automation still required for this locality."
        return result
    except Exception as e:
        return PropertyResult(address=parsed["original"], city=city, source_url=url, status="error", notes=str(e))
