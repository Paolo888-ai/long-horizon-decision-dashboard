import statistics
from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from .features import add_months, latest_vintage_series, month_end, months_between, robust_z
from .policy_events import build_policy_evidence

CN_SERIES = ("NBS_CN_GOODS_CPI_YOY", "NBS_CN_SERVICES_CPI_YOY", "NBS_CN_PPI_YOY")
JP_SERIES = ("ESTAT_JP_GOODS_CPI_YOY", "ESTAT_JP_SERVICES_CPI_YOY", "BOJ_JP_CGPI_YOY")


def build_cn_jp_inflation_similarity(session: Session, cutoff: datetime) -> dict:
    cn = [_series(session, item, cutoff) for item in CN_SERIES]
    jp = [_series(session, item, cutoff) for item in JP_SERIES]
    jp_all = _series(session, "ESTAT_JP_CPI_YOY", cutoff)
    cn_expectations = _series(session, "PBC_CN_PRICE_EXPECTATION", cutoff)
    jp_expectations = _series(session, "BOJ_JP_GENERAL_PRICE_OUTLOOK_1Y", cutoff)
    if any(not rows for rows in cn + jp) or not jp_all:
        return _empty("required China/Japan inflation history is unavailable")
    target_months = set.intersection(*(set(rows) for rows in cn))
    if not target_months:
        return _empty("China comparison series have no common month")
    target = max(target_months)
    target_vector = [_as_of_z(rows, target) for rows in cn]
    target_trajectory = [_trajectory_z(rows, target) for rows in cn]
    candidate_months = sorted(set.intersection(*(set(rows) for rows in jp)))
    candidate_months = [
        month
        for month in candidate_months
        if months_between(month, target) >= 120
        and all(add_months(month, offset) in jp_all for offset in range(1, 7))
    ]
    ranked = []
    for month in candidate_months:
        state = _similarity(target_vector, [_as_of_z(rows, month) for rows in jp])
        trajectory = _similarity(target_trajectory, [_trajectory_z(rows, month) for rows in jp])
        ranked.append((0.5 * state + 0.5 * trajectory, state, trajectory, month))
    ranked.sort(key=lambda item: (-item[0], item[3]))
    selected = []
    for item in ranked:
        if any(abs(months_between(item[3], prior[3])) < 60 for prior in selected):
            continue
        selected.append(item)
        if len(selected) == 3:
            break
    candidates = []
    for total, state, trajectory, month in selected:
        future = [jp_all[add_months(month, offset)] for offset in range(1, 7)]
        candidates.append(
            {
                "geography": "JP",
                "historical_month": month.isoformat(),
                "total_similarity": round(total, 1),
                "state_similarity": round(state, 1),
                "trajectory_similarity": round(trajectory, 1),
                "subsequent_six_month_cpi_change": round(
                    statistics.mean(future) - jp_all[month], 3
                ),
            }
        )
    policy_evidence = build_policy_evidence()
    return {
        "analysis_id": "cn-jp-inflation-retrospective-v0.4",
        "target_geography": "CN",
        "reference_geography": "JP",
        "target_month": target.isoformat(),
        "comparable_subthemes": ["goods_prices", "services_prices", "producer_prices"],
        "expectation_context": _expectation_context(cn_expectations, jp_expectations),
        "structural_comparability": _structural_comparability(
            session, cutoff, policy_evidence
        ),
        "policy_evidence": policy_evidence,
        "state_weight": 0.5,
        "trajectory_weight": 0.5,
        "minimum_calendar_distance_months": 120,
        "candidate_event_separation_months": 60,
        "claim_status": "retrospective_diagnostic_only",
        "readiness": "fail",
        "readiness_reasons": [
            (
                "e-Stat long history is a current linked/final series, "
                "not historical vintage snapshots"
            ),
            (
                "Japan enterprise expectations begin in 2014 and differ from "
                "China household expectations in respondents and units"
            ),
            (
                "World Bank credit structure is a current annual snapshot, "
                "not cutoff-aligned historical vintage data"
            ),
            "cross-country normalization has not been prospectively validated",
        ],
        "candidates": candidates,
    }


def _series(session: Session, indicator_id: str, cutoff: datetime) -> dict[date, float]:
    return {
        month_end(row.observation_date): float(row.value)
        for row in latest_vintage_series(session, indicator_id, cutoff)
        if row.value is not None
    }


def _as_of_z(rows: dict[date, float], month: date) -> float:
    values = [value for key, value in rows.items() if key <= month]
    return robust_z(values, rows[month]) if len(values) >= 5 else 0.0


def _trajectory_z(rows: dict[date, float], month: date) -> float:
    prior = add_months(month, -6)
    if prior not in rows:
        return 0.0
    changes = []
    ordered = sorted(key for key in rows if key <= month)
    for key in ordered:
        lag = add_months(key, -6)
        if lag in rows:
            changes.append(rows[key] - rows[lag])
    current = rows[month] - rows[prior]
    return robust_z(changes, current) if len(changes) >= 5 else 0.0


def _similarity(left: list[float], right: list[float]) -> float:
    gap = statistics.mean(abs(a - b) for a, b in zip(left, right, strict=True))
    return max(0.0, 100.0 - 20.0 * gap)


def _expectation_context(cn: dict[date, float], jp: dict[date, float]) -> dict:
    return {
        "included_in_analog_ranking": False,
        "reason": "insufficient pre-2016 Japan history and non-equivalent respondent populations",
        "china": _latest_context(cn, "households", "index"),
        "japan": _latest_context(jp, "enterprises", "percent_one_year_ahead"),
    }


def _latest_context(rows: dict[date, float], respondents: str, unit: str) -> dict | None:
    if not rows:
        return None
    latest = max(rows)
    return {
        "latest_month": latest.isoformat(),
        "latest_value": round(rows[latest], 3),
        "history_start": min(rows).isoformat(),
        "respondents": respondents,
        "unit": unit,
    }


def _structural_comparability(
    session: Session, cutoff: datetime, policy_evidence: dict | None = None
) -> dict:
    cn_population = _series(session, "WB_CN_LABOR_AGE_POP", cutoff)
    jp_population = _series(session, "WB_JP_LABOR_AGE_POP", cutoff)
    cn_change = _five_year_percent_change(cn_population)
    jp_change = _five_year_percent_change(jp_population)
    population_score = None
    if cn_change is not None and jp_change is not None:
        population_score = max(0.0, 100.0 - 5.0 * abs(cn_change - jp_change))
    credit = _credit_comparability(
        _current_series(session, "WB_CN_PRIVATE_CREDIT_GDP"),
        _current_series(session, "WB_JP_PRIVATE_CREDIT_GDP"),
    )
    components = [
        {
            "id": "working_age_population_trend",
            "score": None if population_score is None else round(population_score, 1),
            "china_five_year_change_percent": cn_change,
            "japan_five_year_change_percent": jp_change,
            "status": "scored" if population_score is not None else "missing",
        },
        {
            "id": "inflation_expectation_measure",
            "score": 25.0,
            "status": "scored_with_rubric",
            "reason": "household index versus enterprise one-year percentage outlook",
        },
        {"id": "credit_regime", **credit},
        {
            "id": "policy_institution_regime",
            "score": None,
            "status": "approval_gate_not_met",
            "reason": "event timeline exists; two-reviewer scoring gate has not passed",
            "event_count": len((policy_evidence or {}).get("events", [])),
        },
    ]
    scored = [row["score"] for row in components if row["score"] is not None]
    return {
        "score": round(statistics.mean(scored), 1) if scored else None,
        "coverage": f"{len(scored)}/{len(components)}",
        "confidence": "low",
        "included_in_surface_similarity": False,
        "components": components,
    }


def _credit_comparability(cn: dict[date, float], jp: dict[date, float]) -> dict:
    common_years = sorted(set(cn) & set(jp))
    if not common_years:
        return {"score": None, "status": "missing_comparable_pair"}
    latest = common_years[-1]
    prior_years = [key for key in common_years if key.year <= latest.year - 5]
    if not prior_years:
        return {"score": None, "status": "insufficient_common_history"}
    prior = prior_years[-1]
    level_gap = abs(cn[latest] - jp[latest])
    cn_change = cn[latest] - cn[prior]
    jp_change = jp[latest] - jp[prior]
    change_gap = abs(cn_change - jp_change)
    level_score = max(0.0, 100.0 - level_gap)
    change_score = max(0.0, 100.0 - 2.0 * change_gap)
    return {
        "score": round(0.5 * level_score + 0.5 * change_score, 1),
        "status": "scored",
        "latest_common_year": latest.year,
        "comparison_start_year": prior.year,
        "china_percent_gdp": round(cn[latest], 2),
        "japan_percent_gdp": round(jp[latest], 2),
        "china_five_year_change_pp": round(cn_change, 2),
        "japan_five_year_change_pp": round(jp_change, 2),
        "method": "50% level gap + 50% five-year change gap; annual retrospective data",
        "temporal_basis": "current World Bank snapshot; not cutoff-aligned vintage data",
    }


def _current_series(session: Session, indicator_id: str) -> dict[date, float]:
    return _series(session, indicator_id, datetime.max.replace(tzinfo=UTC))


def _five_year_percent_change(rows: dict[date, float]) -> float | None:
    if len(rows) < 6:
        return None
    latest = max(rows)
    candidates = sorted(key for key in rows if key.year <= latest.year - 5)
    if not candidates or rows[candidates[-1]] == 0:
        return None
    return round((rows[latest] / rows[candidates[-1]] - 1.0) * 100.0, 2)


def _empty(reason: str) -> dict:
    return {
        "analysis_id": "cn-jp-inflation-retrospective-v0.4",
        "claim_status": "retrospective_diagnostic_only",
        "readiness": "fail",
        "readiness_reasons": [reason],
        "candidates": [],
    }
