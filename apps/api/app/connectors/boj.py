from calendar import monthrange
from datetime import UTC, date, datetime, timedelta

import httpx

from .base import ConnectorError, FetchResult, Observation, request_with_retry


class BojConnector:
    source_id = "boj"
    endpoint = "https://www.stat-search.boj.or.jp/api/v1/getDataCode"

    def __init__(self, client: httpx.Client | None = None) -> None:
        self.client = client or httpx.Client(timeout=30, follow_redirects=True)

    def fetch(self, database: str, series_code: str, start: str, end: str) -> FetchResult:
        response = request_with_retry(
            self.client,
            "GET",
            self.endpoint,
            params={
                "format": "json",
                "lang": "en",
                "db": database,
                "startDate": start,
                "endDate": end,
                "code": series_code,
            },
        )
        if response.status_code != 200:
            raise ConnectorError(f"BOJ returned HTTP {response.status_code}")
        payload = response.json()
        series = self._find_series(payload)
        observations = self._parse_series(series)
        return FetchResult(
            source_id=self.source_id,
            request_url=str(response.request.url),
            media_type=response.headers.get("content-type", "application/json"),
            retrieved_at=datetime.now(UTC),
            raw_content=response.content,
            observations=observations,
        )

    @staticmethod
    def _find_series(payload: object) -> dict:
        if isinstance(payload, dict):
            result_set = payload.get("RESULTSET")
            if isinstance(result_set, list) and result_set and isinstance(result_set[0], dict):
                return result_set[0]
            for key in ("data", "result", "observations"):
                rows = payload.get(key)
                if isinstance(rows, list) and rows and isinstance(rows[0], dict):
                    return {"FREQUENCY": "MONTHLY", "ROWS": rows}
        if isinstance(payload, list) and payload and isinstance(payload[0], dict):
            return {"FREQUENCY": "MONTHLY", "ROWS": payload}
        raise ConnectorError("BOJ response has an unexpected shape")

    @staticmethod
    def _parse_series(series: dict) -> tuple[Observation, ...]:
        if "ROWS" in series:
            return tuple(BojConnector._parse_flat_row(row) for row in series["ROWS"])
        values = series.get("VALUES", {})
        dates = values.get("SURVEY_DATES", [])
        observations = values.get("VALUES", [])
        if not isinstance(dates, list) or not isinstance(observations, list):
            raise ConnectorError("BOJ values have an unexpected shape")
        if len(dates) != len(observations):
            raise ConnectorError("BOJ dates and values have different lengths")
        frequency = series.get("FREQUENCY", "MONTHLY")
        parsed = []
        for period, value in zip(dates, observations, strict=True):
            observation_date = BojConnector._period_date(str(period), frequency)
            parsed.append(
                Observation(
                    observation_date=observation_date,
                    value=None if value in (None, "", "NA") else float(value),
                    status="missing" if value in (None, "", "NA") else "published",
                    available_at=(
                        datetime.combine(
                            observation_date + timedelta(days=31), datetime.min.time(), UTC
                        )
                        if frequency == "QUARTERLY"
                        else None
                    ),
                )
            )
        return tuple(parsed)

    @staticmethod
    def _parse_flat_row(row: dict) -> Observation:
        period = str(row.get("date") or row.get("time") or row.get("period"))
        raw_value = row.get("value")
        return Observation(
            observation_date=BojConnector._period_date(period, "MONTHLY"),
            value=None if raw_value in (None, "", "NA") else float(raw_value),
            status="missing" if raw_value in (None, "", "NA") else "published",
        )

    @staticmethod
    def _period_date(period: str, frequency: str) -> date:
        if len(period) == 6 and frequency == "QUARTERLY":
            quarter = int(period[4:])
            if quarter not in (1, 2, 3, 4):
                raise ConnectorError(f"Invalid BOJ quarter: {period}")
            month = quarter * 3
            return date(int(period[:4]), month, monthrange(int(period[:4]), month)[1])
        if len(period) == 6:
            return date(int(period[:4]), int(period[4:]), 1)
        if len(period) == 8:
            return date(int(period[:4]), int(period[4:6]), int(period[6:]))
        return date.fromisoformat(period)
