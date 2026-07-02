from abc import ABC, abstractmethod
from typing import Optional

from models import PropertyData


class PropertyLookupClient(ABC):
    @abstractmethod
    def lookup(self, address: str, city: Optional[str] = None) -> Optional[PropertyData]:
        """Return property data for one address, or None when no reliable match is found."""
        raise NotImplementedError

    def close(self) -> None:
        """Optional cleanup hook for clients that hold network resources."""
        return None
