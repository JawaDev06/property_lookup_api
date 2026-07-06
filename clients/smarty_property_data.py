from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Optional

import requests

from clients.base import PropertyLookupClient
from models import PropertyData, parse_date, parse_decimal, parse_float, parse_int


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "y", "on"}


def _norm_key(value: Any) -> str:
    text = str(value).strip()
    text = re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", text)
    text = re.sub(r"[^A-Za-z0-9]+", "_", text)
    return text.lower().strip("_")


def _flatten_json(value: Any, prefix: str = "") -> dict[str, Any]:
    flat: dict[str, Any] = {}
    if isinstance(value, dict):
        for key, item in value.items():
            clean_key = _norm_key(key)
            nested_key = f"{prefix}_{clean_key}" if prefix else clean_key
            flat[nested_key] = item
            flat.update(_flatten_json(item, nested_key))
    elif isinstance(value, list):
        for idx, item in enumerate(value[:5]):
            nested_key = f"{prefix}_{idx}" if prefix else str(idx)
            flat[nested_key] = item
            flat.update(_flatten_json(item, nested_key))
    return flat


def _pick(data: dict[str, Any], *names: str):
    lowered = {_norm_key(k): v for k, v in data.items()}
    aliases = [_norm_key(name) for name in names]

    for alias in aliases:
        value = lowered.get(alias)
        if value not in (None, "", [], {}):
            return value

    for key, value in lowered.items():
        if value in (None, "", [], {}):
            continue
        for alias in aliases:
            # Do not let full/half bath fields satisfy total bathroom aliases.
            if alias in {"baths", "bath", "bathrooms", "bath_count", "total_baths"} and (
                "full_bath" in key or "half_bath" in key or key.endswith("baths_full") or key.endswith("baths_half")
            ):
                continue
            if key.endswith("_" + alias) or key.endswith(alias):
                return value
    return None

def _parse_parking_spaces(value: Any) -> Optional[int]:
    """Return a reasonable whole-number parking/garage space count from Smarty fields."""
    direct = parse_int(value)
    if direct is not None and direct >= 0:
        return direct
    if value in (None, ""):
        return None
    text = str(value).lower()
    word_map = {"one": 1, "two": 2, "three": 3, "four": 4}
    for word, number in word_map.items():
        if re.search(rf"\b{word}\b", text):
            return number
    match = re.search(r"\b(\d+)\s*(?:car|cars|space|spaces|stall|stalls)\b", text)
    if match:
        return int(match.group(1))
    return None


def _garage_type_from_raw(value: Any) -> Optional[str]:
    """Best-effort attached/detached label from Smarty's garage text.

    Smarty documents a generic `garage` field, not a guaranteed explicit attached/detached
    enum. This parser only labels attached/detached when the returned text contains that
    wording; otherwise it leaves the type generic.
    """
    if value in (None, ""):
        return None
    text = str(value).strip()
    low = text.lower()
    if low in {"0", "n", "no", "none", "false", "unknown", "not available", "n/a", "--"}:
        return None
    if "detached" in low or re.search(r"\bdet\b", low):
        return "Detached"
    if "attached" in low or re.search(r"\batt\b", low):
        return "Attached"
    if "carport" in low:
        return "Carport"
    if low in {"1", "y", "yes", "true", "garage"}:
        return "Garage"
    # Preserve useful raw descriptors if they are not just yes/no.
    return text[:80]


def _cars_from_sqft(garage_sqft: Optional[int]) -> tuple[Optional[int], bool]:
    """Estimate car count from garage square footage when no parking-space field is returned.

    Returns (count, estimated). Thresholds can be overridden in .env.
    """
    if garage_sqft is None or garage_sqft <= 0:
        return None, False
    if not _env_bool("SMARTY_ESTIMATE_GARAGE_CARS_FROM_SQFT", True):
        return None, False
    one_max = int(os.getenv("SMARTY_ONE_CAR_GARAGE_MAX_SQFT", "399"))
    two_max = int(os.getenv("SMARTY_TWO_CAR_GARAGE_MAX_SQFT", "649"))
    min_sqft = int(os.getenv("SMARTY_MIN_GARAGE_SQFT_FOR_CAR_ESTIMATE", "180"))
    if garage_sqft < min_sqft:
        return None, False
    if garage_sqft <= one_max:
        return 1, True
    if garage_sqft <= two_max:
        return 2, True
    return 3, True


def _garage_summary(raw_garage: Any, garage_sqft: Optional[int], parking_spaces: Optional[int]) -> Optional[str]:
    garage_type = _garage_type_from_raw(raw_garage)
    spaces = parking_spaces
    estimated = False
    if spaces is None:
        # Sometimes the generic garage text contains the car count.
        spaces = _parse_parking_spaces(raw_garage)
    if spaces is None:
        spaces, estimated = _cars_from_sqft(garage_sqft)

    if not garage_type and spaces is None and garage_sqft is None:
        return None

    if spaces is not None and spaces > 0:
        suffix = " (est.)" if estimated else ""
        if garage_type and garage_type not in {"Garage"}:
            return f"{garage_type} {spaces}-car{suffix}"
        return f"{spaces}-car garage{suffix}"

    if garage_type and garage_type in {"Attached", "Detached"}:
        return f"{garage_type} garage"
    if garage_type:
        return garage_type
    if garage_sqft:
        return "Garage"
    return None



def _first_record(payload: Any) -> Optional[dict[str, Any]]:
    if payload is None:
        return None
    if isinstance(payload, list):
        return _first_record(payload[0]) if payload else None
    if not isinstance(payload, dict):
        return None

    if isinstance(payload.get("attributes"), dict):
        return payload

    for key in ("property", "record", "result", "data", "match"):
        value = payload.get(key)
        if isinstance(value, dict):
            return _first_record(value) or value
        if isinstance(value, list) and value:
            return _first_record(value)

    for key in ("properties", "records", "results", "matches", "items"):
        value = payload.get(key)
        if isinstance(value, list) and value:
            return _first_record(value[0])

    return payload


def property_data_from_smarty_payload(payload: Any, source: str = "smarty_property_data") -> Optional[PropertyData]:
    """Map Smarty US Address Enrichment property JSON to the workbook fields."""
    record = _first_record(payload)
    if not isinstance(record, dict) or not record:
        return None

    attrs = record.get("attributes") if isinstance(record.get("attributes"), dict) else record
    flat = _flatten_json(attrs)
    flat.update({_norm_key(k): v for k, v in attrs.items()} if isinstance(attrs, dict) else {})

    full_baths = parse_float(_pick(
        flat,
        "full_baths", "full_bath", "full_bathrooms", "baths_full", "bathrooms_full",
        "full_bath_count", "bath_full_count", "bathroom_full_count",
    ))
    half_baths = parse_float(_pick(
        flat,
        "half_baths", "half_bath", "half_bathrooms", "baths_half", "bathrooms_half",
        "half_bath_count", "bath_half_count", "bathroom_half_count", "bathrooms_partial",
    ))
    total_baths = parse_float(_pick(
        flat,
        "baths", "bath", "bathrooms", "total_baths", "bath_total", "bath_count",
        "bathroom_count", "total_bath_count", "bathrooms_total",
    ))
    baths = total_baths if total_baths is not None else (
        (full_baths or 0) + 0.5 * (half_baths or 0)
        if (full_baths is not None or half_baths is not None)
        else None
    )

    data = PropertyData(
        latest_assessed_value=parse_decimal(_pick(
            flat,
            "latest_assessed_value", "assessed_value", "assessment_value", "total_assessed_value",
            "total_assessment", "current_assessed_value", "tax_assessed_value",
            "value_assessed_total", "assessed_total", "tax_assessment_value", "assessment_total",
            "total_value_assessed", "property_assessed_value", "property_tax_assessed_value",
        )),
        square_feet=parse_int(_pick(
            flat,
            "square_feet", "sqft", "sq_ft", "living_area", "living_square_feet", "living_sqft",
            "building_area", "building_square_feet", "building_sqft", "gross_living_area",
            "finished_sqft", "structure_area", "property_sqft", "universal_building_square_feet",
            "total_building_area", "area_building", "gross_sqft", "building_sqft",
        )),
        year_built=parse_int(_pick(
            flat,
            "year_built", "yr_built", "built", "construction_year", "actual_year_built",
            "building_year_built", "effective_year_built",
        )),
        beds=parse_float(_pick(
            flat,
            "beds", "bedrooms", "bed_count", "bedroom_count", "bedrooms_count",
            "total_bedrooms", "room_bed_count",
        )),
        baths=baths,
        last_sold_date=parse_date(_pick(
            flat,
            "last_sold_date", "last_sale_date", "deed_sale_date", "sale_date", "sold_date",
            "ownership_transfer_date", "last_transfer_date", "instrument_date", "recording_date",
            "deed_date", "sale_recording_date", "last_market_sale_date", "transfer_date", "prior_sale_date",
        )),
        last_sold_amount=parse_decimal(_pick(
            flat,
            "last_sold_amount", "last_sale_amount", "deed_sale_price", "sale_price", "sale_amount",
            "sold_amount", "last_sale_price", "transfer_amount", "consideration", "deed_amount",
            "last_market_sale_amount", "prior_sale_amount",
        )),
        garage=str(_pick(flat, "garage", "garage_type", "garage_description") or "").strip() or None,
        garage_sqft=parse_int(_pick(flat, "garage_sqft", "garage_square_feet", "garage_area", "garage_area_sqft")),
        parking_spaces=_parse_parking_spaces(_pick(flat, "parking_spaces", "garage_spaces", "garage_parking_spaces", "covered_parking_spaces")),
        tax_assess_year=parse_int(_pick(flat, "tax_assess_year", "assessment_year", "assess_year")),
        assessor_taxroll_update=parse_date(_pick(flat, "assessor_taxroll_update", "taxroll_update", "tax_roll_update")),
        assessor_last_update=parse_date(_pick(flat, "assessor_last_update", "last_assessor_update", "tax_roll_last_update")),
        publication_date=parse_date(_pick(flat, "publication_date", "data_publication_date", "file_publication_date")),
        source=source,
        raw=record,
    )

    data.garage_summary = _garage_summary(data.garage, data.garage_sqft, data.parking_spaces)

    if all(getattr(data, field) is None for field in (
        "latest_assessed_value", "square_feet", "year_built", "beds", "baths", "last_sold_date",
        "last_sold_amount", "garage", "garage_summary", "garage_sqft", "parking_spaces",
        "tax_assess_year", "assessor_taxroll_update", "assessor_last_update", "publication_date"
    )):
        return None
    return data


class SmartyPropertyDataClient(PropertyLookupClient):
    """
    Smarty-only property data client.

    Recommended path:
      GET https://us-enrichment.api.smarty.com/lookup/search/property

    Fallback path if address-search property enrichment is not enabled on your plan:
      1) GET https://us-street.api.smarty.com/street-address?match=enhanced
      2) GET https://us-enrichment.api.smarty.com/lookup/{smarty_key}/property
    """

    def __init__(self, auth_id: Optional[str] = None, auth_token: Optional[str] = None):
        self.auth_id = (auth_id or os.getenv("SMARTY_AUTH_ID") or os.getenv("SMARTY_API_KEY") or "").strip()
        self.auth_token = (auth_token or os.getenv("SMARTY_AUTH_TOKEN") or "").strip()
        if not self.auth_id or not self.auth_token:
            raise RuntimeError(
                "Smarty mode requires SMARTY_AUTH_ID and SMARTY_AUTH_TOKEN. "
                "Do not paste them into ChatGPT; put them in your .env file."
            )

        self.default_state = os.getenv("SMARTY_DEFAULT_STATE", "VA").strip()
        self.timeout = float(os.getenv("SMARTY_TIMEOUT_SECONDS", "30"))
        self.rate_limit = float(os.getenv("SMARTY_RATE_LIMIT_SECONDS", "0.15"))
        self.use_enrichment_search = _env_bool("SMARTY_USE_ENRICHMENT_SEARCH", True)
        self.include = os.getenv("SMARTY_INCLUDE", "").strip()
        self.exclude = os.getenv("SMARTY_EXCLUDE", "").strip()
        self.enrichment_base_url = os.getenv("SMARTY_ENRICHMENT_BASE_URL", "https://us-enrichment.api.smarty.com").rstrip("/")
        self.street_url = os.getenv("SMARTY_STREET_URL", "https://us-street.api.smarty.com/street-address").strip()
        self.session = requests.Session()

    def _auth_params(self) -> dict[str, str]:
        return {"auth-id": self.auth_id, "auth-token": self.auth_token}

    def _headers(self) -> dict[str, str]:
        return {"Accept": "application/json"}

    def _enrichment_params(self, address: str, city: Optional[str]) -> dict[str, str]:
        params = self._auth_params()
        if city:
            params.update({"street": address, "city": city})
            if self.default_state:
                params["state"] = self.default_state
        else:
            freeform = address
            if self.default_state and not re.search(r"\b[A-Z]{2}\b", address.upper()):
                freeform = f"{address}, {self.default_state}"
            params["freeform"] = freeform
        if self.include:
            params["include"] = self.include
        if self.exclude:
            params["exclude"] = self.exclude
        return params

    def _handle_common_errors(self, response: requests.Response, api_name: str) -> None:
        if response.status_code == 401:
            raise RuntimeError(f"{api_name} returned 401 Unauthorized. Check SMARTY_AUTH_ID and SMARTY_AUTH_TOKEN.")
        if response.status_code == 402:
            raise RuntimeError(f"{api_name} returned 402 Payment Required. Your account may not include US Property Data.")
        if response.status_code == 429:
            raise RuntimeError(f"{api_name} returned 429 Rate Limit. Increase SMARTY_RATE_LIMIT_SECONDS.")
        response.raise_for_status()

    def _get_property_by_search(self, address: str, city: Optional[str]) -> Optional[PropertyData]:
        url = f"{self.enrichment_base_url}/lookup/search/property"
        response = self.session.get(url, params=self._enrichment_params(address, city), headers=self._headers(), timeout=self.timeout)
        if response.status_code in (204, 404):
            return None
        self._handle_common_errors(response, "Smarty Enrichment address search")
        if not response.content:
            return None
        return property_data_from_smarty_payload(response.json(), source="smarty_property_data_search")

    def _get_smarty_key(self, address: str, city: Optional[str]) -> Optional[str]:
        params = self._auth_params()
        params.update({"street": address, "candidates": "1", "match": "enhanced"})
        if city:
            params["city"] = city
        if self.default_state:
            params["state"] = self.default_state
        response = self.session.get(self.street_url, params=params, headers=self._headers(), timeout=self.timeout)
        self._handle_common_errors(response, "Smarty Street API")
        candidates = response.json() if response.content else []
        if not candidates:
            return None
        key = candidates[0].get("smarty_key") if isinstance(candidates[0], dict) else None
        return str(key).strip() if key else None

    def _get_property_by_smarty_key(self, smarty_key: str) -> Optional[PropertyData]:
        url = f"{self.enrichment_base_url}/lookup/{smarty_key}/property"
        params = self._auth_params()
        if self.include:
            params["include"] = self.include
        if self.exclude:
            params["exclude"] = self.exclude
        response = self.session.get(url, params=params, headers=self._headers(), timeout=self.timeout)
        if response.status_code in (204, 404):
            return None
        self._handle_common_errors(response, "Smarty Enrichment API")
        if not response.content:
            return None
        return property_data_from_smarty_payload(response.json(), source="smarty_property_data_key")

    def lookup(self, address: str, city: Optional[str] = None) -> Optional[PropertyData]:
        if self.rate_limit > 0:
            time.sleep(self.rate_limit)
        if self.use_enrichment_search:
            return self._get_property_by_search(address, city)
        key = self._get_smarty_key(address, city)
        if not key:
            return None
        return self._get_property_by_smarty_key(key)
