from typing import Literal

from pydantic import BaseModel, Field

Geography = Literal["CN", "US", "JP", "GLOBAL"]
Confidence = Literal["低", "中", "高"]


class DimensionState(BaseModel):
    id: str
    label: str
    score: int = Field(ge=-100, le=100)
    state: str
    direction: Literal["up", "down", "flat"]
    confidence: Confidence


class CycleState(BaseModel):
    label: str
    state: str
    trend: str


class Scenario(BaseModel):
    label: str
    one_year: int = Field(ge=0, le=100, serialization_alias="oneYear")
    three_year: int = Field(ge=0, le=100, serialization_alias="threeYear")
    long_term: int = Field(ge=0, le=100, serialization_alias="longTerm")


class Analog(BaseModel):
    country: str
    period: str
    data_similarity: int = Field(ge=0, le=100, serialization_alias="dataSimilarity")
    structural_comparability: int = Field(
        ge=0, le=100, serialization_alias="structuralComparability"
    )
    confidence: Confidence


class Snapshot(BaseModel):
    geography: Geography
    geography_label: str = Field(serialization_alias="geographyLabel")
    as_of: str = Field(serialization_alias="asOf")
    data_completeness: int = Field(ge=0, le=100, serialization_alias="dataCompleteness")
    confidence: Confidence
    summary: str
    caveat: str
    dimensions: list[DimensionState]
    cycles: list[CycleState]
    scenarios: list[Scenario]
    analogs: list[Analog]
    changes: list[str]
    forks: list[str]
    model_version: str = Field(serialization_alias="modelVersion")
    is_sample: bool = Field(serialization_alias="isSample")


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    model_version: str


class PublicationPolicyResponse(BaseModel):
    timezone: str
    cutoff_day: int
    cutoff_time: str
    publication_day: int
    rule: str


class DataQualityResponse(BaseModel):
    generated_at: str
    indicator_count: int
    active_indicator_count: int
    geography_indicator_counts: dict[str, int]
    indicators_with_observations: int
    coverage_percent: float
    observation_vintage_count: int
    raw_asset_count: int
    feature_row_count: int
    indicators_with_features: int
    missing_indicator_ids: list[str]
    high_frequency_coverage: dict[str, dict[str, float | int]]
    high_frequency_history_months: dict[str, int]
    mature_high_frequency_indicators: dict[str, int]
    experimental_scoring_ready: bool
    readiness_reasons: list[str]
    status: Literal["pass", "incomplete"]


class IndicatorSummary(BaseModel):
    id: str
    name_zh: str
    name_en: str | None
    geography: Geography
    dimension: str
    frequency: str
    unit: str | None
    source_id: str
    external_code: str
    quality_grade: str


class LatestObservationResponse(BaseModel):
    indicator: IndicatorSummary
    observation_date: str
    vintage_at: str
    value: float | None
    status: str
    raw_asset_hash: str | None


class IndicatorHistoryPoint(BaseModel):
    month: str
    source_observation_date: str
    level: float | None
    robust_z: float | None
    momentum_3m: float | None
    change_12m: float | None
    change_12m_percent: float | None
    data_age_days: int
    freshness_weight: float
    is_carried_forward: bool


class IndicatorDetailResponse(BaseModel):
    indicator: IndicatorSummary
    source_provider: str
    source_dataset: str
    source_url: str
    attribution_text: str | None
    latest_vintage_at: str | None
    feature_cutoff: str | None
    history: list[IndicatorHistoryPoint]


class ExperimentalDimension(BaseModel):
    dimension: str
    score: float
    state: str
    direction: str
    confidence: str
    coverage: float
    indicator_ids: list[str]


class ExperimentalEnvironmentResponse(BaseModel):
    geography: Geography
    cutoff: str
    model_version: str
    is_experimental: bool
    decision_use: Literal["research_only"]
    warning: str
    dimensions: list[ExperimentalDimension]
    missing_dimensions: list[str]
