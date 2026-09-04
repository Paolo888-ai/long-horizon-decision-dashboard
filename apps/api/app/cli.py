import argparse
import json
import math
from datetime import UTC, date, datetime
from pathlib import Path

import httpx
from sqlalchemy import delete, select

from .backtest import (
    rolling_cn_inflation_backtest,
    rolling_cn_inflation_backtest_v2,
    rolling_cn_inflation_backtest_v3,
    rolling_cn_inflation_backtest_v4,
)
from .config import get_settings
from .connectors import (
    BlsConnector,
    BojConnector,
    CensusRetailConnector,
    ChinaOfficialCsvConnector,
    JapanCpiCsvConnector,
    NbsReleaseConnector,
    PbcDepositorSurveyConnector,
    TreasuryYieldCurveConnector,
    WorldBankConnector,
)
from .connectors.base import ConnectorError, FetchResult, request_with_retry
from .connectors.nbs_release import discover_release_urls
from .connectors.pbc_depositor import discover_depositor_report_pages
from .cross_country_similarity import build_cn_jp_inflation_similarity
from .database import SessionLocal, create_schema
from .direction_backtest import rolling_cn_cpi_direction_backtest
from .features import build_all_features
from .forecast import rolling_cn_cpi_forecast_backtest
from .historical_similarity import backtest_cn_inflation_similarity
from .ingestion import store_fetch_result
from .models import IndicatorDefinition, ObservationVintage, RawAsset
from .quality import build_quality_report
from .seeds import seed_registry
from .similarity_cards import build_cn_similarity_evidence_card


def init_db() -> None:
    create_schema()
    with SessionLocal() as session:
        seed_registry(session)
    print("Database schema and seed registry are ready.")


def ingest_world_bank(geography: str | None, indicator_id: str | None = None) -> None:
    settings = get_settings()
    create_schema()
    connector = WorldBankConnector()
    with SessionLocal() as session:
        seed_registry(session)
        statement = select(IndicatorDefinition).where(
            IndicatorDefinition.source_id == "world_bank",
            IndicatorDefinition.active.is_(True),
        )
        if geography:
            statement = statement.where(IndicatorDefinition.geography == geography.upper())
        if indicator_id:
            statement = statement.where(IndicatorDefinition.id == indicator_id)
        indicators = list(session.scalars(statement).all())
        for indicator in indicators:
            country, code = indicator.external_code.split(":", maxsplit=1)
            result = connector.fetch(country=country, indicator=code)
            store_fetch_result(session, indicator.id, result, Path(settings.raw_data_dir))
            print(f"Ingested {indicator.id}: {len(result.observations)} observations")


def ingest_china_csv(indicator_id: str, path: Path, source_url: str) -> None:
    settings = get_settings()
    connector = ChinaOfficialCsvConnector()
    with SessionLocal() as session:
        result = connector.fetch(path, source_url)
        store_fetch_result(session, indicator_id, result, Path(settings.raw_data_dir))
    print(f"Ingested {indicator_id}: {len(result.observations)} observations")


def ingest_japan_cpi(path: Path, source_url: str, released_at: str) -> None:
    release = datetime.fromisoformat(released_at)
    if release.tzinfo is None:
        raise ValueError("Japan CPI release timestamp must include timezone offset")
    settings = get_settings()
    create_schema()
    connector = JapanCpiCsvConnector()
    with SessionLocal() as session:
        seed_registry(session)
        for indicator_id, series in (
            ("ESTAT_JP_CPI_YOY", "all_items"),
            ("ESTAT_JP_GOODS_CPI_YOY", "goods"),
            ("ESTAT_JP_SERVICES_CPI_YOY", "services"),
        ):
            result = connector.fetch(path, series, source_url, release)
            store_fetch_result(session, indicator_id, result, Path(settings.raw_data_dir))
            print(f"Ingested {indicator_id}: {len(result.observations)} observations")


def ingest_pbc_depositor(path: Path, source_url: str, released_at: str) -> None:
    settings = get_settings()
    release = datetime.fromisoformat(released_at)
    if release.tzinfo is None:
        raise ValueError("PBC release timestamp must include timezone offset")
    create_schema()
    with SessionLocal() as session:
        seed_registry(session)
        result = PbcDepositorSurveyConnector().fetch(path, source_url, release)
        store_fetch_result(session, "PBC_CN_PRICE_EXPECTATION", result, Path(settings.raw_data_dir))
    print(f"Ingested PBC survey snapshot: {len(result.observations)} observations")


def backfill_pbc_depositor(start_page: int, end_page: int) -> None:
    settings = get_settings()
    create_schema()
    connector = PbcDepositorSurveyConnector()
    report_pages: list[str] = []
    with httpx.Client(
        timeout=30,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0 LongHorizonDashboard/0.1"},
    ) as client:
        for page_number in range(start_page, end_page + 1):
            suffix = "" if page_number == 1 else f"-{page_number}"
            listing_url = f"https://www.pbc.gov.cn/diaochatongjisi/116219/116227/11874{suffix}.html"
            response = request_with_retry(client, "GET", listing_url)
            if response.status_code != 200:
                print(f"Skipped PBC listing {page_number}: HTTP {response.status_code}")
                continue
            found = discover_depositor_report_pages(response.content, listing_url)
            report_pages.extend(found)
            print(f"PBC listing {page_number}: found {len(found)} depositor reports")
    with SessionLocal() as session:
        seed_registry(session)
        for page_url in dict.fromkeys(report_pages):
            try:
                result = connector.fetch_report_page(page_url)
                store_fetch_result(
                    session,
                    "PBC_CN_PRICE_EXPECTATION",
                    result,
                    Path(settings.raw_data_dir),
                )
                latest = max(result.observations, key=lambda row: row.observation_date)
                print(f"Ingested PBC {latest.observation_date}: {latest.value}")
            except ConnectorError as error:
                print(f"Skipped PBC report {page_url}: {error}")


def ingest_nbs_release(indicator_id: str, urls: list[str]) -> None:
    settings = get_settings()
    create_schema()
    connector = NbsReleaseConnector()
    with SessionLocal() as session:
        seed_registry(session)
        indicator = session.get(IndicatorDefinition, indicator_id)
        if indicator is None or indicator.source_id != "nbs_cn":
            raise ValueError("Indicator must be a registered NBS China indicator")
        for url in urls:
            result = connector.fetch(indicator_id, url)
            store_fetch_result(session, indicator_id, result, Path(settings.raw_data_dir))
            item = result.observations[0]
            print(f"Ingested {indicator_id} {item.observation_date}: {item.value}")


def backfill_nbs(indicator_id: str, start_page: int, end_page: int) -> None:
    urls: list[str] = []
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        for page in range(start_page, end_page + 1):
            suffix = "" if page == 0 else f"index_{page}.html"
            page_url = f"https://www.stats.gov.cn/sj/zxfb/{suffix}"
            response = request_with_retry(client, "GET", page_url)
            if response.status_code != 200:
                print(f"Skipped listing {page}: HTTP {response.status_code}")
                continue
            discovered = discover_release_urls(response.content, page_url, indicator_id)
            urls.extend(discovered)
            print(f"Listing {page}: found {len(discovered)} releases")
    unique_urls = list(dict.fromkeys(urls))
    if not unique_urls:
        raise ValueError("No releases discovered in requested listing pages")
    failures = 0
    for url in unique_urls:
        try:
            ingest_nbs_release(indicator_id, [url])
        except ConnectorError as error:
            failures += 1
            print(f"Skipped incompatible release {url}: {error}")
    print(f"NBS backfill finished: {len(unique_urls) - failures} ingested, {failures} skipped")


def derive_nbs_cpi_components() -> None:
    settings = get_settings()
    connector = NbsReleaseConnector()
    component_ids = (
        "NBS_CN_CORE_CPI_YOY",
        "NBS_CN_GOODS_CPI_YOY",
        "NBS_CN_SERVICES_CPI_YOY",
    )
    with SessionLocal() as session:
        seed_registry(session)
        session.execute(
            delete(ObservationVintage).where(ObservationVintage.indicator_id.in_(component_ids))
        )
        session.commit()
        assets = session.scalars(
            select(RawAsset)
            .join(
                ObservationVintage,
                ObservationVintage.raw_asset_hash == RawAsset.content_hash,
            )
            .where(
                ObservationVintage.indicator_id == "NBS_CN_CPI_YOY",
                RawAsset.media_type.contains("html"),
            )
            .distinct()
        ).all()
        for component_id in component_ids:
            ingested = 0
            skipped = 0
            seen: set[tuple[date, datetime | None]] = set()
            for asset in assets:
                content = Path(asset.storage_path).read_bytes()
                try:
                    observation = connector.parse(component_id, content)
                except ConnectorError:
                    skipped += 1
                    continue
                key = (observation.observation_date, observation.available_at)
                if key in seen:
                    skipped += 1
                    continue
                seen.add(key)
                retrieved_at = asset.retrieved_at
                if retrieved_at.tzinfo is None:
                    retrieved_at = retrieved_at.replace(tzinfo=UTC)
                result = FetchResult(
                    source_id="nbs_cn",
                    request_url=asset.request_url,
                    media_type=asset.media_type,
                    retrieved_at=retrieved_at,
                    raw_content=content,
                    observations=(observation,),
                )
                store_fetch_result(session, component_id, result, Path(settings.raw_data_dir))
                ingested += 1
            print(f"Derived {component_id}: {ingested} ingested, {skipped} skipped")


def ingest_bls() -> None:
    settings = get_settings()
    create_schema()
    connector = BlsConnector()
    with SessionLocal() as session:
        seed_registry(session)
        indicators = session.scalars(
            select(IndicatorDefinition).where(
                IndicatorDefinition.source_id == "bls",
                IndicatorDefinition.active.is_(True),
            )
        ).all()
        for indicator in indicators:
            result = connector.fetch(indicator.external_code)
            store_fetch_result(session, indicator.id, result, Path(settings.raw_data_dir))
            print(f"Ingested {indicator.id}: {len(result.observations)} observations")


def ingest_treasury(start_year: int, end_year: int) -> None:
    settings = get_settings()
    create_schema()
    connector = TreasuryYieldCurveConnector()
    with SessionLocal() as session:
        seed_registry(session)
        for year in range(start_year, end_year + 1):
            result = connector.fetch(year)
            store_fetch_result(session, "TREASURY_US_10Y2Y", result, Path(settings.raw_data_dir))
            print(f"Ingested Treasury {year}: {len(result.observations)} observations")


def ingest_census_retail() -> None:
    settings = get_settings()
    create_schema()
    connector = CensusRetailConnector()
    with SessionLocal() as session:
        seed_registry(session)
        result = connector.fetch()
        store_fetch_result(session, "CENSUS_US_RETAIL_SALES", result, Path(settings.raw_data_dir))
    print(f"Ingested CENSUS_US_RETAIL_SALES: {len(result.observations)} observations")


def ingest_boj(start: str, end: str) -> None:
    settings = get_settings()
    create_schema()
    connector = BojConnector()
    with SessionLocal() as session:
        seed_registry(session)
        indicators = session.scalars(
            select(IndicatorDefinition).where(
                IndicatorDefinition.source_id == "boj",
                IndicatorDefinition.active.is_(True),
            )
        ).all()
        for indicator in indicators:
            database, code = indicator.external_code.split(":", maxsplit=1)
            series_start = boj_period_for_frequency(start, indicator.frequency)
            series_end = boj_period_for_frequency(end, indicator.frequency)
            result = connector.fetch(database, code, series_start, series_end)
            store_fetch_result(session, indicator.id, result, Path(settings.raw_data_dir))
            print(f"Ingested {indicator.id}: {len(result.observations)} observations")


def boj_period_for_frequency(period: str, frequency: str) -> str:
    if len(period) != 6 or not period.isdigit():
        raise ValueError("BOJ period must use YYYYMM")
    if frequency != "Q":
        return period
    month = int(period[4:])
    if not 1 <= month <= 12:
        raise ValueError("BOJ month must be between 01 and 12")
    return f"{period[:4]}{math.ceil(month / 3):02d}"


def quality_report(output: Path | None) -> None:
    create_schema()
    with SessionLocal() as session:
        report = build_quality_report(session)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
        print(f"Quality report written to {output}")
    else:
        print(rendered)


def build_features(cutoff: str) -> None:
    parsed = datetime.fromisoformat(cutoff)
    if parsed.tzinfo is None:
        raise ValueError("Feature cutoff must include a timezone offset")
    create_schema()
    with SessionLocal() as session:
        report = build_all_features(session, parsed)
    print(json.dumps(report, ensure_ascii=False, indent=2))


def backtest_cn_inflation(start: str, end: str, output: Path | None) -> None:
    settings = get_settings()
    start_date = date.fromisoformat(f"{start}-01")
    end_date = date.fromisoformat(f"{end}-01")
    with SessionLocal() as session:
        report = rolling_cn_inflation_backtest(session, start_date, end_date, settings)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
        print(f"Backtest report written to {output}")
    else:
        print(rendered)


def backtest_cn_inflation_v2(start: str, end: str, output: Path | None) -> None:
    settings = get_settings()
    start_date = date.fromisoformat(f"{start}-01")
    end_date = date.fromisoformat(f"{end}-01")
    with SessionLocal() as session:
        report = rolling_cn_inflation_backtest_v2(session, start_date, end_date, settings)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
        print(f"Backtest v0.2 report written to {output}")
    else:
        print(rendered)


def backtest_cn_inflation_v3(start: str, end: str, output: Path | None) -> None:
    settings = get_settings()
    start_date = date.fromisoformat(f"{start}-01")
    end_date = date.fromisoformat(f"{end}-01")
    with SessionLocal() as session:
        report = rolling_cn_inflation_backtest_v3(session, start_date, end_date, settings)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
        print(f"Backtest v0.3 report written to {output}")
    else:
        print(rendered)


def backtest_cn_inflation_v4(start: str, end: str, output: Path | None) -> None:
    settings = get_settings()
    with SessionLocal() as session:
        report = rolling_cn_inflation_backtest_v4(
            session, date.fromisoformat(f"{start}-01"), date.fromisoformat(f"{end}-01"), settings
        )
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
        print(f"Backtest v0.4 report written to {output}")
    else:
        print(rendered)


def backtest_cn_cpi_forecast(start: str, end: str, horizon: int, output: Path | None) -> None:
    with SessionLocal() as session:
        report = rolling_cn_cpi_forecast_backtest(
            session,
            date.fromisoformat(f"{start}-01"),
            date.fromisoformat(f"{end}-01"),
            get_settings(),
            horizon,
        )
    rendered = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
        print(f"Forecast backtest written to {output}")
    else:
        print(rendered)


def backtest_cn_cpi_direction(start: str, end: str, output: Path | None) -> None:
    with SessionLocal() as session:
        report = rolling_cn_cpi_direction_backtest(
            session,
            date.fromisoformat(f"{start}-01"),
            date.fromisoformat(f"{end}-01"),
            get_settings(),
        )
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
        print(f"Direction backtest written to {output}")
    else:
        print(rendered)


def backtest_cn_similarity(start: str, end: str, output: Path | None) -> None:
    with SessionLocal() as session:
        report = backtest_cn_inflation_similarity(
            session,
            date.fromisoformat(f"{start}-01"),
            date.fromisoformat(f"{end}-01"),
            get_settings(),
        )
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
        print(f"Similarity backtest written to {output}")
    else:
        print(rendered)


def similarity_evidence_card(cutoff: str | None, output: Path | None) -> None:
    with SessionLocal() as session:
        card = build_cn_similarity_evidence_card(
            session, date(2021, 9, 1), date(2026, 8, 1), get_settings(), cutoff
        )
    rendered = json.dumps(card, ensure_ascii=False, indent=2)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
        print(f"Similarity evidence card written to {output}")
    else:
        print(rendered)


def cn_jp_similarity(cutoff: str, output: Path | None) -> None:
    parsed = datetime.fromisoformat(cutoff)
    if parsed.tzinfo is None:
        raise ValueError("Cross-country cutoff must include timezone offset")
    with SessionLocal() as session:
        report = build_cn_jp_inflation_similarity(session, parsed)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
        print(f"China-Japan similarity report written to {output}")
    else:
        print(rendered)


def parser() -> argparse.ArgumentParser:
    command_parser = argparse.ArgumentParser(description="Dashboard data pipeline")
    subparsers = command_parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init-db")
    world_bank = subparsers.add_parser("ingest-world-bank")
    world_bank.add_argument("--geography", choices=["CN", "US", "JP", "GLOBAL"])
    world_bank.add_argument("--indicator-id")
    subparsers.add_parser("ingest-bls")
    treasury = subparsers.add_parser("ingest-treasury")
    treasury.add_argument("--start-year", type=int, default=1990)
    treasury.add_argument("--end-year", type=int, default=datetime.now().year)
    subparsers.add_parser("ingest-census-retail")
    boj = subparsers.add_parser("ingest-boj")
    boj.add_argument("--start", default="196001")
    boj.add_argument("--end", default="210012")
    china = subparsers.add_parser("ingest-china-csv")
    china.add_argument("--indicator-id", required=True)
    china.add_argument("--path", type=Path, required=True)
    china.add_argument("--source-url", required=True)
    japan_cpi = subparsers.add_parser("ingest-japan-cpi")
    japan_cpi.add_argument("--path", type=Path, required=True)
    japan_cpi.add_argument("--source-url", required=True)
    japan_cpi.add_argument("--released-at", required=True)
    pbc = subparsers.add_parser("ingest-pbc-depositor")
    pbc.add_argument("--path", type=Path, required=True)
    pbc.add_argument("--source-url", required=True)
    pbc.add_argument("--released-at", required=True)
    pbc_backfill = subparsers.add_parser("backfill-pbc-depositor")
    pbc_backfill.add_argument("--start-page", type=int, default=2)
    pbc_backfill.add_argument("--end-page", type=int, default=4)
    nbs = subparsers.add_parser("ingest-nbs-release")
    nbs.add_argument("--indicator-id", required=True)
    nbs.add_argument("--url", action="append", required=True)
    nbs_backfill = subparsers.add_parser("backfill-nbs-cpi")
    nbs_backfill.add_argument("--start-page", type=int, default=0)
    nbs_backfill.add_argument("--end-page", type=int, default=32)
    nbs_backfill.add_argument(
        "--indicator-id",
        default="NBS_CN_CPI_YOY",
        choices=["NBS_CN_CPI_YOY", "NBS_CN_PPI_YOY", "NBS_CN_INDUSTRIAL_PRODUCTION_YOY"],
    )
    subparsers.add_parser("derive-nbs-cpi-components")
    quality = subparsers.add_parser("quality-report")
    quality.add_argument("--output", type=Path)
    features = subparsers.add_parser("build-features")
    features.add_argument("--cutoff", required=True, help="ISO datetime with timezone")
    backtest = subparsers.add_parser("backtest-cn-inflation")
    backtest.add_argument("--start", default="2024-03")
    backtest.add_argument("--end", default="2026-08")
    backtest.add_argument("--output", type=Path)
    backtest_v2 = subparsers.add_parser("backtest-cn-inflation-v2")
    backtest_v2.add_argument("--start", default="2024-03")
    backtest_v2.add_argument("--end", default="2026-08")
    backtest_v2.add_argument("--output", type=Path)
    backtest_v3 = subparsers.add_parser("backtest-cn-inflation-v3")
    backtest_v3.add_argument("--start", default="2024-03")
    backtest_v3.add_argument("--end", default="2026-08")
    backtest_v3.add_argument("--output", type=Path)
    backtest_v4 = subparsers.add_parser("backtest-cn-inflation-v4")
    backtest_v4.add_argument("--start", default="2024-03")
    backtest_v4.add_argument("--end", default="2026-08")
    backtest_v4.add_argument("--output", type=Path)
    forecast = subparsers.add_parser("backtest-cn-cpi-forecast")
    forecast.add_argument("--start", default="2024-03")
    forecast.add_argument("--end", default="2026-08")
    forecast.add_argument("--horizon", type=int, choices=[6, 12], default=6)
    forecast.add_argument("--output", type=Path)
    direction = subparsers.add_parser("backtest-cn-cpi-direction")
    direction.add_argument("--start", default="2022-11")
    direction.add_argument("--end", default="2026-08")
    direction.add_argument("--output", type=Path)
    similarity = subparsers.add_parser("backtest-cn-similarity")
    similarity.add_argument("--start", default="2021-09")
    similarity.add_argument("--end", default="2026-08")
    similarity.add_argument("--output", type=Path)
    evidence_card = subparsers.add_parser("similarity-evidence-card")
    evidence_card.add_argument("--cutoff")
    evidence_card.add_argument("--output", type=Path)
    cn_jp = subparsers.add_parser("analyze-cn-jp-similarity")
    cn_jp.add_argument("--cutoff", default="2026-08-15T23:59:00+08:00")
    cn_jp.add_argument("--output", type=Path)
    return command_parser


def main() -> None:
    args = parser().parse_args()
    if args.command == "init-db":
        init_db()
    elif args.command == "ingest-world-bank":
        ingest_world_bank(args.geography, args.indicator_id)
    elif args.command == "ingest-china-csv":
        ingest_china_csv(args.indicator_id, args.path, args.source_url)
    elif args.command == "ingest-japan-cpi":
        ingest_japan_cpi(args.path, args.source_url, args.released_at)
    elif args.command == "ingest-pbc-depositor":
        ingest_pbc_depositor(args.path, args.source_url, args.released_at)
    elif args.command == "backfill-pbc-depositor":
        backfill_pbc_depositor(args.start_page, args.end_page)
    elif args.command == "ingest-nbs-release":
        ingest_nbs_release(args.indicator_id, args.url)
    elif args.command == "backfill-nbs-cpi":
        backfill_nbs(args.indicator_id, args.start_page, args.end_page)
    elif args.command == "derive-nbs-cpi-components":
        derive_nbs_cpi_components()
    elif args.command == "ingest-bls":
        ingest_bls()
    elif args.command == "ingest-treasury":
        ingest_treasury(args.start_year, args.end_year)
    elif args.command == "ingest-census-retail":
        ingest_census_retail()
    elif args.command == "ingest-boj":
        ingest_boj(args.start, args.end)
    elif args.command == "quality-report":
        quality_report(args.output)
    elif args.command == "build-features":
        build_features(args.cutoff)
    elif args.command == "backtest-cn-inflation":
        backtest_cn_inflation(args.start, args.end, args.output)
    elif args.command == "backtest-cn-inflation-v2":
        backtest_cn_inflation_v2(args.start, args.end, args.output)
    elif args.command == "backtest-cn-inflation-v3":
        backtest_cn_inflation_v3(args.start, args.end, args.output)
    elif args.command == "backtest-cn-inflation-v4":
        backtest_cn_inflation_v4(args.start, args.end, args.output)
    elif args.command == "backtest-cn-cpi-forecast":
        backtest_cn_cpi_forecast(args.start, args.end, args.horizon, args.output)
    elif args.command == "backtest-cn-cpi-direction":
        backtest_cn_cpi_direction(args.start, args.end, args.output)
    elif args.command == "backtest-cn-similarity":
        backtest_cn_similarity(args.start, args.end, args.output)
    elif args.command == "similarity-evidence-card":
        similarity_evidence_card(args.cutoff, args.output)
    elif args.command == "analyze-cn-jp-similarity":
        cn_jp_similarity(args.cutoff, args.output)


if __name__ == "__main__":
    main()
