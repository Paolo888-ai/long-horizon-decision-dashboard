from datetime import UTC, date, datetime

import httpx

from .base import ConnectorError, FetchResult, Observation


class WorldBankConnector:
    source_id = "world_bank"
    base_url = "https://api.worldbank.org/v2"

    def __init__(self, client: httpx.Client | None = None) -> None:
        self.client = client or httpx.Client(timeout=30, follow_redirects=True)

    def fetch(self, country: str, indicator: str, start_year: int = 1960) -> FetchResult:
        url = f"{self.base_url}/country/{country}/indicator/{indicator}"
        response = self.client.get(
            url,
            params={"format": "json", "per_page": 20000, "date": f"{start_year}:2100"},
        )
        if response.status_code != 200:
            raise ConnectorError(f"World Bank returned HTTP {response.status_code}")
        payload = response.json()
        if not isinstance(payload, list) or len(payload) < 2 or not isinstance(payload[1], list):
            raise ConnectorError("World Bank response has an unexpected shape")
        observations = tuple(
            Observation(observation_date=date(int(row["date"]), 12, 31), value=row["value"])
            for row in payload[1]
            if row.get("date") and row.get("value") is not None
        )
        return FetchResult(
            source_id=self.source_id,
            request_url=str(response.request.url),
            media_type=response.headers.get("content-type", "application/json"),
            retrieved_at=datetime.now(UTC),
            raw_content=response.content,
            observations=observations,
        )
