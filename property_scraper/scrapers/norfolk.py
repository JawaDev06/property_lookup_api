import httpx
from property_scraper.models import PropertyResult

# Norfolk should use official open data rather than AIR browser scraping.
# Dataset IDs can change by fiscal year. Configure NORFOLK_SOCRATA_ENDPOINT in config.py/env when you confirm the current dataset.

def lookup(parsed, site):
    endpoint = site.get("socrata_endpoint")
    address = parsed["normalized"]
    if not endpoint:
        return PropertyResult(
            address=parsed["original"], city="norfolk", source_url=site.get("url"), status="source_not_configured",
            notes="Norfolk AIR blocks automation. Configure official Socrata endpoint/dataset in config.py for unattended jobs."
        )
    try:
        with httpx.Client(timeout=30, follow_redirects=True) as client:
            # Conservative client-side match; avoids assuming field names until endpoint is confirmed.
            resp = client.get(endpoint, params={"$limit": 5000})
            resp.raise_for_status()
            rows = resp.json()
        target = address.replace(" ", "")
        best = None
        for row in rows:
            row_text = " ".join(str(v) for v in row.values()).upper().replace(" ", "")
            if target in row_text:
                best = row; break
        if not best:
            return PropertyResult(address=parsed["original"], city="norfolk", source_url=endpoint, status="not_found", notes="No matching record found in configured Norfolk open-data endpoint.")
        def pick(*names):
            for n in names:
                for k,v in best.items():
                    if k.lower().replace("_","") == n.lower().replace("_",""):
                        return v
            return None
        def num(v):
            if v in (None, ""): return None
            try: return float(str(v).replace('$','').replace(',',''))
            except Exception: return None
        r = PropertyResult(address=parsed["original"], city="norfolk", source_url=endpoint)
        r.assessed_value = num(pick("total_assessment","total_value","assessed_value"))
        r.sqft = num(pick("building_area","living_area","sqft","square_feet"))
        y = num(pick("year_built","yr_built")); r.year_built = int(y) if y else None
        r.beds = num(pick("bedrooms","beds"))
        r.baths = num(pick("bathrooms","baths"))
        vals = [r.assessed_value, r.sqft, r.year_built, r.beds, r.baths]
        r.status = "complete" if all(v is not None for v in vals) else "partial"
        r.notes = "Matched Norfolk open-data row. Review field mapping if any fields are missing."
        return r
    except Exception as e:
        return PropertyResult(address=parsed["original"], city="norfolk", source_url=endpoint, status="error", notes=str(e))
