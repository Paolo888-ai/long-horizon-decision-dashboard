from datetime import UTC, date, datetime

import httpx

from .base import ConnectorError, FetchResult, Observation


class BlsConnector:
    source_id = "bls"
    endpoint = "https://api.bls.gov/publicAPI/v2/timeseries/data/"

    def __init__(self, client: httpx.Client | None = None) -> None:
        self.client = client or httpx.Client(timeout=30, follow_redirects=True)

    def fetch(self, series_id: str) -> FetchResult:
        response = self.client.get(f"{self.endpoint}{series_id}")
        if response.status_code != 200:
            raise ConnectorError(f"BLS returned HTTP {response.status_code}")
        payload = response.json()
        if payload.get("status") != "REQUEST_SUCCEEDED":
            raise ConnectorError(f"BLS request failed: {payload.get('message')}")
        try:
            rows = payload["Results"]["series"][0]["data"]
        except (KeyError, IndexError, TypeError) as error:
            raise ConnectorError("BLS response has an unexpected shape") from error
        observations = []
        for row in rows:
            period = row.get("period", "")
            if not (period.startswith("M") and period[1:].isdigit() and 1 <= int(period[1:]) <= 12):
                continue
            observations.append(
                Observation(
                    observation_date=date(int(row["year"]), int(period[1:]), 1),
                    value=float(row["value"]),
                    status="preliminary" if self._is_preliminary(row) else "published",
                )
            )
        return FetchResult(
            source_id=self.source_id,
            request_url=str(response.request.url),
            media_type=response.headers.get("content-type", "application/json"),
            retrieved_at=datetime.now(UTC),
            raw_content=response.content,
            observations=tuple(observations),
        )

    @staticmethod
    def _is_preliminary(row: dict) -> bool:
        return any(
            footnote and footnote.get("code") == "P" for footnote in row.get("footnotes", [])
        )
