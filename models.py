from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional


@dataclass
class PropertyData:
    latest_assessed_value: Optional[Decimal] = None
    square_feet: Optional[int] = None
    year_built: Optional[int] = None
    beds: Optional[float] = None
    baths: Optional[float] = None
    last_sold_date: Optional[date] = None
    last_sold_amount: Optional[Decimal] = None
    garage: Optional[str] = None
    garage_summary: Optional[str] = None
    garage_code: Optional[str] = None
    garage_sqft: Optional[int] = None
    parking_spaces: Optional[int] = None
    tax_assess_year: Optional[int] = None
    assessor_taxroll_update: Optional[date] = None
    assessor_last_update: Optional[date] = None
    publication_date: Optional[date] = None
    source: Optional[str] = None
    raw: Optional[dict[str, Any]] = None


def parse_decimal(value: Any) -> Optional[Decimal]:
    if value in (None, ""):
        return None
    if isinstance(value, Decimal):
        return value
    text = str(value).strip().replace("$", "").replace(",", "")
    if text in {"", "None", "null", "N/A", "--"}:
        return None
    try:
        return Decimal(text)
    except Exception:
        return None


def parse_int(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    text = str(value).strip().replace(",", "")
    if text in {"", "None", "null", "N/A", "--"}:
        return None
    try:
        return int(float(text))
    except Exception:
        return None


def parse_float(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    text = str(value).strip().replace(",", "")
    if text in {"", "None", "null", "N/A", "--"}:
        return None
    try:
        return float(text)
    except Exception:
        return None


def parse_date(value: Any) -> Optional[date]:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if text in {"", "None", "null", "N/A", "--"}:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            continue
    return None
