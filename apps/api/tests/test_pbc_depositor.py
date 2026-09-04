from datetime import UTC, datetime

import pytest

from app.connectors.pbc_depositor import (
    discover_depositor_report_pages,
    parse_price_expectation_text,
)


def test_parse_price_expectation_rows_share_release_vintage() -> None:
    release = datetime(2025, 3, 21, 17, 14, tzinfo=UTC)
    rows = parse_price_expectation_text(
        "2024.Q3 60.9 45.7 45.2 30.2 41.3\n2024.Q4 59.8 46.0 45.1 30.0 41.5",
        release,
    )
    assert [row.value for row in rows] == [60.9, 59.8]
    assert rows[-1].observation_date.isoformat() == "2024-12-31"
    assert all(row.available_at == release for row in rows)


def test_parse_requires_timezone_aware_release() -> None:
    with pytest.raises(ValueError):
        parse_price_expectation_text("2024.Q4 59.8", datetime(2025, 3, 21))


def test_discover_depositor_report_pages_filters_other_surveys() -> None:
    html = (
        '<a href="abc/index.html">2022年第一季度城镇储户问卷调查报告</a>'
        '<a href="bank/index.html">2022年第一季度银行家问卷调查报告</a>'
    ).encode()
    assert discover_depositor_report_pages(
        html, "https://www.pbc.gov.cn/diaochatongjisi/list.html"
    ) == ["https://www.pbc.gov.cn/diaochatongjisi/abc/index.html"]
