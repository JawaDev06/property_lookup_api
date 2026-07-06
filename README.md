# Smarty-Only Weekly Property Workbook Tool

## v5 update: extra headers on row 2

This version writes the optional Smarty columns' headers on **row 2** by default, only if those cells are blank:

```text
W  = Garage Summary
X  = Garage Sq Ft
Y  = Tax Assess Year
Z  = Assessor Taxroll Update
AA = Assessor Last Update
AB = Publication Date
AC = Parking Spaces
AD = Garage Raw
```

To change the header row, set this in `.env`:

```env
SMARTY_EXTRA_HEADER_ROW=2
```

If your actual property rows start on row 3 because row 2 is now the header row, run with `--start-row 3`.


This version enriches your weekly Excel workbook using **Smarty APIs only**. It does **not** open, scrape, or call any county/GIS/property assessor websites.

## What it fills

The workbook mapping is:

| Column | Field |
|---|---|
| B | Input property address |
| F | Latest assessed value |
| N | Square feet |
| O | Year built |
| P | Beds |
| Q | Baths |
| U | Last sold date |
| V | Last sold amount |

Baths are calculated as:

- If Smarty returns `bathrooms_total`, the tool uses that.
- Otherwise, it uses `full baths + 0.5 × half baths` when those fields are available.

## Smarty product needed

You need Smarty credentials and access to **US Property Data / US Address Enrichment API**. A normal address-validation-only plan may validate addresses but may not return assessed value, square feet, beds, baths, and sale information.

Smarty usually provides an **Auth ID** and **Auth Token**. Put them in `.env`; do not paste them into ChatGPT.

## Setup on Mac

From inside the unzipped folder:

```bash
cd /Users/danielagonzalez/smarty_only_workbook_tool
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and set:

```env
SMARTY_AUTH_ID=your-smarty-auth-id
SMARTY_AUTH_TOKEN=your-smarty-auth-token
SMARTY_DEFAULT_STATE=VA
SMARTY_USE_ENRICHMENT_SEARCH=true
```

## Run it manually

Use quotes around workbook names that contain spaces:

```bash
source .venv/bin/activate
python -u process_workbook.py "Southside sales June 29 to July 3-1.xlsx" "Southside sales June 29 to July 3-1_updated.xlsx" --start-row 2
```

If your workbook has a city/locality column, use it. Example for column C:

```bash
python -u process_workbook.py "Southside sales June 29 to July 3-1.xlsx" "Southside sales June 29 to July 3-1_updated.xlsx" --start-row 2 --city-column C
```

The `-u` flag makes progress print immediately. You should see messages like:

```text
Row 2: Smarty lookup for 123 Main St, Hampton
Row 2: updated
```

## If Smarty address search is not available

The default is:

```env
SMARTY_USE_ENRICHMENT_SEARCH=true
```

That calls:

```text
GET https://us-enrichment.api.smarty.com/lookup/search/property
```

If Smarty support says your plan must use SmartyKey instead, set:

```env
SMARTY_USE_ENRICHMENT_SEARCH=false
```

Then the tool will:

1. Call the US Street Address API with `match=enhanced` to get `smarty_key`.
2. Call the US Address Enrichment API using that `smarty_key`.

## Local web server for Zapier testing

Run:

```bash
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

Check:

```text
http://localhost:8000/health
```

For Zapier, deploy this app to a public URL using Render, Railway, Fly.io, Google Cloud Run, or another hosting provider.

## Zapier flow

1. Gmail trigger: new email / new attachment.
2. Filter for `.xlsx`.
3. Webhooks by Zapier → POST:

```text
https://your-public-domain.com/process
```

Header:

```text
X-API-Key: your APP_API_KEY
```

JSON body:

```json
{
  "file_url": "{{Gmail attachment file}}",
  "original_filename": "{{Gmail attachment filename}}",
  "sender_email": "{{sender email}}",
  "original_subject": "{{subject}}",
  "start_row": 3,
  "city_column": "C"
}
```

Use `city_column` only if your workbook has city/locality in column C. The `original_filename` field is optional, but when Zapier sends it the returned workbook keeps the original attachment name.

The API returns:

```json
{
  "download_url": "https://your-public-domain.com/files/<job_id>/Original%20Workbook.xlsx",
  "filename": "Original Workbook.xlsx",
  "stats": {
    "rows_seen": 10,
    "rows_with_address": 10,
    "rows_updated": 8,
    "rows_not_found": 2,
    "errors": 0
  }
}
```

4. Gmail action: send/reply to the sender and attach the returned `download_url`.

## Troubleshooting

### `401 Unauthorized`

Check `SMARTY_AUTH_ID` and `SMARTY_AUTH_TOKEN`.

### `402 Payment Required`

Your Smarty account probably does not include US Property Data / Address Enrichment for the fields you need.

### No fields populate

Try leaving `SMARTY_INCLUDE` blank in `.env` so Smarty returns all fields your subscription includes:

```env
SMARTY_INCLUDE=
```

Then rerun and inspect one row. If you receive a sample JSON response from Smarty, the field mapper can be adjusted quickly.

### File names with spaces

Always quote workbook names:

```bash
python process_workbook.py "input file.xlsx" "output file.xlsx"
```

## Security notes

- Do not commit `.env` to GitHub.
- Do not paste your Smarty Auth Token into ChatGPT.
- For production, put credentials in your hosting provider's environment variables.


## Data freshness and optional garage columns

Smarty returns the property data available in your Smarty US Property Data subscription. For deeds and assessments,
third-party aggregated property data can lag the local assessor/recorder. This is normal when a city/county has a very
recent sale or a newly released assessment roll.

The tool can optionally write extra fields when Smarty returns them. Add any of these to `.env` to turn them on:

```env
SMARTY_GARAGE_COLUMN=W
SMARTY_GARAGE_SQFT_COLUMN=X
SMARTY_TAX_ASSESS_YEAR_COLUMN=Y
SMARTY_ASSESSOR_TAXROLL_UPDATE_COLUMN=Z
SMARTY_ASSESSOR_LAST_UPDATE_COLUMN=AA
SMARTY_PUBLICATION_DATE_COLUMN=AB
```

These are blank by default so the tool does not overwrite columns you may already use.

For troubleshooting missing fields, you can save the raw Smarty response for each matched row:

```env
SMARTY_RAW_JSON_DIR=./smarty_raw_json
```

Then rerun the workbook. If a field is present in the raw JSON but not in the workbook, adjust the mapping in
`clients/smarty_property_data.py`. If the field is not present in the raw JSON, Smarty does not currently have it for
that address/account response.

## v4 garage summary columns

Version 4 changes the default garage output so column W is a friendly garage summary instead of only the raw Smarty garage field.

Default extra columns:

- W = Garage Summary, for example `Attached 2-car`, `Detached garage`, `2-car garage`, or `2-car garage (est.)`
- X = Garage Sq Ft
- Y = Tax Assess Year
- Z = Assessor Taxroll Update
- AA = Assessor Last Update
- AB = Publication Date
- AC = Parking Spaces
- AD = Garage Raw

Important: Smarty documents `garage`, `garage_sqft`, and `parking_spaces` in the structural property data group. It does not guarantee a separate attached/detached field. The tool labels attached/detached only when Smarty's returned `garage` text includes that wording. If no car count is returned, the tool can estimate the car count from garage square feet and marks it with `(est.)`.

To change/disable these columns, edit `.env`:

```env
SMARTY_GARAGE_SUMMARY_COLUMN=W
SMARTY_GARAGE_SQFT_COLUMN=X
SMARTY_PARKING_SPACES_COLUMN=AC
SMARTY_GARAGE_RAW_COLUMN=AD
SMARTY_ESTIMATE_GARAGE_CARS_FROM_SQFT=true
```
