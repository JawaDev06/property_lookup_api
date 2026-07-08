# Smarty-only workbook tool v9

This version uses **Smarty only**. It does not call county assessor/GIS websites.

## v9 output columns

| Column | Field |
|---|---|
| B | Input property address |
| F | Latest assessed value |
| N | Square feet |
| O | Year built |
| P | Beds |
| Q | Baths |
| R | Garage A/D SqFt |
| U | Last Sold Date |
| V | Last Sold Amount |

Garage values in column R use this format:

- `A 420` = attached garage, 420 sqft
- `D 240` = detached garage, 240 sqft
- `A` = attached garage, sqft unavailable
- `D` = detached garage, sqft unavailable
- `420` = garage sqft available, but attached/detached not returned by Smarty

`A`/`D` are only written when Smarty returns enough garage detail to identify attached vs detached.

## Headers

By default, the tool writes these headers on row 2 only if the cells are blank:

- R = `Garage A/D SqFt`
- U = `Last Sold Date`
- V = `Last Sold Amount`

Control this with:

```env
SMARTY_WRITE_EXTRA_HEADERS=true
SMARTY_EXTRA_HEADER_ROW=2
```

If row 2 is your header row, run the workbook with `--start-row 3`.

## Removed columns

v9 deletes **W:AD** by default after processing, but it keeps **U/V** for last sold date and amount.

```env
SMARTY_DELETE_COLUMNS_W_AD=true
```

If your Railway project still has the older variable below, v9 treats it as “delete W:AD only.” It will not delete U/V:

```env
SMARTY_DELETE_COLUMNS_U_AD=true
```

To stop deleting W:AD, set either variable to `false`.

## No added formatting/comments

This version does not add green fill/background colors and does not add cell comments. It only writes values and number formats.

## Setup on Mac

```bash
cd /Users/danielagonzalez/smarty_only_workbook_tool
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
cp .env.example .env
open -e .env
```

Set your Smarty credentials in `.env` locally, or in Railway Variables for deployment:

```env
SMARTY_AUTH_ID=your-smarty-auth-id
SMARTY_AUTH_TOKEN=your-smarty-auth-token
SMARTY_DEFAULT_STATE=VA
SMARTY_USE_ENRICHMENT_SEARCH=true
SMARTY_INCLUDE=group_structural,group_financial
```

## Run manually

Use quotes around workbook names with spaces:

```bash
source .venv/bin/activate
python -u process_workbook.py "Southside sales June 29 to July 3-1.xlsx" "Southside sales June 29 to July 3-1_updated.xlsx" --start-row 3 --city-column C
```

Use `--city-column C` only if column C contains the city/locality. If the full address in B already includes city/state, omit it.

## Railway variables

Add these as Railway Variables, not in GitHub:

```env
APP_API_KEY=your-private-zapier-password
PUBLIC_BASE_URL=https://your-railway-url.up.railway.app
WORK_DIR=/tmp/weekly_property_workbooks
PYTHON_VERSION=3.12.10

SMARTY_AUTH_ID=your-smarty-auth-id
SMARTY_AUTH_TOKEN=your-smarty-auth-token
SMARTY_DEFAULT_STATE=VA
SMARTY_USE_ENRICHMENT_SEARCH=true
SMARTY_TIMEOUT_SECONDS=30
SMARTY_RATE_LIMIT_SECONDS=0.15
SMARTY_INCLUDE=group_structural,group_financial

SMARTY_EXTRA_HEADER_ROW=2
SMARTY_WRITE_EXTRA_HEADERS=true
SMARTY_DELETE_COLUMNS_W_AD=true
```

Start command:

```bash
uvicorn app:app --host 0.0.0.0 --port $PORT
```

Health check:

```text
https://your-railway-url.up.railway.app/health
```

## Zapier webhook body

Use **Webhooks by Zapier → POST** with payload type `json`.

Data fields:

```text
file_url            Gmail attachment/file
original_filename   Gmail attachment filename
sender_email        Gmail From Email
original_subject    Gmail Subject
start_row           3
city_column         C
```

Headers:

```text
Content-Type: application/json
X-API-Key: your APP_API_KEY value
```

The API returns a `download_url`. Use that `download_url` as the attachment in your final Gmail Send Email/Reply step.

## Smarty product needed

Your Smarty account must include US Property Data / US Address Enrichment. Address-validation-only access may not return assessed value, square feet, beds, baths, garage, and sale information.

## Troubleshooting

If a value is missing, set this temporarily to inspect Smarty’s raw response:

```env
SMARTY_RAW_JSON_DIR=./smarty_raw_json
```

If the field is not in the raw JSON, Smarty does not currently have it for that address/account response. If it is in the raw JSON under a different field name, update `clients/smarty_property_data.py`.
