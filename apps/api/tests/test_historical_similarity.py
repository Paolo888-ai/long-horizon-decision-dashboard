from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import Settings
from app.historical_similarity import backtest_cn_inflation_similarity
from app.models import Base
from app.seeds import seed_registry


def test_similarity_backtest_fails_safely_without_history() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_registry(session)
        report = backtest_cn_inflation_similarity(
            session, date(2021, 9, 1), date(2022, 1, 1), Settings()
        )
    assert report["evaluation_count"] == 0
    assert report["readiness"] == "fail"
    assert report["limitations"]
