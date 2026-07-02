from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = Path(os.getenv("INPUT_DIR", BASE_DIR / "Input"))
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", BASE_DIR / "Output"))
PROCESSED_DIR = Path(os.getenv("PROCESSED_DIR", BASE_DIR / "Processed"))
LOGS_DIR = Path(os.getenv("LOGS_DIR", BASE_DIR / "Logs"))

for folder in [INPUT_DIR, OUTPUT_DIR, PROCESSED_DIR, LOGS_DIR]:
    folder.mkdir(parents=True, exist_ok=True)

SITES = {
    "norfolk": {
        "module": "norfolk",
        "url": "https://www.norfolk.gov/4545/Property-Search",
        # Set this after confirming the current official Socrata API endpoint, e.g.
        # "https://data.norfolk.gov/resource/xxxx-yyyy.json"
        "socrata_endpoint": os.getenv("NORFOLK_SOCRATA_ENDPOINT", ""),
    },
    "hampton": {"module": "hampton", "url": "https://webgis3.hampton.gov/civquest/"},
    "newport news": {"module": "newport_news", "url": "https://assessment.nnva.gov/PT/search/commonsearch.aspx?mode=address"},
    "portsmouth": {"module": "portsmouth", "url": "http://data.portsmouthva.gov/assessor/data/realestatesearch.aspx"},
    "chesapeake": {"module": "chesapeake", "url": "https://chesapeake.civ.quest"},
    "suffolk": {"module": "suffolk", "url": "https://property.spatialest.com/va/suffolk#/"},
    "virginia beach": {"module": "virginia_beach", "url": "https://propertysearch.virginiabeach.gov/#/"},
    "james city county": {"module": "james_city", "url": "https://property.jamescitycountyva.gov/JamesCity/"},
    "williamsburg": {"module": "williamsburg", "url": "https://property.spatialest.com/va/williamsburg#/"},
    "gloucester": {"module": "gloucester", "url": "https://gis.vgsi.com/gloucesterva/Search.aspx"},
    "hayes": {"module": "gloucester", "url": "https://gis.vgsi.com/gloucesterva/Search.aspx"},
    "yorktown": {"module": "york", "url": "https://maps.yorkcounty.gov"},
    "poquoson": {"module": "poquoson", "url": "https://www.geoplan.app/poquoson/"},
}
