from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.connectors.base import FetchResult, Observation
from app.ingestion import content_hash, store_fetch_result
from app.models import Base, ObservationVintage, RawAsset
from app.quality import build_quality_report
from app.seeds import build_indicator_seed, seed_registry


def session_for_test() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_seed_has_expected_indicators_for_every_geography() -> None:
    rows = build_indicator_seed()
    assert len(rows) == 35
    assert sum(row["geography"] == "CN" for row in rows) == 11
    assert sum(row["geography"] == "US" for row in rows) == 9
    assert sum(row["geography"] == "JP" for row in rows) == 11
    assert sum(row["geography"] == "GLOBAL" for row in rows) == 4


def test_ingestion_persists_raw_asset_metadata_and_vintage(tmp_path: Path) -> None:
    raw = b'{"value": 4.2}'
    result = FetchResult(
        source_id="world_bank",
        request_url="https://api.worldbank.org/test",
        media_type="application/json",
        retrieved_at=datetime(2026, 8, 15, 4, 0, tzinfo=UTC),
        raw_content=raw,
        observations=(Observation(date(2024, 12, 31), 4.2),),
    )
    with session_for_test() as session:
        seed_registry(session)
        asset = store_fetch_result(session, "WB_CN_GDP_GROWTH", result, tmp_path)
        assert asset.content_hash == content_hash(raw)
        assert Path(asset.storage_path).read_bytes() == raw
        assert len(list(session.scalars(select(RawAsset)).all())) == 1
        vintage = session.scalar(select(ObservationVintage))
        assert vintage is not None
        assert vintage.value == 4.2
        report = build_quality_report(session)
        assert report["raw_asset_count"] == 1
        assert report["indicators_with_observations"] == 1
        assert report["experimental_scoring_ready"] is False
        assert report["readiness_reasons"]


def test_ingestion_uses_source_availability_without_losing_retrieval_time(tmp_path: Path) -> None:
    released = datetime(2025, 2, 9, 1, 30, tzinfo=UTC)
    retrieved = datetime(2026, 8, 15, 4, 0, tzinfo=UTC)
    result = FetchResult(
        source_id="nbs_cn",
        request_url="https://www.stats.gov.cn/release.html",
        media_type="text/html",
        retrieved_at=retrieved,
        raw_content=b"official release",
        observations=(Observation(date(2025, 1, 31), 0.5, available_at=released),),
    )
    with session_for_test() as session:
        seed_registry(session)
        asset = store_fetch_result(session, "NBS_CN_CPI_YOY", result, tmp_path)
        observation = session.scalar(select(ObservationVintage))
        assert observation is not None
        assert observation.vintage_at.replace(tzinfo=UTC) == released
        assert asset.retrieved_at.replace(tzinfo=UTC) == retrieved


def test_ingestion_is_idempotent_for_same_indicator_date_and_vintage(tmp_path: Path) -> None:
    released = datetime(2024, 1, 12, 1, 30, tzinfo=UTC)
    result = FetchResult(
        source_id="nbs_cn",
        request_url="https://www.stats.gov.cn/release.html",
        media_type="text/html",
        retrieved_at=datetime(2026, 8, 16, tzinfo=UTC),
        raw_content=b"same official release",
        observations=(Observation(date(2023, 12, 31), -0.3, available_at=released),),
    )
    with session_for_test() as session:
        seed_registry(session)
        store_fetch_result(session, "NBS_CN_CPI_YOY", result, tmp_path)
        store_fetch_result(session, "NBS_CN_CPI_YOY", result, tmp_path)
        assert len(session.scalars(select(ObservationVintage)).all()) == 1
