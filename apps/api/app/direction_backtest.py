from collections import Counter
from datetime import date, datetime

from sqlalchemy.orm import Session

from .config import Settings
from .forecast import rolling_cn_cpi_forecast_backtest

CLASSES = ("down", "stable", "up")


def rolling_cn_cpi_direction_backtest(
    session: Session,
    start: date,
    end: date,
    settings: Settings,
    neutral_band: float = 0.2,
    minimum_training_labels: int = 4,
) -> dict:
    regression = rolling_cn_cpi_forecast_backtest(
        session, start, end, settings, horizon_months=6, minimum_training_labels=1
    )
    candidates = []
    for row in regression["forecasts"]:
        actual_change = row["actual_future_average"] - row["current_cpi"]
        trend_change = row["predictions"]["trend_3m"] - row["current_cpi"]
        candidates.append(
            {
                "cutoff": datetime.fromisoformat(row["cutoff"]),
                "target_end_month": date.fromisoformat(row["target_end_month"]),
                "score": row["environment_score"],
                "actual": _label(actual_change, neutral_band),
                "trend": _label(trend_change, neutral_band),
            }
        )
    predictions = []
    maximum_training_labels = 0
    for candidate in candidates:
        matured = [
            row
            for row in candidates
            if row["target_end_month"] < candidate["cutoff"].date().replace(day=1)
        ]
        maximum_training_labels = max(maximum_training_labels, len(matured))
        if len(matured) < minimum_training_labels:
            continue
        counts = Counter(row["actual"] for row in matured)
        majority = max(CLASSES, key=lambda label: (counts[label], -CLASSES.index(label)))
        centroids = {
            label: sum(row["score"] for row in matured if row["actual"] == label) / counts[label]
            for label in CLASSES
            if counts[label]
        }
        score_model = min(
            centroids,
            key=lambda label: (abs(candidate["score"] - centroids[label]), CLASSES.index(label)),
        )
        predictions.append(
            {
                "cutoff": candidate["cutoff"].isoformat(),
                "target_end_month": candidate["target_end_month"].isoformat(),
                "training_label_count": len(matured),
                "environment_score": candidate["score"],
                "actual": candidate["actual"],
                "predictions": {
                    "score_nearest_centroid": score_model,
                    "always_stable": "stable",
                    "expanding_majority": majority,
                    "trend_3m": candidate["trend"],
                },
            }
        )
    metrics = {
        model: _classification_metrics(predictions, model)
        for model in (
            "score_nearest_centroid",
            "always_stable",
            "expanding_majority",
            "trend_3m",
        )
    }
    model_f1 = metrics["score_nearest_centroid"]["macro_f1"]
    baseline_f1 = max(
        metrics[name]["macro_f1"] or 0
        for name in ("always_stable", "expanding_majority", "trend_3m")
    )
    reasons = []
    if len(predictions) < 12:
        reasons.append("fewer than 12 genuine walk-forward classifications")
    if model_f1 is None or model_f1 <= baseline_f1:
        reasons.append("score classifier does not beat the best baseline on macro F1")
    return {
        "backtest_id": "cn-cpi-direction-6m-v0.1",
        "mode": "expanding_window_out_of_sample",
        "target": "direction of next-6-month average CPI versus current CPI",
        "neutral_band_percentage_points": neutral_band,
        "minimum_training_labels": minimum_training_labels,
        "candidate_count": len(candidates),
        "maximum_matured_training_labels": maximum_training_labels,
        "prediction_count": len(predictions),
        "actual_class_counts": dict(Counter(row["actual"] for row in predictions)),
        "metrics": metrics,
        "predictive_readiness": "fail" if reasons else "pass",
        "predictive_readiness_reasons": reasons,
        "claim_status": "diagnostic_only",
        "warning": "Small, overlapping samples; classification performance is exploratory.",
        "predictions": predictions,
    }


def _label(change: float, band: float) -> str:
    if change > band:
        return "up"
    if change < -band:
        return "down"
    return "stable"


def _classification_metrics(rows: list[dict], model: str) -> dict:
    if not rows:
        return {"accuracy": None, "macro_f1": None, "balanced_accuracy": None}
    actual = [row["actual"] for row in rows]
    predicted = [row["predictions"][model] for row in rows]
    f1_scores = []
    recalls = []
    for label in CLASSES:
        pairs = list(zip(actual, predicted, strict=True))
        true_positive = sum(a == label and p == label for a, p in pairs)
        false_positive = sum(a != label and p == label for a, p in pairs)
        false_negative = sum(a == label and p != label for a, p in pairs)
        support = sum(a == label for a in actual)
        if support:
            recalls.append(true_positive / support)
            denominator = 2 * true_positive + false_positive + false_negative
            f1_scores.append(2 * true_positive / denominator if denominator else 0.0)
    return {
        "accuracy": round(
            sum(a == p for a, p in zip(actual, predicted, strict=True)) / len(rows), 3
        ),
        "macro_f1": round(sum(f1_scores) / len(f1_scores), 3),
        "balanced_accuracy": round(sum(recalls) / len(recalls), 3),
    }
