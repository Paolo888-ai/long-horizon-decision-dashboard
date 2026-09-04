import json
from datetime import datetime
from pathlib import Path

import httpx
import pytest

from app.cli import boj_period_for_frequency
from app.connectors import (
    BlsConnector,
    BojConnector,
    CensusRetailConnector,
    ChinaOfficialCsvConnector,
    ConnectorError,
    FredConnector,
    JapanCpiCsvConnector,
    NbsReleaseConnector,
    TreasuryYieldCurveConnector,
    WorldBankConnector,
)
from app.connectors.nbs_release import discover_cpi_release_urls


def mock_client(payload: object, status_code: int = 200) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=payload, request=request)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_world_bank_parses_annual_observations() -> None:
    payload = [
        {"page": 1, "pages": 1},
        [
            {"date": "2024", "value": 4.2},
            {"date": "2023", "value": None},
        ],
    ]
    result = WorldBankConnector(mock_client(payload)).fetch("CHN", "NY.GDP.MKTP.KD.ZG")
    assert len(result.observations) == 1
    assert result.observations[0].observation_date.isoformat() == "2024-12-31"
    assert result.observations[0].value == 4.2


def test_world_bank_rejects_unexpected_payload() -> None:
    with pytest.raises(ConnectorError):
        WorldBankConnector(mock_client({"error": "bad"})).fetch("CHN", "GDP")


def test_fred_parses_missing_values_and_masks_key() -> None:
    payload = {
        "observations": [
            {"date": "2024-01-01", "value": "1.5"},
            {"date": "2024-02-01", "value": "."},
        ]
    }
    result = FredConnector("secret-key", mock_client(payload)).fetch("CPIAUCSL")
    assert [item.value for item in result.observations] == [1.5, None]
    assert "secret-key" not in result.request_url


def test_boj_parses_monthly_rows() -> None:
    payload = {"data": [{"date": "202601", "value": "0.5"}]}
    result = BojConnector(mock_client(payload)).fetch("IR01", "SERIES", "202601", "202601")
    assert result.observations[0].observation_date.isoformat() == "2026-01-01"
    assert result.observations[0].value == 0.5


def test_boj_parses_official_quarterly_shape() -> None:
    payload = {
        "STATUS": 200,
        "RESULTSET": [
            {
                "FREQUENCY": "QUARTERLY",
                "VALUES": {"SURVEY_DATES": [202401, 202402], "VALUES": [11, 13]},
            }
        ],
    }
    result = BojConnector(mock_client(payload)).fetch("CO", "SERIES", "202401", "202402")
    assert [item.observation_date.isoformat() for item in result.observations] == [
        "2024-03-31",
        "2024-06-30",
    ]
    assert result.observations[0].available_at is not None
    assert result.observations[0].available_at.isoformat() == "2024-05-01T00:00:00+00:00"


def test_bls_parses_monthly_data_and_preliminary_status() -> None:
    payload = {
        "status": "REQUEST_SUCCEEDED",
        "Results": {
            "series": [
                {
                    "data": [
                        {
                            "year": "2026",
                            "period": "M07",
                            "value": "4.2",
                            "footnotes": [{"code": "P", "text": "Preliminary"}],
                        },
                        {"year": "2025", "period": "M13", "value": "4.0", "footnotes": []},
                    ]
                }
            ]
        },
    }
    result = BlsConnector(mock_client(payload)).fetch("LNS14000000")
    assert len(result.observations) == 1
    assert result.observations[0].status == "preliminary"


def test_treasury_parses_10y_2y_spread() -> None:
    payload = b"""<?xml version="1.0"?>
    <feed xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata"
          xmlns:d="http://schemas.microsoft.com/ado/2007/08/dataservices">
      <entry><content><m:properties>
        <d:NEW_DATE>2025-01-02T00:00:00</d:NEW_DATE>
        <d:BC_2YEAR>4.25</d:BC_2YEAR><d:BC_10YEAR>4.57</d:BC_10YEAR>
      </m:properties></content></entry>
    </feed>"""
    result = TreasuryYieldCurveConnector.parse(payload)
    assert result[0].observation_date.isoformat() == "2025-01-02"
    assert result[0].value == pytest.approx(0.32)


@pytest.mark.parametrize(
    ("indicator_id", "headline", "expected"),
    [
        ("NBS_CN_CPI_YOY", "2026年6月份居民消费价格同比上涨1.0%", 1.0),
        ("NBS_CN_PPI_YOY", "2026年6月份工业生产者出厂价格同比下降2.1%", -2.1),
        (
            "NBS_CN_INDUSTRIAL_PRODUCTION_YOY",
            "2026年6月份规模以上工业增加值增长5.3%",
            5.3,
        ),
    ],
)
def test_nbs_release_parses_signed_headline_value(
    indicator_id: str, headline: str, expected: float
) -> None:
    observation = NbsReleaseConnector.parse(
        indicator_id, f"<html><h1>{headline}</h1></html>".encode()
    )
    assert observation.observation_date.isoformat() == "2026-06-30"
    assert observation.value == expected


def test_nbs_release_preserves_official_availability_time() -> None:
    payload = "<h1>2025年1月份居民消费价格同比上涨0.5%</h1><p>2025/02/09 09:30</p>".encode()
    observation = NbsReleaseConnector.parse("NBS_CN_CPI_YOY", payload)
    assert observation.available_at is not None
    assert observation.available_at.isoformat() == "2025-02-09T09:30:00+08:00"


def test_nbs_release_parses_core_cpi_yoy_from_table_row() -> None:
    payload = """<h1>2025年12月份居民消费价格同比上涨0.8%</h1>
    <p>2026/01/09 09:30</p><table><tr><td>其中：不包括食品和能源</td>
    <td>0.2</td><td>1.2</td><td>0.7</td></tr></table>""".encode()
    observation = NbsReleaseConnector.parse("NBS_CN_CORE_CPI_YOY", payload)
    assert observation.value == 1.2
    assert observation.observation_date.isoformat() == "2025-12-31"


def test_nbs_release_parses_goods_and_services_rows() -> None:
    payload = """<h1>2025年12月份居民消费价格同比上涨0.8%</h1>
    <p>2026/01/09 09:30</p><table>
    <tr><td>其中：消费品</td><td>0.3</td><td>1.0</td><td>0.8</td></tr>
    <tr><td>服务</td><td>0.0</td><td>0.6</td><td>0.5</td></tr></table>""".encode()
    goods = NbsReleaseConnector.parse("NBS_CN_GOODS_CPI_YOY", payload)
    services = NbsReleaseConnector.parse("NBS_CN_SERVICES_CPI_YOY", payload)
    assert goods.value == 1.0
    assert services.value == 0.6


def test_census_retail_ignores_seasonal_factor_section() -> None:
    payload = b"""RETAIL & FOOD SERVICES\nYEAR JAN FEB\n2025 711260 711575\n\nSEASONAL FACTORS\n2025 0.911 0.891\n"""
    observations = CensusRetailConnector.parse(payload)
    assert [item.value for item in observations] == [711260.0, 711575.0]
    assert observations[-1].observation_date.isoformat() == "2025-02-28"


def test_nbs_listing_discovers_only_official_cpi_articles() -> None:
    html = b"""<a href="./202502/t1.html">2025\xe5\xb9\xb41\xe6\x9c\x88\xe4\xbb\xbd\xe5\xb1\x85\xe6\xb0\x91\xe6\xb6\x88\xe8\xb4\xb9\xe4\xbb\xb7\xe6\xa0\xbc\xe5\x90\x8c\xe6\xaf\x94\xe4\xb8\x8a\xe6\xb6\xa80.5%</a><a href="https://evil.example/a.html">2025\xe5\xb9\xb42\xe6\x9c\x88\xe4\xbb\xbd\xe5\xb1\x85\xe6\xb0\x91\xe6\xb6\x88\xe8\xb4\xb9\xe4\xbb\xb7\xe6\xa0\xbc</a>"""
    urls = discover_cpi_release_urls(html, "https://www.stats.gov.cn/sj/zxfb/index_1.html")
    assert urls == ["https://www.stats.gov.cn/sj/zxfb/202502/t1.html"]


def test_china_csv_requires_normalized_columns(tmp_path: Path) -> None:
    path = tmp_path / "official.csv"
    path.write_text("date,value\n2025-01-01,3.4\n2025-02-01,\n", encoding="utf-8")
    result = ChinaOfficialCsvConnector().fetch(path, "https://data.stats.gov.cn/")
    assert len(result.observations) == 2
    assert result.observations[1].status == "missing"
    assert json.loads(json.dumps(result.observations[0].value)) == 3.4


def test_boj_cli_converts_month_to_quarter_code() -> None:
    assert boj_period_for_frequency("202608", "Q") == "202603"
    assert boj_period_for_frequency("202608", "M") == "202608"


def test_japan_cpi_parses_english_goods_and_services_columns() -> None:
    released = datetime.fromisoformat("2026-07-24T08:30:00+09:00")
    csv_text = "\n".join(
        [
            "Japanese header,overall,goods,services",
            "Group/Item,All items,Goods,Services",
            "codes,0201,0202,0220",
            "serial,801,802,813",
            "weight,1,1,1",
            "per,1,1,1",
            "197001,,,,",
            "197101,6.5,5.7,7.4",
            "197102,6.0,5.4,6.9",
        ]
    )
    rows = JapanCpiCsvConnector.parse(csv_text.encode("cp932"), "services", released)
    assert rows[-1].observation_date.isoformat() == "1971-02-01"
    assert rows[-1].value == 6.9
    assert rows[-1].available_at == released
