import csv
import io
from datetime import UTC, date, datetime
from pathlib import Path

from .base import ConnectorError, FetchResult, Observation


class JapanCpiCsvConnector:
    """Parse the official e-Stat goods/services year-on-year time-series CSV."""

    source_id = "estat_jp"
    columns = {
        "all_items": "All items",
        "goods": "Goods",
        "services": "Services",
    }

    def fetch(self, path: Path, series: str, source_url: str, released_at: datetime) -> FetchResult:
        if series not in self.columns:
            raise ConnectorError(f"Unsupported Japan CPI series: {series}")
        if released_at.tzinfo is None:
            raise ConnectorError("Japan CPI release timestamp must be timezone-aware")
        content = path.read_bytes()
        observations = self.parse(content, series, released_at)
        return FetchResult(
            source_id=self.source_id,
            request_url=source_url,
            media_type="text/csv; charset=shift_jis",
            retrieved_at=datetime.now(UTC),
            raw_content=content,
            observations=observations,
        )

    @classmethod
    def parse(cls, content: bytes, series: str, released_at: datetime) -> tuple[Observation, ...]:
        try:
            text = content.decode("cp932")
        except UnicodeDecodeError as error:
            raise ConnectorError("Japan CPI CSV is not valid Shift-JIS/CP932") from error
        rows = list(csv.reader(io.StringIO(text)))
        if len(rows) < 7:
            raise ConnectorError("Japan CPI CSV has too few rows")
        english_header = rows[1]
        column_name = cls.columns.get(series)
        if column_name is None or column_name not in english_header:
            raise ConnectorError(f"Japan CPI column is missing: {series}")
        column = english_header.index(column_name)
        observations = []
        for row in rows[6:]:
            if not row or len(row[0]) != 6 or not row[0].isdigit():
                continue
            value = row[column].strip() if column < len(row) else ""
            year, month = int(row[0][:4]), int(row[0][4:])
            observations.append(
                Observation(
                    observation_date=date(year, month, 1),
                    value=None if value in {"", "-"} else float(value),
                    status="missing" if value in {"", "-"} else "published",
                    available_at=released_at,
                )
            )
        if not observations:
            raise ConnectorError("Japan CPI CSV contains no monthly observations")
        return tuple(observations)
