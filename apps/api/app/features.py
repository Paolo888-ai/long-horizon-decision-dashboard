import math
import statistics
from calendar import monthrange
from datetime import UTC, date, datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .models import FeatureMonthly, IndicatorDefinition, ObservationVintage

HALF_LIFE_MONTHS = {"D": 1.0, "W": 1.0, "M": 3.0, "Q": 6.0, "A": 18.0}
MAX_CARRY_MONTHS = {"D": 1, "W": 1, "M": 2, "Q": 5, "A": 24}


def month_end(value: date) -> date:
    return date(value.year, value.month, monthrange(value.year, value.month)[1])


def add_months(value: date, count: int) -> date:
    index = value.year * 12 + value.month - 1 + count
    year, month_index = divmod(index, 12)
    month = month_index + 1
    return date(year, month, monthrange(year, month)[1])


def months_between(earlier: date, later: date) -> int:
    return (later.year - earlier.year) * 12 + later.month - earlier.month


def latest_vintage_series(
    session: Session, indicator_id: str, cutoff: datetime
) -> list[ObservationVintage]:
    database_cutoff = cutoff
    if session.get_bind().dialect.name == "sqlite" and cutoff.tzinfo is not None:
        database_cutoff = cutoff.astimezone(UTC).replace(tzinfo=None)
    rows = session.scalars(
        select(ObservationVintage)
        .where(
            ObservationVintage.indicator_id == indicator_id,
            ObservationVintage.vintage_at <= database_cutoff,
            ObservationVintage.observation_date <= cutoff.date(),
        )
        .order_by(
            ObservationVintage.observation_date,
            ObservationVintage.vintage_at.desc(),
        )
    ).all()
    latest: dict[date, ObservationVintage] = {}
    for row in rows:
        latest.setdefault(row.observation_date, row)
    return [latest[key] for key in sorted(latest)]


def robust_z(values: list[float], current: float) -> float:
    median = statistics.median(values)
    deviations = [abs(value - median) for value in values]
    mad = statistics.median(deviations)
    if mad == 0:
        return 0.0
    return max(-8.0, min(8.0, 0.6745 * (current - median) / mad))


def build_indicator_features(
    session: Session,
    indicator: IndicatorDefinition,
    cutoff: datetime,
) -> list[FeatureMonthly]:
    observations = [
        row for row in latest_vintage_series(session, indicator.id, cutoff) if row.value is not None
    ]
    if not observations:
        return []
    by_month = {month_end(row.observation_date): row for row in observations}
    first_month = min(by_month)
    last_month = month_end(cutoff.date())
    half_life = HALF_LIFE_MONTHS.get(indicator.frequency, 6.0)
    max_carry = MAX_CARRY_MONTHS.get(indicator.frequency, 6)
    rows: list[FeatureMonthly] = []
    history: list[float] = []
    current_month = first_month
    last_observation: ObservationVintage | None = None
    levels: list[float | None] = []
    while current_month <= last_month:
        if current_month in by_month:
            last_observation = by_month[current_month]
        age = (
            None
            if last_observation is None
            else months_between(month_end(last_observation.observation_date), current_month)
        )
        value = (
            None
            if last_observation is None or age is None or age > max_carry
            else last_observation.value
        )
        if value is None:
            levels.append(None)
            current_month = add_months(current_month, 1)
            continue
        history.append(value)
        levels.append(value)
        momentum = value - levels[-4] if len(levels) >= 4 and levels[-4] is not None else None
        change_12m = value - levels[-13] if len(levels) >= 13 and levels[-13] is not None else None
        freshness = math.exp(-math.log(2) * age / half_life)
        rows.append(
            FeatureMonthly(
                indicator_id=indicator.id,
                month=current_month,
                vintage_cutoff=cutoff,
                source_observation_date=last_observation.observation_date,
                level=value,
                robust_z=robust_z(history, value) if len(history) >= 5 else None,
                momentum_3m=momentum,
                change_12m=change_12m,
                freshness_weight=freshness,
                is_carried_forward=age > 0,
            )
        )
        current_month = add_months(current_month, 1)
    return rows


def build_all_features(session: Session, cutoff: datetime) -> dict:
    session.execute(delete(FeatureMonthly).where(FeatureMonthly.vintage_cutoff == cutoff))
    indicators = session.scalars(
        select(IndicatorDefinition).where(IndicatorDefinition.active.is_(True))
    ).all()
    counts = {}
    for indicator in indicators:
        rows = build_indicator_features(session, indicator, cutoff)
        session.add_all(rows)
        counts[indicator.id] = len(rows)
    session.commit()
    return {
        "vintage_cutoff": cutoff.isoformat(),
        "indicator_count": len(indicators),
        "indicators_with_features": sum(count > 0 for count in counts.values()),
        "feature_row_count": sum(counts.values()),
        "rows_by_indicator": counts,
    }
