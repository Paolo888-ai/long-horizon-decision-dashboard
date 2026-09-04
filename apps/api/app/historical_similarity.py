import statistics
from datetime import date, datetime

from sqlalchemy.orm import Session

from .backtest import CN_INFLATION_V4_IDS, rolling_cn_inflation_backtest_v4
from .config import Settings
from .features import add_months, latest_vintage_series, month_end
from .forecast import _aware, _finalized_cpi


def backtest_cn_inflation_similarity(
    session: Session,
    start: date,
    end: date,
    settings: Settings,
    horizon_months: int = 6,
    neighbor_count: int = 3,
) -> dict:
    environment = rolling_cn_inflation_backtest_v4(session, start, end, settings)
    finalized, first_available = _finalized_cpi(session)
    points = [point for point in environment["points"] if point["indicator_count"] == 4]
    enriched = []
    for index, point in enumerate(points):
        cutoff = datetime.fromisoformat(point["cutoff"])
        cpi = [
            row
            for row in latest_vintage_series(session, "NBS_CN_CPI_YOY", cutoff)
            if row.value is not None
        ]
        if not cpi:
            continue
        anchor = month_end(cpi[-1].observation_date)
        future = [add_months(anchor, offset) for offset in range(1, horizon_months + 1)]
        if any(month not in finalized for month in future):
            continue
        actual = statistics.mean(finalized[month] for month in future)
        outcome_available = max(first_available[month] for month in future)
        enriched.append(
            {
                "index": index,
                "cutoff": cutoff,
                "anchor": anchor,
                "score": point["score"],
                "signals": point["signals"],
                "current_cpi": float(cpi[-1].value),
                "actual": actual,
                "delta": actual - float(cpi[-1].value),
                "outcome_available": _aware(outcome_available),
            }
        )
    evaluations = []
    previous_neighbors: set[str] | None = None
    jaccards = []
    for target in enriched:
        candidates = [
            row
            for row in enriched
            if row["cutoff"] < target["cutoff"] and row["outcome_available"] <= target["cutoff"]
        ]
        ranked = []
        for candidate in candidates:
            state_similarity = _state_similarity(target["signals"], candidate["signals"])
            trajectory_similarity = _trajectory_similarity(
                points, target["index"], candidate["index"]
            )
            total = 0.5 * state_similarity + 0.5 * trajectory_similarity
            ranked.append((total, state_similarity, trajectory_similarity, candidate))
        ranked.sort(key=lambda item: (-item[0], item[3]["cutoff"]))
        selected = []
        for item in ranked:
            candidate = item[3]
            if any(
                abs(
                    (candidate["anchor"].year - prior[3]["anchor"].year) * 12
                    + candidate["anchor"].month
                    - prior[3]["anchor"].month
                )
                < 6
                for prior in selected
            ):
                continue
            selected.append(item)
            if len(selected) == neighbor_count:
                break
        if len(selected) < neighbor_count:
            continue
        analog_delta = statistics.median(item[3]["delta"] for item in selected)
        prediction = target["current_cpi"] + analog_delta
        neighbor_ids = {item[3]["cutoff"].date().isoformat() for item in selected}
        if previous_neighbors is not None:
            union = previous_neighbors | neighbor_ids
            jaccards.append(len(previous_neighbors & neighbor_ids) / len(union))
        previous_neighbors = neighbor_ids
        evaluations.append(
            {
                "cutoff": target["cutoff"].isoformat(),
                "current_cpi": round(target["current_cpi"], 3),
                "actual_future_average": round(target["actual"], 3),
                "analog_prediction": round(prediction, 3),
                "persistence_prediction": round(target["current_cpi"], 3),
                "neighbor_outcome_range": round(
                    max(item[3]["delta"] for item in selected)
                    - min(item[3]["delta"] for item in selected),
                    3,
                ),
                "neighbors": [
                    {
                        "historical_cutoff": item[3]["cutoff"].isoformat(),
                        "total_similarity": round(item[0], 1),
                        "state_similarity": round(item[1], 1),
                        "trajectory_similarity": round(item[2], 1),
                        "subsequent_cpi_change": round(item[3]["delta"], 3),
                        "closest_subthemes": _subtheme_comparison(
                            target["signals"], item[3]["signals"], largest=False
                        ),
                        "largest_subtheme_gaps": _subtheme_comparison(
                            target["signals"], item[3]["signals"], largest=True
                        ),
                    }
                    for item in selected
                ],
            }
        )
    analog_errors = [
        abs(row["analog_prediction"] - row["actual_future_average"]) for row in evaluations
    ]
    persistence_errors = [
        abs(row["persistence_prediction"] - row["actual_future_average"]) for row in evaluations
    ]
    analog_mae = round(statistics.mean(analog_errors), 3) if analog_errors else None
    persistence_mae = round(statistics.mean(persistence_errors), 3) if persistence_errors else None
    reasons = []
    if len(evaluations) < 12:
        reasons.append("fewer than 12 evaluable historical-analogy forecasts")
    if analog_mae is None or persistence_mae is None or analog_mae >= persistence_mae:
        reasons.append("historical analog median does not beat CPI persistence on MAE")
    return {
        "backtest_id": "cn-inflation-historical-similarity-v0.1",
        "scope": "China inflation subthemes only",
        "state_weight": 0.5,
        "trajectory_weight": 0.5,
        "trajectory_window_months": 6,
        "event_separation_months": 6,
        "neighbor_count": neighbor_count,
        "evaluation_count": len(evaluations),
        "analog_mae": analog_mae,
        "persistence_mae": persistence_mae,
        "mean_neighbor_outcome_range": (
            round(statistics.mean(row["neighbor_outcome_range"] for row in evaluations), 3)
            if evaluations
            else None
        ),
        "mean_consecutive_neighbor_jaccard": (
            round(statistics.mean(jaccards), 3) if jaccards else None
        ),
        "readiness": "fail" if reasons else "pass",
        "readiness_reasons": reasons,
        "claim_status": "diagnostic_only",
        "limitations": [
            "Only one country and one dimension are available; no structural reranking.",
            (
                "The 10-year exclusion and 36-month trajectory from the PRD are "
                "impossible with current history."
            ),
            "Similarity is a reference aid, not evidence that history will repeat.",
        ],
        "evaluations": evaluations,
    }


def _state_similarity(left: dict[str, float], right: dict[str, float]) -> float:
    differences = [abs(left[key] - right[key]) for key in CN_INFLATION_V4_IDS]
    return max(0.0, 100.0 - statistics.mean(differences) / 2)


def _trajectory_similarity(points: list[dict], left_index: int, right_index: int) -> float:
    window = 6
    if left_index < window - 1 or right_index < window - 1:
        return 0.0
    left = [points[index]["score"] for index in range(left_index - window + 1, left_index + 1)]
    right = [points[index]["score"] for index in range(right_index - window + 1, right_index + 1)]
    difference = statistics.mean(abs(a - b) for a, b in zip(left, right, strict=True))
    return max(0.0, 100.0 - difference / 2)


def _subtheme_comparison(
    current: dict[str, float], historical: dict[str, float], *, largest: bool
) -> list[dict]:
    labels = {
        "NBS_CN_GOODS_CPI_YOY": "consumer_goods_prices",
        "NBS_CN_SERVICES_CPI_YOY": "services_prices",
        "NBS_CN_PPI_YOY": "producer_prices",
        "PBC_CN_PRICE_EXPECTATION": "household_price_expectations",
    }
    rows = [
        {
            "subtheme": labels[indicator_id],
            "current_signal": round(current[indicator_id], 2),
            "historical_signal": round(historical[indicator_id], 2),
            "absolute_gap": round(abs(current[indicator_id] - historical[indicator_id]), 2),
        }
        for indicator_id in CN_INFLATION_V4_IDS
    ]
    rows.sort(key=lambda row: row["absolute_gap"], reverse=largest)
    return rows[:2]
