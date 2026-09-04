import math
import statistics
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .backtest import rolling_cn_inflation_backtest_v4
from .config import Settings
from .features import add_months, latest_vintage_series, month_end
from .models import ObservationVintage


def rolling_cn_cpi_forecast_backtest(
    session: Session,
    start: date,
    end: date,
    settings: Settings,
    horizon_months: int = 6,
    minimum_training_labels: int = 8,
) -> dict:
    if horizon_months not in {6, 12}:
        raise ValueError("Forecast horizon must be 6 or 12 months")
    environment = rolling_cn_inflation_backtest_v4(session, start, end, settings)
    finalized, first_available = _finalized_cpi(session)
    candidates = []
    for point in environment["points"]:
        if point["indicator_count"] != 4:
            continue
        cutoff = datetime.fromisoformat(point["cutoff"])
        visible = latest_vintage_series(session, "NBS_CN_CPI_YOY", cutoff)
        visible = [row for row in visible if row.value is not None]
        if len(visible) < 4:
            continue
        anchor = month_end(visible[-1].observation_date)
        future_months = [add_months(anchor, offset) for offset in range(1, horizon_months + 1)]
        if any(month not in finalized for month in future_months):
            continue
        actual = statistics.mean(finalized[month] for month in future_months)
        available_at = max(first_available[month] for month in future_months)
        slope_3m = (float(visible[-1].value) - float(visible[-4].value)) / 3
        candidates.append(
            {
                "cutoff": cutoff,
                "anchor_month": anchor,
                "current_cpi": float(visible[-1].value),
                "score": float(point["score"]),
                "actual": actual,
                "actual_available_at": available_at,
                "persistence": float(visible[-1].value),
                "trend": float(visible[-1].value) + slope_3m * (horizon_months + 1) / 2,
            }
        )

    forecasts = []
    maximum_matured_training_labels = 0
    for candidate in candidates:
        matured = [
            row
            for row in candidates
            if row["cutoff"] < candidate["cutoff"]
            and _aware(row["actual_available_at"]) <= candidate["cutoff"]
        ]
        maximum_matured_training_labels = max(
            maximum_matured_training_labels, len(matured)
        )
        if len(matured) < minimum_training_labels:
            continue
        denominator = sum(row["score"] ** 2 for row in matured)
        beta = (
            sum(row["score"] * (row["actual"] - row["current_cpi"]) for row in matured)
            / denominator
            if denominator
            else 0.0
        )
        model = candidate["current_cpi"] + beta * candidate["score"]
        forecasts.append(
            {
                "cutoff": candidate["cutoff"].isoformat(),
                "anchor_month": candidate["anchor_month"].isoformat(),
                "target_end_month": add_months(
                    candidate["anchor_month"], horizon_months
                ).isoformat(),
                "training_label_count": len(matured),
                "beta": round(beta, 5),
                "current_cpi": round(candidate["current_cpi"], 3),
                "environment_score": round(candidate["score"], 2),
                "actual_future_average": round(candidate["actual"], 3),
                "predictions": {
                    "v0.4_score_calibrated": round(model, 3),
                    "persistence": round(candidate["persistence"], 3),
                    "trend_3m": round(candidate["trend"], 3),
                },
            }
        )
    metrics = {
        model: _metrics(forecasts, model)
        for model in ("v0.4_score_calibrated", "persistence", "trend_3m")
    }
    model_mae = metrics["v0.4_score_calibrated"]["mae"]
    baseline_values = [
        value
        for value in (metrics["persistence"]["mae"], metrics["trend_3m"]["mae"])
        if value is not None
    ]
    baseline_mae = min(baseline_values) if baseline_values else None
    reasons = []
    if len(forecasts) < 12:
        reasons.append("fewer than 12 genuine walk-forward forecasts")
    if model_mae is None or baseline_mae is None or model_mae >= baseline_mae:
        reasons.append("score-calibrated model does not beat the best simple baseline on MAE")
    return {
        "backtest_id": f"cn-cpi-walk-forward-{horizon_months}m-v0.1",
        "mode": "expanding_window_out_of_sample",
        "target": f"average CPI YoY over the next {horizon_months} observed months",
        "horizon_months": horizon_months,
        "minimum_training_labels": minimum_training_labels,
        "candidate_count": len(candidates),
        "maximum_matured_training_labels": maximum_matured_training_labels,
        "forecast_count": len(forecasts),
        "metrics": metrics,
        "predictive_readiness": "fail" if reasons else "pass",
        "predictive_readiness_reasons": reasons,
        "claim_status": "diagnostic_only",
        "warning": (
            "Overlapping horizons and a small sample make this exploratory, "
            "not personal advice."
        ),
        "forecasts": forecasts,
    }


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def _finalized_cpi(session: Session) -> tuple[dict[date, float], dict[date, datetime]]:
    rows = session.scalars(
        select(ObservationVintage)
        .where(
            ObservationVintage.indicator_id == "NBS_CN_CPI_YOY",
            ObservationVintage.value.is_not(None),
        )
        .order_by(ObservationVintage.observation_date, ObservationVintage.vintage_at)
    ).all()
    latest: dict[date, float] = {}
    first_available: dict[date, datetime] = {}
    for row in rows:
        key = month_end(row.observation_date)
        first_available.setdefault(key, row.vintage_at)
        latest[key] = float(row.value)
    return latest, first_available


def _metrics(forecasts: list[dict], model: str) -> dict:
    if not forecasts:
        return {"mae": None, "rmse": None, "directional_accuracy": None}
    errors = [row["predictions"][model] - row["actual_future_average"] for row in forecasts]
    direction_hits = []
    for row in forecasts:
        actual_change = row["actual_future_average"] - row["current_cpi"]
        predicted_change = row["predictions"][model] - row["current_cpi"]
        actual_direction = _direction(actual_change)
        predicted_direction = _direction(predicted_change)
        direction_hits.append(actual_direction == predicted_direction)
    return {
        "mae": round(statistics.mean(abs(error) for error in errors), 3),
        "rmse": round(math.sqrt(statistics.mean(error**2 for error in errors)), 3),
        "directional_accuracy": round(sum(direction_hits) / len(direction_hits), 3),
    }


def _direction(change: float, neutral_band: float = 0.05) -> int:
    if change > neutral_band:
        return 1
    if change < -neutral_band:
        return -1
    return 0
