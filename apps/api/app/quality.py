from collections import Counter
from datetime import UTC, datetime

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from .models import FeatureMonthly, IndicatorDefinition, ObservationVintage, RawAsset


def build_quality_report(session: Session) -> dict:
    indicators = list(session.scalars(select(IndicatorDefinition)).all())
    geography_counts = Counter(indicator.geography for indicator in indicators)
    active_ids = {indicator.id for indicator in indicators if indicator.active}
    observed_ids = set(session.scalars(select(distinct(ObservationVintage.indicator_id))).all())
    observation_count = session.scalar(select(func.count()).select_from(ObservationVintage)) or 0
    raw_asset_count = session.scalar(select(func.count()).select_from(RawAsset)) or 0
    feature_row_count = session.scalar(select(func.count()).select_from(FeatureMonthly)) or 0
    feature_indicator_count = (
        session.scalar(select(func.count(distinct(FeatureMonthly.indicator_id)))) or 0
    )
    missing_ids = sorted(active_ids - observed_ids)
    coverage = (
        0 if not active_ids else round(len(active_ids & observed_ids) / len(active_ids) * 100, 1)
    )
    high_frequency_ids: dict[str, set[str]] = {}
    for indicator in indicators:
        if indicator.active and indicator.frequency in {"D", "W", "M", "Q"}:
            high_frequency_ids.setdefault(indicator.geography, set()).add(indicator.id)
    high_frequency_coverage = {
        geography: {
            "defined": len(ids),
            "observed": len(ids & observed_ids),
            "percent": round(len(ids & observed_ids) / len(ids) * 100, 1) if ids else 0,
        }
        for geography, ids in sorted(high_frequency_ids.items())
    }
    core_high_frequency_ready = all(
        high_frequency_coverage.get(geography, {}).get("observed", 0) >= 1
        for geography in ("CN", "US", "JP")
    )
    history_months: dict[str, int] = {}
    mature_indicators: dict[str, int] = {}
    for geography, ids in high_frequency_ids.items():
        dates = session.scalars(
            select(ObservationVintage.observation_date).where(
                ObservationVintage.indicator_id.in_(ids)
            )
        ).all()
        history_months[geography] = len({(item.year, item.month) for item in dates})
        mature = 0
        for indicator_id in ids:
            indicator_dates = session.scalars(
                select(ObservationVintage.observation_date).where(
                    ObservationVintage.indicator_id == indicator_id
                )
            ).all()
            if len({(item.year, item.month) for item in indicator_dates}) >= 24:
                mature += 1
        mature_indicators[geography] = mature
    readiness_reasons: list[str] = []
    for geography in ("CN", "US", "JP"):
        mature = mature_indicators.get(geography, 0)
        months = history_months.get(geography, 0)
        if mature < 2:
            readiness_reasons.append(f"{geography} needs at least 2 high-frequency indicators with 24 months each")
        if months < 24:
            readiness_reasons.append(f"{geography} needs at least 24 months of high-frequency history")
    experimental_scoring_ready = coverage >= 70 and not readiness_reasons
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "indicator_count": len(indicators),
        "active_indicator_count": len(active_ids),
        "geography_indicator_counts": dict(sorted(geography_counts.items())),
        "indicators_with_observations": len(active_ids & observed_ids),
        "coverage_percent": coverage,
        "observation_vintage_count": observation_count,
        "raw_asset_count": raw_asset_count,
        "feature_row_count": feature_row_count,
        "indicators_with_features": feature_indicator_count,
        "missing_indicator_ids": missing_ids,
        "high_frequency_coverage": high_frequency_coverage,
        "high_frequency_history_months": history_months,
        "mature_high_frequency_indicators": mature_indicators,
        "experimental_scoring_ready": experimental_scoring_ready,
        "readiness_reasons": readiness_reasons,
        "status": "pass" if coverage >= 70 and core_high_frequency_ready else "incomplete",
    }
