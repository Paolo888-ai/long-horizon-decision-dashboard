import statistics
from datetime import date

from sqlalchemy.orm import Session

from .config import Settings
from .features import build_indicator_features
from .models import IndicatorDefinition
from .publication import cutoff_for_month

CN_INFLATION_IDS = ("NBS_CN_CPI_YOY", "NBS_CN_PPI_YOY")
CN_INFLATION_V2_IDS = (
    "NBS_CN_CPI_YOY",
    "NBS_CN_CORE_CPI_YOY",
    "NBS_CN_PPI_YOY",
)
CN_INFLATION_V3_IDS = (
    "NBS_CN_GOODS_CPI_YOY",
    "NBS_CN_SERVICES_CPI_YOY",
    "NBS_CN_PPI_YOY",
)
CN_INFLATION_V4_IDS = (*CN_INFLATION_V3_IDS, "PBC_CN_PRICE_EXPECTATION")


def rolling_cn_inflation_backtest(
    session: Session, start: date, end: date, settings: Settings
) -> dict:
    points = []
    cursor = date(start.year, start.month, 1)
    while cursor <= end:
        cutoff = cutoff_for_month(cursor.year, cursor.month, settings)
        signals: dict[str, float] = {}
        source_dates: dict[str, str] = {}
        for indicator_id in CN_INFLATION_IDS:
            indicator = session.get(IndicatorDefinition, indicator_id)
            if indicator is None:
                continue
            rows = build_indicator_features(session, indicator, cutoff)
            eligible = [row for row in rows if row.robust_z is not None]
            if not eligible:
                continue
            latest = eligible[-1]
            raw_signal = (latest.robust_z or 0) * 25 * latest.freshness_weight
            signals[indicator_id] = max(-100, min(100, raw_signal))
            source_dates[indicator_id] = latest.source_observation_date.isoformat()
        if signals:
            score = sum(signals.values()) / len(signals)
            loo = [abs(score - value) for value in signals.values()] if len(signals) > 1 else []
            points.append(
                {
                    "cutoff": cutoff.isoformat(),
                    "score": round(max(-100, min(100, score)), 2),
                    "state": _state(score),
                    "indicator_count": len(signals),
                    "signals": {key: round(value, 2) for key, value in signals.items()},
                    "source_observation_dates": source_dates,
                    "max_leave_one_out_delta": round(max(loo), 2) if loo else None,
                }
            )
        cursor = _next_month(cursor)
    scores = [point["score"] for point in points]
    changes = [later - earlier for earlier, later in zip(scores, scores[1:])]
    flips = sum(left["state"] != right["state"] for left, right in zip(points, points[1:]))
    turning_points = sum(previous * current < 0 for previous, current in zip(changes, changes[1:]))
    runs: list[int] = []
    for point in points:
        if not runs or point["state"] != points[sum(runs) - 1]["state"]:
            runs.append(1)
        else:
            runs[-1] += 1
    sensitivities = [
        point["max_leave_one_out_delta"]
        for point in points
        if point["max_leave_one_out_delta"] is not None
    ]
    monthly_change_std = round(statistics.pstdev(changes), 2) if changes else None
    max_sensitivity = round(max(sensitivities), 2) if sensitivities else None
    readiness_reasons = []
    if len(points) < 24:
        readiness_reasons.append("fewer than 24 evaluable monthly cutoffs")
    if monthly_change_std is None or monthly_change_std > 15:
        readiness_reasons.append("monthly score-change volatility exceeds 15 points")
    if max_sensitivity is None or max_sensitivity > 25:
        readiness_reasons.append("single-indicator removal changes score by more than 25 points")
    return {
        "backtest_id": "cn-inflation-strict-vintage-v0.1",
        "mode": "strict_vintage",
        "start": start.isoformat(),
        "end": end.isoformat(),
        "cutoff_rule": "Asia/Shanghai day 15 23:59",
        "point_count": len(points),
        "two_indicator_point_count": sum(point["indicator_count"] == 2 for point in points),
        "state_flip_count": flips,
        "turning_point_count": turning_points,
        "one_month_state_run_count": sum(length == 1 for length in runs),
        "monthly_change_std": monthly_change_std,
        "mean_leave_one_out_delta": (
            round(statistics.mean(sensitivities), 2) if sensitivities else None
        ),
        "max_leave_one_out_delta": max_sensitivity,
        "model_readiness": "fail" if readiness_reasons else "pass",
        "model_readiness_reasons": readiness_reasons,
        "claim_status": "diagnostic_only",
        "warning": "This tests vintage integrity and score stability, not predictive accuracy.",
        "points": points,
    }


def rolling_cn_inflation_backtest_v2(
    session: Session, start: date, end: date, settings: Settings
) -> dict:
    raw_points = []
    cursor = date(start.year, start.month, 1)
    while cursor <= end:
        cutoff = cutoff_for_month(cursor.year, cursor.month, settings)
        signals: dict[str, float] = {}
        source_dates: dict[str, str] = {}
        for indicator_id in CN_INFLATION_V2_IDS:
            indicator = session.get(IndicatorDefinition, indicator_id)
            if indicator is None:
                continue
            eligible = [
                row
                for row in build_indicator_features(session, indicator, cutoff)
                if row.robust_z is not None
            ]
            if not eligible:
                continue
            latest = eligible[-1]
            value = (latest.robust_z or 0) * 25 * latest.freshness_weight
            signals[indicator_id] = max(-100, min(100, value))
            source_dates[indicator_id] = latest.source_observation_date.isoformat()
        if signals:
            raw_score = _v2_aggregate(signals)
            loo = [
                abs(
                    raw_score
                    - _v2_aggregate(
                        {key: value for key, value in signals.items() if key != removed}
                    )
                )
                for removed in signals
                if len(signals) > 1
            ]
            raw_points.append(
                {
                    "cutoff": cutoff.isoformat(),
                    "raw_score": raw_score,
                    "indicator_count": len(signals),
                    "signals": {key: round(value, 2) for key, value in signals.items()},
                    "source_observation_dates": source_dates,
                    "max_leave_one_out_delta": round(max(loo), 2) if loo else None,
                }
            )
        cursor = _next_month(cursor)
    points = []
    confirmed_state: str | None = None
    previous_candidate: str | None = None
    for index, raw_point in enumerate(raw_points):
        window = raw_points[max(0, index - 2) : index + 1]
        score = sum(item["raw_score"] for item in window) / len(window)
        smoothed_loo = []
        for removed in CN_INFLATION_V2_IDS:
            alternative = []
            for item in window:
                remaining = {key: value for key, value in item["signals"].items() if key != removed}
                if remaining:
                    alternative.append(_v2_aggregate(remaining))
            if alternative:
                smoothed_loo.append(abs(score - sum(alternative) / len(alternative)))
        candidate = _state(score)
        if confirmed_state is None:
            confirmed_state = candidate
        elif candidate != confirmed_state and candidate == previous_candidate:
            confirmed_state = candidate
        point = dict(raw_point)
        point["raw_score"] = round(raw_point["raw_score"], 2)
        point["score"] = round(score, 2)
        point["candidate_state"] = candidate
        point["state"] = confirmed_state
        point["max_leave_one_out_delta"] = round(max(smoothed_loo), 2) if smoothed_loo else None
        points.append(point)
        previous_candidate = candidate
    return _summarize_v2(points, start, end)


def _v2_aggregate(signals: dict[str, float]) -> float:
    consumer = [signals[key] for key in ("NBS_CN_CPI_YOY", "NBS_CN_CORE_CPI_YOY") if key in signals]
    subthemes = []
    if consumer:
        subthemes.append(sum(consumer) / len(consumer))
    if "NBS_CN_PPI_YOY" in signals:
        subthemes.append(signals["NBS_CN_PPI_YOY"])
    return sum(subthemes) / len(subthemes) if subthemes else 0.0


def _summarize_v2(points: list[dict], start: date, end: date) -> dict:
    scores = [point["score"] for point in points]
    changes = [later - earlier for earlier, later in zip(scores, scores[1:])]
    sensitivities = [
        point["max_leave_one_out_delta"]
        for point in points
        if point["max_leave_one_out_delta"] is not None
    ]
    monthly_std = round(statistics.pstdev(changes), 2) if changes else None
    max_sensitivity = round(max(sensitivities), 2) if sensitivities else None
    reasons = []
    if len(points) < 24:
        reasons.append("fewer than 24 evaluable monthly cutoffs")
    if monthly_std is None or monthly_std > 15:
        reasons.append("monthly score-change volatility exceeds 15 points")
    if max_sensitivity is None or max_sensitivity > 25:
        reasons.append("single-indicator removal changes score by more than 25 points")
    return {
        "backtest_id": "cn-inflation-strict-vintage-v0.2",
        "mode": "strict_vintage",
        "start": start.isoformat(),
        "end": end.isoformat(),
        "point_count": len(points),
        "three_indicator_point_count": sum(point["indicator_count"] == 3 for point in points),
        "state_flip_count": sum(
            left["state"] != right["state"] for left, right in zip(points, points[1:])
        ),
        "turning_point_count": sum(a * b < 0 for a, b in zip(changes, changes[1:])),
        "monthly_change_std": monthly_std,
        "mean_leave_one_out_delta": round(statistics.mean(sensitivities), 2)
        if sensitivities
        else None,
        "max_leave_one_out_delta": max_sensitivity,
        "model_readiness": "fail" if reasons else "pass",
        "model_readiness_reasons": reasons,
        "claim_status": "diagnostic_only",
        "warning": "V0.2 adds subthemes, 3-month smoothing and two-cutoff state confirmation; it does not test predictive accuracy.",
        "points": points,
    }


def rolling_cn_inflation_backtest_v3(
    session: Session, start: date, end: date, settings: Settings
) -> dict:
    raw_points = []
    cursor = date(start.year, start.month, 1)
    while cursor <= end:
        cutoff = cutoff_for_month(cursor.year, cursor.month, settings)
        signals: dict[str, float] = {}
        source_dates: dict[str, str] = {}
        for indicator_id in CN_INFLATION_V3_IDS:
            indicator = session.get(IndicatorDefinition, indicator_id)
            if indicator is None:
                continue
            eligible = [
                row
                for row in build_indicator_features(session, indicator, cutoff)
                if row.robust_z is not None
            ]
            if not eligible:
                continue
            latest = eligible[-1]
            value = (latest.robust_z or 0) * 25 * latest.freshness_weight
            signals[indicator_id] = max(-100, min(100, value))
            source_dates[indicator_id] = latest.source_observation_date.isoformat()
        if signals:
            raw_score = sum(signals.values()) / len(signals)
            loo = [
                abs(
                    raw_score
                    - sum(value for key, value in signals.items() if key != removed)
                    / (len(signals) - 1)
                )
                for removed in signals
                if len(signals) > 1
            ]
            raw_points.append(
                {
                    "cutoff": cutoff.isoformat(),
                    "raw_score": raw_score,
                    "indicator_count": len(signals),
                    "signals": {key: round(value, 2) for key, value in signals.items()},
                    "source_observation_dates": source_dates,
                    "max_leave_one_out_delta": round(max(loo), 2) if loo else None,
                }
            )
        cursor = _next_month(cursor)
    points = []
    confirmed_state: str | None = None
    previous_candidate: str | None = None
    for index, raw_point in enumerate(raw_points):
        window = raw_points[max(0, index - 2) : index + 1]
        score = sum(item["raw_score"] for item in window) / len(window)
        smoothed_loo = []
        for removed in CN_INFLATION_V3_IDS:
            alternative = []
            for item in window:
                remaining = [value for key, value in item["signals"].items() if key != removed]
                if remaining:
                    alternative.append(sum(remaining) / len(remaining))
            if alternative:
                smoothed_loo.append(abs(score - sum(alternative) / len(alternative)))
        candidate = _state(score)
        if confirmed_state is None:
            confirmed_state = candidate
        elif candidate != confirmed_state and candidate == previous_candidate:
            confirmed_state = candidate
        point = dict(raw_point)
        point["raw_score"] = round(raw_point["raw_score"], 2)
        point["score"] = round(score, 2)
        point["candidate_state"] = candidate
        point["state"] = confirmed_state
        point["max_leave_one_out_delta"] = round(max(smoothed_loo), 2) if smoothed_loo else None
        points.append(point)
        previous_candidate = candidate
    return _summarize_v3(points, start, end)


def _summarize_v3(points: list[dict], start: date, end: date) -> dict:
    scores = [point["score"] for point in points]
    changes = [later - earlier for earlier, later in zip(scores, scores[1:])]
    sensitivities = [
        point["max_leave_one_out_delta"]
        for point in points
        if point["max_leave_one_out_delta"] is not None
    ]
    monthly_std = round(statistics.pstdev(changes), 2) if changes else None
    max_sensitivity = round(max(sensitivities), 2) if sensitivities else None
    reasons = []
    if len(points) < 24:
        reasons.append("fewer than 24 evaluable monthly cutoffs")
    if monthly_std is None or monthly_std > 15:
        reasons.append("monthly score-change volatility exceeds 15 points")
    if max_sensitivity is None or max_sensitivity > 25:
        reasons.append("single-subtheme removal changes score by more than 25 points")
    return {
        "backtest_id": "cn-inflation-strict-vintage-v0.3",
        "mode": "strict_vintage",
        "start": start.isoformat(),
        "end": end.isoformat(),
        "point_count": len(points),
        "three_subtheme_point_count": sum(point["indicator_count"] == 3 for point in points),
        "state_flip_count": sum(
            left["state"] != right["state"] for left, right in zip(points, points[1:])
        ),
        "turning_point_count": sum(a * b < 0 for a, b in zip(changes, changes[1:])),
        "monthly_change_std": monthly_std,
        "mean_leave_one_out_delta": round(statistics.mean(sensitivities), 2)
        if sensitivities
        else None,
        "max_leave_one_out_delta": max_sensitivity,
        "model_readiness": "fail" if reasons else "pass",
        "model_readiness_reasons": reasons,
        "claim_status": "diagnostic_only",
        "warning": "V0.3 separates goods, services and producer prices; predictive accuracy remains untested.",
        "points": points,
    }


def rolling_cn_inflation_backtest_v4(
    session: Session, start: date, end: date, settings: Settings
) -> dict:
    raw_points = []
    cursor = date(start.year, start.month, 1)
    while cursor <= end:
        cutoff = cutoff_for_month(cursor.year, cursor.month, settings)
        signals: dict[str, float] = {}
        source_dates: dict[str, str] = {}
        for indicator_id in CN_INFLATION_V4_IDS:
            indicator = session.get(IndicatorDefinition, indicator_id)
            if indicator is None:
                continue
            eligible = [
                row
                for row in build_indicator_features(session, indicator, cutoff)
                if row.robust_z is not None
            ]
            if not eligible:
                continue
            latest = eligible[-1]
            value = (latest.robust_z or 0) * 25 * latest.freshness_weight
            signals[indicator_id] = max(-100, min(100, value))
            source_dates[indicator_id] = latest.source_observation_date.isoformat()
        if signals:
            raw_points.append(
                {
                    "cutoff": cutoff.isoformat(),
                    "raw_score": sum(signals.values()) / len(signals),
                    "indicator_count": len(signals),
                    "signals": {key: round(value, 2) for key, value in signals.items()},
                    "source_observation_dates": source_dates,
                }
            )
        cursor = _next_month(cursor)
    points = []
    confirmed_state: str | None = None
    previous_candidate: str | None = None
    for index, raw_point in enumerate(raw_points):
        window = raw_points[max(0, index - 2) : index + 1]
        score = sum(item["raw_score"] for item in window) / len(window)
        smoothed_loo = []
        for removed in CN_INFLATION_V4_IDS:
            alternatives = []
            for item in window:
                remaining = [v for k, v in item["signals"].items() if k != removed]
                if remaining:
                    alternatives.append(sum(remaining) / len(remaining))
            if alternatives:
                smoothed_loo.append(abs(score - sum(alternatives) / len(alternatives)))
        candidate = _state(score)
        if confirmed_state is None:
            confirmed_state = candidate
        elif candidate != confirmed_state and candidate == previous_candidate:
            confirmed_state = candidate
        point = dict(raw_point)
        point.update(
            raw_score=round(raw_point["raw_score"], 2),
            score=round(score, 2),
            candidate_state=candidate,
            state=confirmed_state,
            max_leave_one_out_delta=round(max(smoothed_loo), 2) if smoothed_loo else None,
        )
        points.append(point)
        previous_candidate = candidate
    report = _summarize_v3(points, start, end)
    report.update(
        backtest_id="cn-inflation-strict-vintage-v0.4",
        four_subtheme_point_count=sum(p["indicator_count"] == 4 for p in points),
        warning=(
            "V0.4 adds the independent PBC household price-expectation subtheme; "
            "predictive accuracy remains untested."
        ),
    )
    report.pop("three_subtheme_point_count", None)
    if report["four_subtheme_point_count"] < 24:
        report["model_readiness"] = "fail"
        report["model_readiness_reasons"].append(
            "fewer than 24 monthly cutoffs have all four subthemes"
        )
    return report


def _next_month(value: date) -> date:
    if value.month == 12:
        return date(value.year + 1, 1, 1)
    return date(value.year, value.month + 1, 1)


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
