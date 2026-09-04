from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Base
from app.seeds import seed_registry
from app.similarity_cards import build_cn_similarity_evidence_card


def test_similarity_card_refuses_when_no_evaluable_history() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_registry(session)
        card = build_cn_similarity_evidence_card(
            session, date(2021, 9, 1), date(2022, 1, 1), Settings()
        )
    assert card["status"] == "no_reliable_analogy"
    assert card["confidence"] == "low"
    assert card["cards"] == []
    assert card["refusal_reasons"]
