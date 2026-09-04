from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import Settings
from app.forecast import rolling_cn_cpi_forecast_backtest
from app.models import Base
from app.seeds import seed_registry


def test_forecast_backtest_is_diagnostic_when_sample_is_empty() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_registry(session)
        report = rolling_cn_cpi_forecast_backtest(
            session, date(2024, 1, 1), date(2024, 3, 1), Settings(), 6
        )
    assert report["mode"] == "expanding_window_out_of_sample"
    assert report["forecast_count"] == 0
    assert report["predictive_readiness"] == "fail"


def test_forecast_horizon_is_restricted() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_registry(session)
        try:
            rolling_cn_cpi_forecast_backtest(
                session, date(2024, 1, 1), date(2024, 3, 1), Settings(), 9
            )
        except ValueError as error:
            assert "6 or 12" in str(error)
        else:
            raise AssertionError("unsupported horizon should fail")
