from datetime import UTC, date, datetime

import httpx

from .base import ConnectorError, FetchResult, Observation


class FredConnector:
    source_id = "fred"
    endpoint = "https://api.stlouisfed.org/fred/series/observations"

    def __init__(self, api_key: str, client: httpx.Client | None = None) -> None:
        if not api_key:
            raise ValueError("FRED_API_KEY is required")
        self.api_key = api_key
        self.client = client or httpx.Client(timeout=30, follow_redirects=True)

    def fetch(self, series_id: str, realtime_start: str | None = None) -> FetchResult:
        params = {"series_id": series_id, "api_key": self.api_key, "file_type": "json"}
        if realtime_start:
            params["realtime_start"] = realtime_start
            params["realtime_end"] = realtime_start
        response = self.client.get(self.endpoint, params=params)
        if response.status_code != 200:
            raise ConnectorError(f"FRED returned HTTP {response.status_code}")
        payload = response.json()
        rows = payload.get("observations")
        if not isinstance(rows, list):
            raise ConnectorError("FRED response has an unexpected shape")
        observations = tuple(
            Observation(
                observation_date=date.fromisoformat(row["date"]),
                value=None if row["value"] == "." else float(row["value"]),
                status="missing" if row["value"] == "." else "published",
            )
            for row in rows
        )
        return FetchResult(
            source_id=self.source_id,
            request_url=str(response.request.url).replace(self.api_key, "***"),
            media_type=response.headers.get("content-type", "application/json"),
            retrieved_at=datetime.now(UTC),
            raw_content=response.content,
            observations=observations,
        )
