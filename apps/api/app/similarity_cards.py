from datetime import date

from sqlalchemy.orm import Session

from .config import Settings
from .historical_similarity import backtest_cn_inflation_similarity


def build_cn_similarity_evidence_card(
    session: Session,
    start: date,
    end: date,
    settings: Settings,
    cutoff: str | None = None,
) -> dict:
    report = backtest_cn_inflation_similarity(session, start, end, settings)
    evaluations = report["evaluations"]
    available_cutoffs = [row["cutoff"][:7] for row in evaluations]
    selected = None
    if cutoff:
        selected = next((row for row in evaluations if row["cutoff"][:7] == cutoff), None)
    elif evaluations:
        selected = evaluations[-1]
    refusal_reasons = list(report["limitations"])
    if report["readiness"] != "pass":
        refusal_reasons.extend(report["readiness_reasons"])
    if selected is None:
        return {
            "mode": "backtest_evidence_card",
            "status": "no_reliable_analogy",
            "confidence": "low",
            "requested_cutoff": cutoff,
            "available_cutoffs": available_cutoffs,
            "refusal_reasons": refusal_reasons + ["No evaluable target month was available."],
            "cards": [],
            "warning": "Current data do not support a reliable historical analogy.",
        }
    changes = [neighbor["subsequent_cpi_change"] for neighbor in selected["neighbors"]]
    cards = []
    for rank, neighbor in enumerate(selected["neighbors"], start=1):
        cards.append(
            {
                "rank": rank,
                "historical_period": neighbor["historical_cutoff"][:7],
                "scores": {
                    "total": neighbor["total_similarity"],
                    "state": neighbor["state_similarity"],
                    "trajectory": neighbor["trajectory_similarity"],
                    "structure": None,
                },
                "main_similarities": neighbor["closest_subthemes"],
                "main_differences": neighbor["largest_subtheme_gaps"],
                "subsequent_path": {
                    "six_month_average_cpi_change": neighbor["subsequent_cpi_change"]
                },
                "comparability_warning": (
                    "No cross-country or institutional structure score is available."
                ),
            }
        )
    return {
        "mode": "backtest_evidence_card",
        "status": "reference_only_high_confidence_refused",
        "confidence": "low",
        "target_cutoff": selected["cutoff"],
        "available_cutoffs": available_cutoffs,
        "current_cpi": selected["current_cpi"],
        "actual_future_average_for_backtest_only": selected["actual_future_average"],
        "path_distribution": {
            "minimum_change": min(changes),
            "median_change": sorted(changes)[len(changes) // 2],
            "maximum_change": max(changes),
            "range": selected["neighbor_outcome_range"],
        },
        "neighbor_stability": {
            "mean_consecutive_jaccard": report["mean_consecutive_neighbor_jaccard"],
            "interpretation": "moderate_or_low_stability",
        },
        "refusal_reasons": refusal_reasons,
        "cards": cards,
        "monitor_next": [
            "consumer_goods_prices",
            "services_prices",
            "producer_prices",
            "household_price_expectations",
        ],
        "warning": (
            "Similarity is a multi-path reference. It is not a forecast and does not "
            "imply that history will repeat."
        ),
    }
