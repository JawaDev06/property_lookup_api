# Property Lookup API v11

This is a clean Railway-ready rebuild.

## What this version does

- Reads `.xlsx` files from `Input/`
- Uses addresses in column `B`
- Writes:
  - `F` = assessed value
  - `N` = square feet
  - `O` = year built
  - `P` = beds
  - `Q` = baths
  - `R` = status
  - `S` = source URL
  - `T` = notes/reason
- Saves updated workbook to `Output/`
- Moves original workbook to `Processed/`
- Writes JSON logs to `Logs/`
- Adds a `Diagnostics` worksheet to every output file

## Important note

This version is designed to be stable and honest. It does not bypass anti-bot detection. For Norfolk, the browser-based AIR site should not be used for unattended scraping. Configure an official Norfolk Socrata/Open Data endpoint using the `NORFOLK_SOCRATA_ENDPOINT` environment variable once you confirm the current dataset URL.

Several city modules are intentionally safe generic modules. They will not crash the job, but they may return `not_found` or `not_implemented` until a confirmed official API/export/search endpoint is mapped.

## Local run

```bash
pip install -r requirements.txt
python3 run_job.py --overwrite
```

Put workbooks in:

```text
Input/
```

Get completed files from:

```text
Output/
```

## Railway background job

Use the included `Dockerfile`.

Railway command:

```bash
python3 run_job.py --overwrite
```

## Railway web/API mode

If you want the test page and `/docs`, change Railway start command to:

```bash
uvicorn main:app --host 0.0.0.0 --port 8080
```

Then test:

```text
/lookup-test?address=22%20Kemper%20Ave%20Newport%20News
```

Upload workbook using:

```text
/process-workbook
```

## Files that should be in GitHub

```text
main.py
router.py
workbook.py
run_job.py
config.py
requirements.txt
Dockerfile
.dockerignore
.gitignore
README.md
property_scraper/
Input/.gitkeep
Output/.gitkeep
Processed/.gitkeep
Logs/.gitkeep
```

Do not commit:

```text
__pycache__/
*.pyc
*_UPDATED.xlsx
scrape_log.json
```
