import html
import re
from calendar import monthrange
from datetime import UTC, date, datetime
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

import httpx
from pypdf import PdfReader

from .base import ConnectorError, FetchResult, Observation, request_with_retry

ROW_PATTERN = re.compile(r"(?m)^(20\d{2})\s*\.\s*Q([1-4])\s+(-?\d+(?:\.\d+)?)")


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href is not None:
            self.links.append((self._href, "".join(self._text).strip()))
            self._href = None


def discover_depositor_report_pages(content: bytes, base_url: str) -> list[str]:
    parser = _LinkParser()
    parser.feed(content.decode("utf-8", errors="replace"))
    urls = []
    for href, title in parser.links:
        if not re.search(r"20\d{2}年(?:第)?[一二三四1-4]季度城镇储户问卷调查报告", title):
            continue
        url = urljoin(base_url, href)
        if urlparse(url).hostname == "www.pbc.gov.cn" and url.endswith("index.html"):
            urls.append(url)
    return list(dict.fromkeys(urls))


def parse_price_expectation_text(text: str, released_at: datetime) -> tuple[Observation, ...]:
    if released_at.tzinfo is None:
        raise ValueError("PBC release time must be timezone-aware")
    rows = []
    for year_text, quarter_text, value_text in ROW_PATTERN.findall(text):
        year, quarter = int(year_text), int(quarter_text)
        month = quarter * 3
        rows.append(
            Observation(
                observation_date=date(year, month, monthrange(year, month)[1]),
                value=float(value_text),
                available_at=released_at,
            )
        )
    if not rows:
        raise ConnectorError("No PBC price-expectation table rows found")
    return tuple(rows)


class PbcDepositorSurveyConnector:
    source_id = "pbc_cn"

    def __init__(self, client: httpx.Client | None = None) -> None:
        self.client = client or httpx.Client(
            timeout=30,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 LongHorizonDashboard/0.1"},
        )

    def fetch(self, path: Path, source_url: str, released_at: datetime) -> FetchResult:
        content = path.read_bytes()
        reader = PdfReader(BytesIO(content))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        observations = parse_price_expectation_text(text, released_at)
        return FetchResult(
            source_id=self.source_id,
            request_url=source_url,
            media_type="application/pdf",
            retrieved_at=datetime.now(UTC),
            raw_content=content,
            observations=observations,
        )

    def fetch_report_page(self, page_url: str) -> FetchResult:
        if not page_url.startswith("https://www.pbc.gov.cn/"):
            raise ConnectorError("PBC report page must use the official www.pbc.gov.cn host")
        page = request_with_retry(self.client, "GET", page_url)
        if page.status_code != 200:
            raise ConnectorError(f"PBC report page returned HTTP {page.status_code}")
        decoded = page.content.decode("utf-8", errors="replace")
        visible_text = html.unescape(re.sub(r"<[^>]+>", " ", decoded))
        visible_text = re.sub(r"\s+", " ", visible_text)
        release_match = re.search(
            r"文章来源：\s*(20\d{2})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2}):(\d{2})",
            visible_text,
        )
        if release_match is None:
            raise ConnectorError("PBC report page contained no exact publication timestamp")
        released_at = datetime(
            *(int(value) for value in release_match.groups()),
            tzinfo=ZoneInfo("Asia/Shanghai"),
        )
        parser = _LinkParser()
        parser.feed(decoded)
        pdf_urls = [
            urljoin(page_url, href)
            for href, title in parser.links
            if href.lower().endswith(".pdf") and "城镇储户问卷调查报告" in title
        ]
        if not pdf_urls:
            raise ConnectorError("PBC report page contained no depositor survey PDF")
        pdf_url = pdf_urls[0]
        pdf = request_with_retry(self.client, "GET", pdf_url)
        if pdf.status_code != 200:
            raise ConnectorError(f"PBC PDF returned HTTP {pdf.status_code}")
        reader = PdfReader(BytesIO(pdf.content))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        return FetchResult(
            source_id=self.source_id,
            request_url=pdf_url,
            media_type="application/pdf",
            retrieved_at=datetime.now(UTC),
            raw_content=pdf.content,
            observations=parse_price_expectation_text(text, released_at),
        )
