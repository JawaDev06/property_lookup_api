from dataclasses import dataclass


@dataclass(frozen=True)
class WorkbookColumns:
    address: str = "B"
    latest_assessed_value: str = "F"
    square_feet: str = "N"
    year_built: str = "O"
    beds: str = "P"
    baths: str = "Q"
    garage: str = "R"


COLUMNS = WorkbookColumns()
DEFAULT_START_ROW = 2
