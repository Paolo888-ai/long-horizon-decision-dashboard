from fastapi.testclient import TestClient

from app.cross_country_similarity import _credit_comparability
from app.main import app
from app.policy_events import build_policy_evidence

client = TestClient(app)


def test_credit_comparability_uses_latest_common_year_and_five_year_change() -> None:
    from datetime import date

    result = _credit_comparability(
        {date(2018, 12, 31): 150.0, date(2023, 12, 31): 160.0},
        {
            date(2018, 12, 31): 155.0,
            date(2023, 12, 31): 165.0,
            date(2024, 12, 31): 170.0,
        },
    )
    assert result["latest_common_year"] == 2023
    assert result["comparison_start_year"] == 2018
    assert result["score"] == 97.5


def test_policy_evidence_stays_locked_until_two_distinct_reviewers_approve() -> None:
    evidence = build_policy_evidence()
    assert len(evidence["events"]) == 6
    assert evidence["score_allowed"] is False
    assert evidence["scoring_gate"]["approved_cn"] == 0
    assert evidence["scoring_gate"]["approved_jp"] == 0
    assert {event["review_status"] for event in evidence["events"]} == {
        "awaiting_second_review"
    }


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_snapshot_supports_four_geographies() -> None:
    for geography in ("CN", "US", "JP", "GLOBAL"):
        response = client.get("/v1/snapshots/latest", params={"geography": geography})
        assert response.status_code == 200
        assert response.json()["geography"] == geography
        assert response.json()["isSample"] is True


def test_snapshot_rejects_unknown_geography() -> None:
    response = client.get("/v1/snapshots/latest", params={"geography": "EU"})
    assert response.status_code == 404


def test_probabilities_sum_to_one_hundred() -> None:
    payload = client.get("/v1/snapshots/latest?geography=JP").json()
    assert sum(item["oneYear"] for item in payload["scenarios"]) == 100
    assert sum(item["threeYear"] for item in payload["scenarios"]) == 100
    assert sum(item["longTerm"] for item in payload["scenarios"]) == 100


def test_data_quality_endpoint() -> None:
    with TestClient(app) as lifespan_client:
        response = lifespan_client.get("/v1/data-quality")
        assert response.status_code == 200
        assert response.json()["indicator_count"] == 35


def test_indicator_catalog_and_unknown_latest() -> None:
    with TestClient(app) as lifespan_client:
        catalog = lifespan_client.get("/v1/indicators", params={"geography": "JP"})
        assert catalog.status_code == 200
        assert len(catalog.json()) == 11
        missing = lifespan_client.get("/v1/indicators/not-real/latest")
        assert missing.status_code == 404
        detail = lifespan_client.get("/v1/indicators/TREASURY_US_10Y2Y")
        assert detail.status_code == 200
        assert detail.json()["source_provider"] == "U.S. Department of the Treasury"
        assert detail.json()["history"] == []


def test_experimental_environment_stays_closed_without_history() -> None:
    with TestClient(app) as lifespan_client:
        response = lifespan_client.get("/v1/experimental/environment?geography=CN")
        assert response.status_code == 409


def test_cn_jp_similarity_endpoint_requires_aware_cutoff() -> None:
    with TestClient(app) as lifespan_client:
        invalid = lifespan_client.get(
            "/v1/research/cn-jp-inflation-similarity", params={"cutoff": "2026-08-15"}
        )
        assert invalid.status_code == 422
        response = lifespan_client.get("/v1/research/cn-jp-inflation-similarity")
        assert response.status_code == 200
        assert response.json()["claim_status"] == "retrospective_diagnostic_only"
