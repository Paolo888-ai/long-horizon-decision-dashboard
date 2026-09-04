from contextlib import asynccontextmanager
from datetime import date, datetime

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from .backtest import (
    rolling_cn_inflation_backtest,
    rolling_cn_inflation_backtest_v2,
    rolling_cn_inflation_backtest_v3,
    rolling_cn_inflation_backtest_v4,
)
from .config import get_settings
from .cross_country_similarity import build_cn_jp_inflation_similarity
from .database import SessionLocal, create_schema
from .direction_backtest import rolling_cn_cpi_direction_backtest
from .experimental import build_experimental_environment
from .forecast import rolling_cn_cpi_forecast_backtest
from .historical_similarity import backtest_cn_inflation_similarity
from .models import FeatureMonthly, IndicatorDefinition, ObservationVintage, SourceRegistry
from .quality import build_quality_report
from .sample_data import SUMMARIES, get_sample_snapshot
from .schemas import (
    DataQualityResponse,
    ExperimentalEnvironmentResponse,
    HealthResponse,
    IndicatorDetailResponse,
    IndicatorHistoryPoint,
    IndicatorSummary,
    LatestObservationResponse,
    PublicationPolicyResponse,
    Snapshot,
)
from .seeds import seed_registry
from .similarity_cards import build_cn_similarity_evidence_card

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    create_schema()
    with SessionLocal() as session:
        seed_registry(session)
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service=settings.app_name, model_version="sample-v0.1")


@app.get("/v1/snapshots/latest", response_model=Snapshot, response_model_by_alias=True)
def latest_snapshot(geography: str = Query(default="CN")) -> Snapshot:
    normalized = geography.upper()
    if normalized not in SUMMARIES:
        raise HTTPException(status_code=404, detail="Unsupported geography")
    return get_sample_snapshot(normalized)


@app.get("/v1/publication-policy", response_model=PublicationPolicyResponse)
def publication_policy() -> PublicationPolicyResponse:
    return PublicationPolicyResponse(
        timezone=settings.publication_timezone,
        cutoff_day=settings.publication_cutoff_day,
        cutoff_time=settings.publication_cutoff_time,
        publication_day=settings.publication_day,
        rule="Only data publicly released by the cutoff can enter that month's immutable snapshot.",
    )


@app.get("/v1/data-quality", response_model=DataQualityResponse)
def data_quality() -> DataQualityResponse:
    with SessionLocal() as session:
        return DataQualityResponse(**build_quality_report(session))


@app.get("/v1/experimental/environment", response_model=ExperimentalEnvironmentResponse)
def experimental_environment(
    geography: str = Query(default="CN"),
) -> ExperimentalEnvironmentResponse:
    normalized = geography.upper()
    if normalized not in {"CN", "US", "JP", "GLOBAL"}:
        raise HTTPException(status_code=404, detail="Unsupported geography")
    with SessionLocal() as session:
        payload = build_experimental_environment(session, normalized)
    if payload is None:
        raise HTTPException(status_code=409, detail="Experimental scoring readiness gate is closed")
    return ExperimentalEnvironmentResponse(**payload)


@app.get("/v1/backtests/cn-inflation")
def cn_inflation_backtest(
    start: str = Query(default="2024-03", pattern=r"^\d{4}-\d{2}$"),
    end: str = Query(default="2026-08", pattern=r"^\d{4}-\d{2}$"),
) -> dict:
    start_date = date.fromisoformat(f"{start}-01")
    end_date = date.fromisoformat(f"{end}-01")
    if start_date > end_date:
        raise HTTPException(status_code=422, detail="start must not be after end")
    with SessionLocal() as session:
        return rolling_cn_inflation_backtest(session, start_date, end_date, settings)


@app.get("/v1/backtests/cn-inflation-v2")
def cn_inflation_backtest_v2(
    start: str = Query(default="2024-03", pattern=r"^\d{4}-\d{2}$"),
    end: str = Query(default="2026-08", pattern=r"^\d{4}-\d{2}$"),
) -> dict:
    start_date = date.fromisoformat(f"{start}-01")
    end_date = date.fromisoformat(f"{end}-01")
    if start_date > end_date:
        raise HTTPException(status_code=422, detail="start must not be after end")
    with SessionLocal() as session:
        return rolling_cn_inflation_backtest_v2(session, start_date, end_date, settings)


@app.get("/v1/backtests/cn-inflation-v3")
def cn_inflation_backtest_v3(
    start: str = Query(default="2024-03", pattern=r"^\d{4}-\d{2}$"),
    end: str = Query(default="2026-08", pattern=r"^\d{4}-\d{2}$"),
) -> dict:
    start_date = date.fromisoformat(f"{start}-01")
    end_date = date.fromisoformat(f"{end}-01")
    if start_date > end_date:
        raise HTTPException(status_code=422, detail="start must not be after end")
    with SessionLocal() as session:
        return rolling_cn_inflation_backtest_v3(session, start_date, end_date, settings)


@app.get("/v1/backtests/cn-inflation-v4")
def cn_inflation_backtest_v4(
    start: str = Query(default="2024-03", pattern=r"^\d{4}-\d{2}$"),
    end: str = Query(default="2026-08", pattern=r"^\d{4}-\d{2}$"),
) -> dict:
    start_date = date.fromisoformat(f"{start}-01")
    end_date = date.fromisoformat(f"{end}-01")
    if start_date > end_date:
        raise HTTPException(status_code=422, detail="start must not be after end")
    with SessionLocal() as session:
        return rolling_cn_inflation_backtest_v4(session, start_date, end_date, settings)


@app.get("/v1/backtests/cn-cpi-forecast")
def cn_cpi_forecast_backtest(
    start: str = Query(default="2024-03", pattern=r"^\d{4}-\d{2}$"),
    end: str = Query(default="2026-08", pattern=r"^\d{4}-\d{2}$"),
    horizon: int = Query(default=6, ge=6, le=12),
) -> dict:
    if horizon not in {6, 12}:
        raise HTTPException(status_code=422, detail="horizon must be 6 or 12")
    start_date = date.fromisoformat(f"{start}-01")
    end_date = date.fromisoformat(f"{end}-01")
    if start_date > end_date:
        raise HTTPException(status_code=422, detail="start must not be after end")
    with SessionLocal() as session:
        return rolling_cn_cpi_forecast_backtest(session, start_date, end_date, settings, horizon)


@app.get("/v1/backtests/cn-cpi-direction")
def cn_cpi_direction_backtest(
    start: str = Query(default="2022-11", pattern=r"^\d{4}-\d{2}$"),
    end: str = Query(default="2026-08", pattern=r"^\d{4}-\d{2}$"),
) -> dict:
    start_date = date.fromisoformat(f"{start}-01")
    end_date = date.fromisoformat(f"{end}-01")
    if start_date > end_date:
        raise HTTPException(status_code=422, detail="start must not be after end")
    with SessionLocal() as session:
        return rolling_cn_cpi_direction_backtest(session, start_date, end_date, settings)


@app.get("/v1/backtests/cn-similarity")
def cn_similarity_backtest(
    start: str = Query(default="2021-09", pattern=r"^\d{4}-\d{2}$"),
    end: str = Query(default="2026-08", pattern=r"^\d{4}-\d{2}$"),
) -> dict:
    start_date = date.fromisoformat(f"{start}-01")
    end_date = date.fromisoformat(f"{end}-01")
    if start_date > end_date:
        raise HTTPException(status_code=422, detail="start must not be after end")
    with SessionLocal() as session:
        return backtest_cn_inflation_similarity(session, start_date, end_date, settings)


@app.get("/v1/backtests/cn-similarity/evidence-card")
def cn_similarity_evidence_card(
    cutoff: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
) -> dict:
    with SessionLocal() as session:
        return build_cn_similarity_evidence_card(
            session, date(2021, 9, 1), date(2026, 8, 1), settings, cutoff
        )


@app.get("/v1/research/cn-jp-inflation-similarity")
def cn_jp_inflation_similarity(
    cutoff: str = Query(default="2026-08-15T23:59:00+08:00"),
) -> dict:
    try:
        parsed = datetime.fromisoformat(cutoff)
    except ValueError as error:
        raise HTTPException(status_code=422, detail="cutoff must be ISO 8601") from error
    if parsed.tzinfo is None:
        raise HTTPException(status_code=422, detail="cutoff must include a timezone offset")
    with SessionLocal() as session:
        return build_cn_jp_inflation_similarity(session, parsed)


def indicator_summary(indicator: IndicatorDefinition) -> IndicatorSummary:
    return IndicatorSummary(
        id=indicator.id,
        name_zh=indicator.name_zh,
        name_en=indicator.name_en,
        geography=indicator.geography,
        dimension=indicator.dimension,
        frequency=indicator.frequency,
        unit=indicator.unit,
        source_id=indicator.source_id,
        external_code=indicator.external_code,
        quality_grade=indicator.quality_grade,
    )


@app.get("/v1/indicators", response_model=list[IndicatorSummary])
def indicators(geography: str | None = Query(default=None)) -> list[IndicatorSummary]:
    with SessionLocal() as session:
        statement = select(IndicatorDefinition).where(IndicatorDefinition.active.is_(True))
        if geography:
            statement = statement.where(IndicatorDefinition.geography == geography.upper())
        rows = session.scalars(statement.order_by(IndicatorDefinition.id)).all()
        return [indicator_summary(row) for row in rows]


@app.get("/v1/indicators/{indicator_id}/latest", response_model=LatestObservationResponse)
def latest_observation(indicator_id: str) -> LatestObservationResponse:
    with SessionLocal() as session:
        indicator = session.get(IndicatorDefinition, indicator_id)
        if indicator is None:
            raise HTTPException(status_code=404, detail="Unknown indicator")
        observation = session.scalars(
            select(ObservationVintage)
            .where(ObservationVintage.indicator_id == indicator_id)
            .order_by(
                ObservationVintage.observation_date.desc(),
                ObservationVintage.vintage_at.desc(),
            )
            .limit(1)
        ).first()
        if observation is None:
            raise HTTPException(status_code=404, detail="Indicator has no observations")
        return LatestObservationResponse(
            indicator=indicator_summary(indicator),
            observation_date=observation.observation_date.isoformat(),
            vintage_at=observation.vintage_at.isoformat(),
            value=observation.value,
            status=observation.status,
            raw_asset_hash=observation.raw_asset_hash,
        )


@app.get("/v1/indicators/{indicator_id}", response_model=IndicatorDetailResponse)
def indicator_detail(indicator_id: str) -> IndicatorDetailResponse:
    with SessionLocal() as session:
        indicator = session.get(IndicatorDefinition, indicator_id)
        if indicator is None:
            raise HTTPException(status_code=404, detail="Unknown indicator")
        source = session.get(SourceRegistry, indicator.source_id)
        latest_vintage = session.scalars(
            select(ObservationVintage)
            .where(ObservationVintage.indicator_id == indicator_id)
            .order_by(ObservationVintage.vintage_at.desc())
            .limit(1)
        ).first()
        latest_feature = session.scalars(
            select(FeatureMonthly)
            .where(FeatureMonthly.indicator_id == indicator_id)
            .order_by(FeatureMonthly.vintage_cutoff.desc(), FeatureMonthly.month.desc())
            .limit(1)
        ).first()
        feature_rows: list[FeatureMonthly] = []
        if latest_feature is not None:
            feature_rows = list(
                session.scalars(
                    select(FeatureMonthly)
                    .where(
                        FeatureMonthly.indicator_id == indicator_id,
                        FeatureMonthly.vintage_cutoff == latest_feature.vintage_cutoff,
                    )
                    .order_by(FeatureMonthly.month.desc())
                    .limit(120)
                ).all()
            )
            feature_rows.reverse()
        return IndicatorDetailResponse(
            indicator=indicator_summary(indicator),
            source_provider=source.provider if source else indicator.source_id,
            source_dataset=source.dataset if source else "",
            source_url=source.official_url if source else "",
            attribution_text=source.attribution_text if source else None,
            latest_vintage_at=(latest_vintage.vintage_at.isoformat() if latest_vintage else None),
            feature_cutoff=(latest_feature.vintage_cutoff.isoformat() if latest_feature else None),
            history=[
                indicator_history_point(row, feature_rows, index)
                for index, row in enumerate(feature_rows)
            ],
        )


def indicator_history_point(
    row: FeatureMonthly, rows: list[FeatureMonthly], index: int
) -> IndicatorHistoryPoint:
    previous = rows[index - 12].level if index >= 12 else None
    percent = None
    if row.level is not None and previous not in (None, 0):
        percent = (row.level / previous - 1) * 100
    return IndicatorHistoryPoint(
        month=row.month.isoformat(),
        source_observation_date=row.source_observation_date.isoformat(),
        level=row.level,
        robust_z=row.robust_z,
        momentum_3m=row.momentum_3m,
        change_12m=row.change_12m,
        change_12m_percent=percent,
        data_age_days=(row.month - row.source_observation_date).days,
        freshness_weight=row.freshness_weight,
        is_carried_forward=row.is_carried_forward,
    )
