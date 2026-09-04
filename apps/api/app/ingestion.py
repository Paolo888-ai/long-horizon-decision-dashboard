import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from .connectors.base import FetchResult
from .models import ObservationVintage, RawAsset


def content_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def store_fetch_result(
    session: Session,
    indicator_id: str,
    result: FetchResult,
    raw_root: Path,
) -> RawAsset:
    digest = content_hash(result.raw_content)
    vintage = result.retrieved_at.astimezone(UTC)
    relative_dir = Path(result.source_id) / vintage.strftime("%Y-%m-%d")
    target_dir = raw_root / relative_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    if "pdf" in result.media_type:
        extension = ".pdf"
    elif "json" in result.media_type:
        extension = ".json"
    elif "xml" in result.media_type:
        extension = ".xml"
    elif "html" in result.media_type:
        extension = ".html"
    else:
        extension = ".csv"
    content_path = target_dir / f"{digest}{extension}"
    metadata_path = target_dir / f"{digest}.metadata.json"
    if not content_path.exists():
        content_path.write_bytes(result.raw_content)
    metadata = {
        "source_id": result.source_id,
        "indicator_id": indicator_id,
        "request_url": result.request_url,
        "retrieved_at": vintage.isoformat(),
        "content_hash": digest,
        "media_type": result.media_type,
        "byte_size": len(result.raw_content),
        "observation_count": len(result.observations),
    }
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    asset = RawAsset(
        content_hash=digest,
        source_id=result.source_id,
        retrieved_at=vintage,
        request_url=result.request_url,
        media_type=result.media_type,
        storage_path=str(content_path),
        byte_size=len(result.raw_content),
    )
    session.merge(asset)
    for observation in result.observations:
        available_at = observation.available_at or vintage
        if available_at.tzinfo is None:
            raise ValueError("Observation availability time must be timezone-aware")
        normalized_available_at = available_at.astimezone(UTC)
        database_available_at = normalized_available_at
        if session.get_bind().dialect.name == "sqlite":
            database_available_at = normalized_available_at.replace(tzinfo=None)
        existing = session.scalars(
            select(ObservationVintage).where(
                ObservationVintage.indicator_id == indicator_id,
                ObservationVintage.observation_date == observation.observation_date,
                ObservationVintage.vintage_at == database_available_at,
            )
        ).first()
        if existing is not None:
            existing.value = observation.value
            existing.status = observation.status
            existing.raw_asset_hash = digest
            continue
        session.add(
            ObservationVintage(
                indicator_id=indicator_id,
                observation_date=observation.observation_date,
                vintage_at=normalized_available_at,
                value=observation.value,
                status=observation.status,
                raw_asset_hash=digest,
            )
        )
    session.commit()
    return asset


def now_utc() -> datetime:
    return datetime.now(UTC)
