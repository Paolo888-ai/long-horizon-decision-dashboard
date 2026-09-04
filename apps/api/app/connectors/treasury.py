from datetime import UTC, date, datetime
from xml.etree import ElementTree

import httpx

from .base import ConnectorError, FetchResult, Observation, request_with_retry


class TreasuryYieldCurveConnector:
    """Official U.S. Treasury daily par-yield XML feed."""

    base_url = (
        "https://home.treasury.gov/resource-center/data-chart-center/"
        "interest-rates/pages/xml"
    )

    def __init__(self, client: httpx.Client | None = None) -> None:
        self.client = client or httpx.Client(timeout=30, follow_redirects=True)

    def fetch(self, year: int) -> FetchResult:
        params = {
            "data": "daily_treasury_yield_curve",
            "field_tdr_date_value": str(year),
        }
        response = request_with_retry(self.client, "GET", self.base_url, params=params)
        if response.status_code != 200:
            raise ConnectorError(f"Treasury returned HTTP {response.status_code}")
        observations = self.parse(response.content)
        return FetchResult(
            source_id="treasury_us",
            request_url=str(response.request.url),
            media_type=response.headers.get("content-type", "application/atom+xml"),
            retrieved_at=datetime.now(UTC),
            raw_content=response.content,
            observations=tuple(observations),
        )

    @staticmethod
    def parse(content: bytes) -> list[Observation]:
        try:
            root = ElementTree.fromstring(content)
        except ElementTree.ParseError as error:
            raise ConnectorError("Treasury response is not valid XML") from error
        rows: list[Observation] = []
        for properties in root.iter():
            if properties.tag.rsplit("}", 1)[-1] != "properties":
                continue
            values = {child.tag.rsplit("}", 1)[-1]: child.text for child in properties}
            raw_date = values.get("NEW_DATE") or values.get("Date")
            two_year = values.get("BC_2YEAR") or values.get("BC_2_YR")
            ten_year = values.get("BC_10YEAR") or values.get("BC_10_YR")
            if not raw_date or not two_year or not ten_year:
                continue
            try:
                observation_date = date.fromisoformat(raw_date[:10])
                spread = float(ten_year) - float(two_year)
            except (TypeError, ValueError):
                continue
            rows.append(Observation(observation_date, spread))
        if not rows:
            raise ConnectorError("Treasury XML contained no usable 10Y-2Y observations")
        return sorted(rows, key=lambda row: row.observation_date)
