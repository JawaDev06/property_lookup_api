# Official Property Scraper Modular v10

This version fixes issues found in v9 outputs:

- Fixes street normalization that incorrectly changed `225 Hampton Roads Ave Hampton` into `225 ROADS AVE`.
- Newport News now handles the public-record disclaimer/agree page before attempting the assessor search.
- Newport News has both HTTP and Playwright fallback search paths.
- Browser-only searches ignore invisible inputs, which fixes the Portsmouth error where the script was filling a hidden Google Translate field.
- Generic field parsing is stricter so bad values like `1` sqft are not written.
- Rows that cannot be completed still write status, source, notes, and normalized address to columns R-U.

## What it fills

For every `.xlsx` file in `Input`, it reads addresses from column **B**, then fills:

- **F** = assessed value
- **N** = square feet
- **O** = year built
- **P** = beds
- **Q** = baths
- **R** = status
- **S** = source URL
- **T** = notes/reason
- **U** = normalized address

## Folder layout

```text
Property Details Automation/
├── Input/
├── Output/
├── Processed/
├── Logs/
└── Script/
    └── official_property_scraper/
```

## Install

From the scraper folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
```

## Run

```bash
python3 official_property_scraper.py --overwrite
```

For troubleshooting browser-only sites:

```bash
python3 official_property_scraper.py --headed --overwrite
```

For background watching:

```bash
python3 official_property_scraper.py --overwrite --watch --interval 300
```

## Important

Some localities do not make all fields available in their public source. In those cases the script will return `partial` and explain the missing fields in columns R-T/logs rather than silently leaving everything blank.

If a locality blocks automated browser access, use that locality's official bulk/open-data source when available or a PropStream export merger workflow.
