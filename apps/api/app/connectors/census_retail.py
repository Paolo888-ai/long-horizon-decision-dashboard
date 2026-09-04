import re
from calendar import monthrange
from datetime import UTC, date, datetime

import httpx

from .base import ConnectorError, FetchResult, Observation, request_with_retry


class CensusRetailConnector:
    """Official Census MARTS adjusted retail and food services text series."""

    url = "https://www.census.gov/retail/marts/www/adv44X72.txt"

    def __init__(self, client: httpx.Client | None = None) -> None:
        self.client = client or httpx.Client(timeout=30, follow_redirects=True)

    def fetch(self) -> FetchResult:
        response = request_with_retry(self.client, "GET", self.url)
        if response.status_code != 200:
            raise ConnectorError(f"Census returned HTTP {response.status_code}")
        observations = self.parse(response.content)
        return FetchResult(
            source_id="census_us",
            request_url=str(response.request.url),
            media_type=response.headers.get("content-type", "text/plain"),
            retrieved_at=datetime.now(UTC),
            raw_content=response.content,
            observations=tuple(observations),
        )

    @staticmethod
    def parse(content: bytes) -> list[Observation]:
        text = content.decode("utf-8", errors="replace")
        sales_section = text.split("SEASONAL FACTORS", maxsplit=1)[0]
        rows: list[Observation] = []
        for line in sales_section.splitlines():
            match = re.match(r"^\s*(20\d{2}|19\d{2})\s+(.+?)\s*$", line)
            if match is None:
                continue
            year = int(match.group(1))
            values = re.findall(r"\d+(?:\.\d+)?", match.group(2))
            for month, raw_value in enumerate(values[:12], start=1):
                rows.append(
                    Observation(
                        date(year, month, monthrange(year, month)[1]),
                        float(raw_value),
                    )
                )
        if not rows:
            raise ConnectorError("Census retail file contained no monthly sales rows")
        return rows
