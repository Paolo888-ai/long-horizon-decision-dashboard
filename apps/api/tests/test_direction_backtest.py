from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import Settings
from app.direction_backtest import rolling_cn_cpi_direction_backtest
from app.models import Base
from app.seeds import seed_registry


def test_direction_backtest_fails_safely_without_history() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_registry(session)
        report = rolling_cn_cpi_direction_backtest(
            session, date(2022, 11, 1), date(2023, 1, 1), Settings()
        )
    assert report["prediction_count"] == 0
    assert report["predictive_readiness"] == "fail"
    assert report["claim_status"] == "diagnostic_only"
