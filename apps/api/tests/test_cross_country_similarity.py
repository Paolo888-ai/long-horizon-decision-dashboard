from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.cross_country_similarity import build_cn_jp_inflation_similarity
from app.models import Base


def test_cn_jp_similarity_fails_safely_without_history() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        report = build_cn_jp_inflation_similarity(session, datetime(2026, 8, 15, tzinfo=UTC))
    assert report["readiness"] == "fail"
    assert report["candidates"] == []
