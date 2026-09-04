from calendar import monthrange
from datetime import datetime, time

from .config import Settings


def cutoff_for_month(year: int, month: int, settings: Settings) -> datetime:
    last_day = monthrange(year, month)[1]
    day = min(settings.publication_cutoff_day, last_day)
    hour, minute = (int(part) for part in settings.publication_cutoff_time.split(":"))
    return datetime.combine(
        datetime(year, month, day).date(),
        time(hour, minute),
        tzinfo=settings.timezone,
    )


def is_observation_eligible(released_at: datetime, cutoff: datetime) -> bool:
    if released_at.tzinfo is None or cutoff.tzinfo is None:
        raise ValueError("released_at and cutoff must be timezone-aware")
    return released_at <= cutoff
