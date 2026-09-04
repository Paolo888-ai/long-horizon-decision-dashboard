from datetime import UTC, date, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.features import build_indicator_features, robust_z
from app.models import Base, IndicatorDefinition, ObservationVintage
from app.seeds import seed_registry


def feature_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    seed_registry(session)
    return session


def add_observation(
    session: Session,
    indicator_id: str,
    observation_date: date,
    value: float,
    vintage_at: datetime,
) -> None:
    session.add(
        ObservationVintage(
            indicator_id=indicator_id,
            observation_date=observation_date,
            value=value,
            vintage_at=vintage_at,
            status="published",
        )
    )
    session.commit()


def test_feature_builder_does_not_use_vintage_after_cutoff() -> None:
    cutoff = datetime(2026, 8, 15, 15, 59, tzinfo=UTC)
    with feature_session() as session:
        indicator = session.get(IndicatorDefinition, "BLS_US_UNEMPLOYMENT")
        assert indicator is not None
        add_observation(session, indicator.id, date(2026, 6, 1), 4.1, cutoff)
        add_observation(
            session,
            indicator.id,
            date(2026, 7, 1),
            9.9,
            datetime(2026, 8, 16, tzinfo=UTC),
        )
        rows = build_indicator_features(session, indicator, cutoff)
        assert rows[-1].source_observation_date == date(2026, 6, 1)
        assert rows[-1].level == 4.1


def test_rolling_cutoffs_reveal_revision_only_after_release() -> None:
    july_cutoff = datetime(2026, 7, 15, 15, 59, tzinfo=UTC)
    august_cutoff = datetime(2026, 8, 15, 15, 59, tzinfo=UTC)
    with feature_session() as session:
        indicator = session.get(IndicatorDefinition, "BLS_US_UNEMPLOYMENT")
        assert indicator is not None
        add_observation(
            session, indicator.id, date(2026, 6, 1), 4.0,
            datetime(2026, 7, 10, tzinfo=UTC),
        )
        add_observation(
            session, indicator.id, date(2026, 6, 1), 4.2,
            datetime(2026, 8, 10, tzinfo=UTC),
        )
        july_rows = build_indicator_features(session, indicator, july_cutoff)
        august_rows = build_indicator_features(session, indicator, august_cutoff)
        assert july_rows[-1].level == 4.0
        assert august_rows[-1].level == 4.2


def test_quarterly_feature_is_carried_with_decay() -> None:
    cutoff = datetime(2026, 8, 15, 15, 59, tzinfo=UTC)
    with feature_session() as session:
        indicator = session.get(IndicatorDefinition, "BOJ_JP_TANKAN_MANUFACTURING")
        assert indicator is not None
        add_observation(session, indicator.id, date(2026, 6, 30), 13.0, cutoff)
        rows = build_indicator_features(session, indicator, cutoff)
        assert rows[-1].month == date(2026, 8, 31)
        assert rows[-1].is_carried_forward is True
        assert 0 < rows[-1].freshness_weight < 1


def test_robust_z_resists_one_outlier() -> None:
    score = robust_z([1, 1, 2, 2, 3, 100], 3)
    assert 0 < score < 2
