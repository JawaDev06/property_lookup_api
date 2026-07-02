from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any

@dataclass
class PropertyResult:
    address: str
    city: Optional[str] = None
    assessed_value: Optional[float] = None
    sqft: Optional[float] = None
    year_built: Optional[int] = None
    beds: Optional[float] = None
    baths: Optional[float] = None
    source_url: Optional[str] = None
    status: str = "not_started"
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
