from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from openpyxl import load_workbook
from openpyxl.comments import Comment
from openpyxl.styles import PatternFill

from clients.base import PropertyLookupClient
from clients.smarty_property_data import SmartyPropertyDataClient
from column_map import COLUMNS, DEFAULT_START_ROW
from models import PropertyData

load_dotenv()


@dataclass
class ProcessStats:
    rows_seen: int = 0
    rows_with_address: int = 0
    rows_updated: int = 0
    rows_not_found: int = 0
    errors: int = 0


def make_client() -> PropertyLookupClient:
    # This package intentionally uses Smarty only. No county/GIS/assessor websites are called.
    return SmartyPropertyDataClient()


def _env_col(name: str, default: str) -> str:
    """Return an output column.

    Defaults the extra columns on so you do not have to edit .env.
    To disable any extra field, set its env var to DISABLED, NONE, or OFF.
    """
    raw = os.getenv(name)
    value = (raw if raw is not None else default).strip().upper()
    if value in {"", "DISABLED", "NONE", "OFF", "FALSE", "0"}:
        return ""
    return value


def _optional_extra_columns() -> dict[str, tuple[str, object, str, str]]:
    """Return extra output columns.

    v4 changes W to a friendly garage summary such as "Attached 2-car" when Smarty
    returns enough information. X remains garage square feet. AC/AD are optional raw
    troubleshooting columns.
    """
    garage_summary_col = _env_col("SMARTY_GARAGE_SUMMARY_COLUMN", os.getenv("SMARTY_GARAGE_COLUMN", "W"))
    return {
        garage_summary_col: ("garage_summary", None, "General", "Garage Summary"),
        _env_col("SMARTY_GARAGE_SQFT_COLUMN", "X"): ("garage_sqft", None, "#,##0", "Garage Sq Ft"),
        _env_col("SMARTY_TAX_ASSESS_YEAR_COLUMN", "Y"): ("tax_assess_year", None, "0", "Tax Assess Year"),
        _env_col("SMARTY_ASSESSOR_TAXROLL_UPDATE_COLUMN", "Z"): ("assessor_taxroll_update", None, "m/d/yyyy", "Assessor Taxroll Update"),
        _env_col("SMARTY_ASSESSOR_LAST_UPDATE_COLUMN", "AA"): ("assessor_last_update", None, "m/d/yyyy", "Assessor Last Update"),
        _env_col("SMARTY_PUBLICATION_DATE_COLUMN", "AB"): ("publication_date", None, "m/d/yyyy", "Publication Date"),
        _env_col("SMARTY_PARKING_SPACES_COLUMN", "AC"): ("parking_spaces", None, "0", "Parking Spaces"),
        _env_col("SMARTY_GARAGE_RAW_COLUMN", "AD"): ("garage", None, "General", "Garage Raw"),
    }


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _write_extra_headers(ws) -> None:
    if not _env_bool("SMARTY_WRITE_EXTRA_HEADERS", True):
        return
    header_row = int(os.getenv("SMARTY_EXTRA_HEADER_ROW", "2"))
    for col, (_field_name, _placeholder, _num_fmt, label) in _optional_extra_columns().items():
        if not col:
            continue
        cell = ws[f"{col}{header_row}"]
        if cell.value in (None, ""):
            cell.value = label


def _safe_filename_piece(value: str, max_len: int = 60) -> str:
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return text[:max_len].strip("._-") or "property"


def _dump_raw_json(row: int, address: str, data: PropertyData) -> None:
    raw_dir = os.getenv("SMARTY_RAW_JSON_DIR", "").strip()
    if not raw_dir or not data.raw:
        return
    out_dir = Path(raw_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"row_{row}_{_safe_filename_piece(address)}.json"
    out_path.write_text(json.dumps(data.raw, indent=2, default=str), encoding="utf-8")


def _write_property_data(ws, row: int, data: PropertyData) -> None:
    values = {
        COLUMNS.latest_assessed_value: data.latest_assessed_value,
        COLUMNS.square_feet: data.square_feet,
        COLUMNS.year_built: data.year_built,
        COLUMNS.beds: data.beds,
        COLUMNS.baths: data.baths,
        COLUMNS.last_sold_date: data.last_sold_date,
        COLUMNS.last_sold_amount: data.last_sold_amount,
    }

    for col, (field_name, _placeholder, _num_fmt, _label) in _optional_extra_columns().items():
        if not col:
            continue
        values[col] = getattr(data, field_name, None)
    for col, value in values.items():
        if value is not None:
            ws[f"{col}{row}"] = float(value) if hasattr(value, "as_tuple") else value

    ws[f"{COLUMNS.latest_assessed_value}{row}"].number_format = '$#,##0'
    ws[f"{COLUMNS.square_feet}{row}"].number_format = '#,##0'
    ws[f"{COLUMNS.year_built}{row}"].number_format = '0'
    ws[f"{COLUMNS.beds}{row}"].number_format = '0.#'
    ws[f"{COLUMNS.baths}{row}"].number_format = '0.0'
    ws[f"{COLUMNS.last_sold_date}{row}"].number_format = 'm/d/yyyy'
    ws[f"{COLUMNS.last_sold_amount}{row}"].number_format = '$#,##0'

    for col, (field_name, _placeholder, num_fmt, _label) in _optional_extra_columns().items():
        if col and getattr(data, field_name, None) is not None:
            ws[f"{col}{row}"].number_format = num_fmt

    fill = PatternFill(fill_type="solid", fgColor="D9EAD3")
    for col in values:
        if values[col] is not None:
            cell = ws[f"{col}{row}"]
            cell.fill = fill
            cell.comment = Comment(f"Updated by Smarty-only workbook tool. Source: {data.source or 'smarty'}", "ChatGPT Tool")


def process_workbook(
    input_path: str | Path,
    output_path: str | Path,
    client: Optional[PropertyLookupClient] = None,
    sheet_name: Optional[str] = None,
    start_row: int = DEFAULT_START_ROW,
    city_column: Optional[str] = None,
    verbose: bool = True,
) -> ProcessStats:
    input_path = Path(input_path)
    output_path = Path(output_path)
    client = client or make_client()

    wb = load_workbook(input_path)
    ws = wb[sheet_name] if sheet_name else wb.active
    _write_extra_headers(ws)
    stats = ProcessStats()

    try:
        for row in range(start_row, ws.max_row + 1):
            stats.rows_seen += 1
            address = ws[f"{COLUMNS.address}{row}"].value
            if not address or not str(address).strip():
                continue
            stats.rows_with_address += 1
            city_value = ws[f"{city_column}{row}"].value if city_column else None
            city = str(city_value).strip() if city_value else None
            address_text = str(address).strip()
            if verbose:
                print(f"Row {row}: Smarty lookup for {address_text}{', ' + city if city else ''}", flush=True)
            try:
                data = client.lookup(address_text, city=city)
                if data is None:
                    stats.rows_not_found += 1
                    ws[f"{COLUMNS.latest_assessed_value}{row}"].comment = Comment("No reliable Smarty property match found.", "ChatGPT Tool")
                    if verbose:
                        print(f"Row {row}: no match", flush=True)
                    continue
                _write_property_data(ws, row, data)
                _dump_raw_json(row, address_text, data)
                stats.rows_updated += 1
                if verbose:
                    print(f"Row {row}: updated", flush=True)
            except Exception as exc:
                stats.errors += 1
                ws[f"{COLUMNS.latest_assessed_value}{row}"].comment = Comment(f"Smarty lookup error: {exc}", "ChatGPT Tool")
                if verbose:
                    print(f"Row {row}: ERROR {exc}", flush=True)
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            close()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    return stats


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Fill weekly workbook property columns using Smarty US Property Data only.")
    parser.add_argument("input", help="Path to input .xlsx")
    parser.add_argument("output", help="Path for updated .xlsx")
    parser.add_argument("--sheet", default=None, help="Worksheet name. Defaults to active sheet.")
    parser.add_argument("--start-row", default=DEFAULT_START_ROW, type=int)
    parser.add_argument("--city-column", default=os.getenv("SMARTY_CITY_COLUMN"), help="Optional Excel column containing city, e.g. C.")
    parser.add_argument("--quiet", action="store_true", help="Suppress row-by-row progress messages.")
    args = parser.parse_args()
    stats = process_workbook(
        args.input,
        args.output,
        sheet_name=args.sheet,
        start_row=args.start_row,
        city_column=args.city_column,
        verbose=not args.quiet,
    )
    print(asdict(stats))
