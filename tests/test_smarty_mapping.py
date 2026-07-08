import json
from pathlib import Path

from clients.smarty_property_data import property_data_from_smarty_payload


def test_smarty_mapping():
    payload = json.loads(Path("tests/sample_smarty_property_response.json").read_text())
    data = property_data_from_smarty_payload(payload)
    assert data is not None
    assert data.latest_assessed_value == 215000
    assert data.square_feet == 1425
    assert data.year_built == 1964
    assert data.beds == 3
    assert data.baths == 1.5
    assert data.last_sold_amount == 188000

    assert data.garage_code == "A"
    assert data.garage_sqft == 420
