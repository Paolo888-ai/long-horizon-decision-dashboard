from datetime import datetime

import pytest

from app.config import Settings
from app.publication import cutoff_for_month, is_observation_eligible


def test_cutoff_uses_shanghai_time() -> None:
    settings = Settings()
    cutoff = cutoff_for_month(2026, 8, settings)
    assert cutoff.isoformat() == "2026-08-15T23:59:00+08:00"


def test_data_after_cutoff_is_ineligible() -> None:
    settings = Settings()
    cutoff = cutoff_for_month(2026, 8, settings)
    release = datetime(2026, 8, 16, 0, 0, tzinfo=settings.timezone)
    assert not is_observation_eligible(release, cutoff)


def test_naive_datetimes_are_rejected() -> None:
    with pytest.raises(ValueError):
        is_observation_eligible(datetime(2026, 8, 15), datetime(2026, 8, 15))
