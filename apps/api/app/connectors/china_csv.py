import csv
import io
from datetime import UTC, date, datetime
from pathlib import Path

from .base import ConnectorError, FetchResult, Observation


class ChinaOfficialCsvConnector:
    source_id = "nbs_cn"

    def fetch(self, path: Path, source_url: str) -> FetchResult:
        raw_content = path.read_bytes()
        text = raw_content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames or not {"date", "value"}.issubset(reader.fieldnames):
            raise ConnectorError("CSV must contain date and value columns")
        observations = []
        for row in reader:
            raw_value = row["value"].strip()
            observations.append(
                Observation(
                    observation_date=date.fromisoformat(row["date"]),
                    value=None if not raw_value else float(raw_value),
                    status="missing" if not raw_value else "published",
                )
            )
        return FetchResult(
            source_id=self.source_id,
            request_url=source_url,
            media_type="text/csv",
            retrieved_at=datetime.now(UTC),
            raw_content=raw_content,
            observations=tuple(observations),
        )
