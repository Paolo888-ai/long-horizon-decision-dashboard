from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import FeatureMonthly, IndicatorDefinition
from .quality import build_quality_report


def build_experimental_environment(session: Session, geography: str) -> dict | None:
    quality = build_quality_report(session)
    if not quality["experimental_scoring_ready"]:
        return None
    cutoff = session.scalar(select(func.max(FeatureMonthly.vintage_cutoff)))
    if cutoff is None:
        return None
    indicators = session.scalars(
        select(IndicatorDefinition).where(
            IndicatorDefinition.active.is_(True),
            IndicatorDefinition.geography == geography,
        )
    ).all()
    by_dimension: dict[str, list[tuple[IndicatorDefinition, FeatureMonthly]]] = defaultdict(list)
    for indicator in indicators:
        feature = session.scalars(
            select(FeatureMonthly)
            .where(
                FeatureMonthly.indicator_id == indicator.id,
                FeatureMonthly.vintage_cutoff == cutoff,
                FeatureMonthly.robust_z.is_not(None),
            )
            .order_by(FeatureMonthly.month.desc())
            .limit(1)
        ).first()
        if feature is not None:
            by_dimension[indicator.dimension].append((indicator, feature))
    dimensions = []
    defined_counts: dict[str, int] = defaultdict(int)
    for indicator in indicators:
        defined_counts[indicator.dimension] += 1
    for dimension, rows in sorted(by_dimension.items()):
        weights = [row.freshness_weight for _, row in rows]
        weighted_z = sum((row.robust_z or 0) * weight for (_, row), weight in zip(rows, weights))
        average_z = weighted_z / sum(weights)
        score = max(-100.0, min(100.0, average_z * 25))
        momenta = [row.momentum_3m for _, row in rows if row.momentum_3m is not None]
        mean_momentum = sum(momenta) / len(momenta) if momenta else 0
        confidence = "high" if len(rows) >= 3 else "medium" if len(rows) >= 2 else "low"
        dimensions.append(
            {
                "dimension": dimension,
                "score": round(score, 1),
                "state": _state(score),
                "direction": "rising" if mean_momentum > 0 else "falling" if mean_momentum < 0 else "stable",
                "confidence": confidence,
                "coverage": round(len(rows) / defined_counts[dimension] * 100, 1),
                "indicator_ids": [indicator.id for indicator, _ in rows],
            }
        )
    return {
        "geography": geography,
        "cutoff": cutoff.isoformat(),
        "model_version": "transparent-baseline-v0.1-experimental",
        "is_experimental": True,
        "decision_use": "research_only",
        "warning": "Scores describe standardized conditions, not good/bad outcomes or personal advice.",
        "dimensions": dimensions,
        "missing_dimensions": sorted(
            {"TECH", "REAL", "CREDIT", "INFLATION", "DEMOGRAPHY", "GEOPOLITICS"}
            - set(by_dimension)
        ),
    }


def _state(score: float) -> str:
    if score <= -50:
        return "very_low"
    if score < -15:
        return "low"
    if score <= 15:
        return "neutral"
    if score < 50:
        return "high"
    return "very_high"
