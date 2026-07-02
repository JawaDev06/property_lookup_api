from property_scraper.models import PropertyResult

def lookup(parsed, site):
    return PropertyResult(
        address=parsed["original"], city=parsed.get("city"), source_url=site.get("url"), status="not_implemented",
        notes="This city module is present but needs a confirmed official API/export or dedicated parser."
    )
