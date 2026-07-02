from __future__ import annotations
import json, time
from typing import Any
from urllib.parse import urlencode
import requests

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 property-data-job/9.0 (+official public records lookup; contact: user-run local script)",
    "Accept": "application/json,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

class HttpClient:
    def __init__(self, timeout: int = 25, retries: int = 2):
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        self.timeout = timeout
        self.retries = retries

    def get(self, url: str, **kwargs) -> requests.Response:
        last = None
        for i in range(self.retries + 1):
            try:
                r = self.session.get(url, timeout=self.timeout, **kwargs)
                return r
            except requests.RequestException as e:
                last = e
                time.sleep(1 + i)
        raise last

    def post(self, url: str, **kwargs) -> requests.Response:
        last = None
        for i in range(self.retries + 1):
            try:
                r = self.session.post(url, timeout=self.timeout, **kwargs)
                return r
            except requests.RequestException as e:
                last = e
                time.sleep(1 + i)
        raise last

    def socrata(self, base: str, resource: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        url = f"{base}/resource/{resource}.json?{urlencode(params)}"
        r = self.get(url)
        r.raise_for_status()
        return r.json()
