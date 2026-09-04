from datetime import UTC, date, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.backtest import (
    rolling_cn_inflation_backtest,
    rolling_cn_inflation_backtest_v2,
    rolling_cn_inflation_backtest_v3,
    rolling_cn_inflation_backtest_v4,
)
from app.config import Settings
from app.models import Base, ObservationVintage
from app.seeds import seed_registry


def test_strict_backtest_uses_only_observations_available_by_cutoff() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_registry(session)
        for index in range(10):
            year = 2024
            month = index + 1
            observation_date = date(year, month, 28)
            release_year = year + (1 if month == 12 else 0)
            release_month = 1 if month == 12 else month + 1
            available_at = datetime(release_year, release_month, 10, 1, 30, tzinfo=UTC)
            for indicator_id, offset in (("NBS_CN_CPI_YOY", 0.0), ("NBS_CN_PPI_YOY", 1.0)):
                session.add(
                    ObservationVintage(
                        indicator_id=indicator_id,
                        observation_date=observation_date,
                        vintage_at=available_at,
                        value=float(index) + offset,
                        status="published",
                    )
                )
        session.commit()
        report = rolling_cn_inflation_backtest(
            session, date(2024, 6, 1), date(2024, 10, 1), Settings()
        )
    assert report["mode"] == "strict_vintage"
    assert report["point_count"] > 0
    for point in report["points"]:
        cutoff_month = point["cutoff"][:7]
        assert all(
            value[:7] <= cutoff_month for value in point["source_observation_dates"].values()
        )


def test_v2_backtest_marks_itself_as_diagnostic() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_registry(session)
        report = rolling_cn_inflation_backtest_v2(
            session, date(2024, 1, 1), date(2024, 3, 1), Settings()
        )
    assert report["backtest_id"].endswith("v0.2")
    assert report["claim_status"] == "diagnostic_only"
    assert report["model_readiness"] == "fail"


def test_v3_backtest_marks_itself_as_diagnostic() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_registry(session)
        report = rolling_cn_inflation_backtest_v3(
            session, date(2024, 1, 1), date(2024, 3, 1), Settings()
        )
    assert report["backtest_id"].endswith("v0.3")
    assert report["claim_status"] == "diagnostic_only"


def test_v4_backtest_marks_itself_as_diagnostic() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_registry(session)
        report = rolling_cn_inflation_backtest_v4(
            session, date(2024, 1, 1), date(2024, 3, 1), Settings()
        )
    assert report["backtest_id"].endswith("v0.4")
    assert report["claim_status"] == "diagnostic_only"
