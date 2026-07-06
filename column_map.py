from dataclasses import dataclass


@dataclass(frozen=True)
class WorkbookColumns:
    address: str = "B"
    latest_assessed_value: str = "F"
    square_feet: str = "N"
    year_built: str = "O"
    beds: str = "P"
    baths: str = "Q"
    last_sold_date: str = "U"
    last_sold_amount: str = "V"


COLUMNS = WorkbookColumns()
DEFAULT_START_ROW = 2
