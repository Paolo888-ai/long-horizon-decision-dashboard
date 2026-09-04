import html
import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
from calendar import monthrange
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import httpx

from .base import ConnectorError, FetchResult, Observation, request_with_retry


PATTERNS = {
    "NBS_CN_CPI_YOY": re.compile(
        r"(?P<year>20\d{2})年(?P<month>\d{1,2})月份居民消费价格同比"
        r"(?P<direction>上涨|下降|持平)(?P<value>\d+(?:\.\d+)?)?%?"
    ),
    "NBS_CN_PPI_YOY": re.compile(
        r"(?P<year>20\d{2})年(?P<month>\d{1,2})月份.*?工业生产者出厂价格同比"
        r"(?P<direction>上涨|下降|持平)(?P<value>\d+(?:\.\d+)?)?%?"
    ),
    "NBS_CN_INDUSTRIAL_PRODUCTION_YOY": re.compile(
        r"(?P<year>20\d{2})年(?P<month>\d{1,2})月份规模以上工业增加值"
        r"(?P<direction>增长|下降|持平)(?P<value>\d+(?:\.\d+)?)?%?"
    ),
    "NBS_CN_CORE_CPI_YOY": re.compile(
        r"(?P<year>20\d{2})年(?P<month>\d{1,2})月份居民消费价格"
    ),
    "NBS_CN_GOODS_CPI_YOY": re.compile(
        r"(?P<year>20\d{2})年(?P<month>\d{1,2})月份居民消费价格"
    ),
    "NBS_CN_SERVICES_CPI_YOY": re.compile(
        r"(?P<year>20\d{2})年(?P<month>\d{1,2})月份居民消费价格"
    ),
}


class _ReleaseLinkParser(HTMLParser):
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
            self._text = []


def discover_release_urls(content: bytes, base_url: str, indicator_id: str) -> list[str]:
    parser = _ReleaseLinkParser()
    parser.feed(content.decode("utf-8", errors="replace"))
    title_patterns = {
        "NBS_CN_CPI_YOY": r"20\d{2}年\d{1,2}月份居民消费价格",
        "NBS_CN_PPI_YOY": r"20\d{2}年\d{1,2}月份工业生产者出厂价格",
        "NBS_CN_INDUSTRIAL_PRODUCTION_YOY": r"20\d{2}年\d{1,2}月份规模以上工业增加值",
    }
    title_pattern = title_patterns.get(indicator_id)
    if title_pattern is None:
        raise ConnectorError(f"Unsupported NBS listing indicator: {indicator_id}")
    found = []
    for href, title in parser.links:
        if not re.search(title_pattern, title):
            continue
        url = urljoin(base_url, href)
        if urlparse(url).hostname == "www.stats.gov.cn" and url.endswith(".html"):
            found.append(url)
    return list(dict.fromkeys(found))


def discover_cpi_release_urls(content: bytes, base_url: str) -> list[str]:
    return discover_release_urls(content, base_url, "NBS_CN_CPI_YOY")


class NbsReleaseConnector:
    """Parse a named indicator from an explicit NBS official release page."""

    def __init__(self, client: httpx.Client | None = None) -> None:
        self.client = client or httpx.Client(timeout=30, follow_redirects=True)

    def fetch(self, indicator_id: str, url: str) -> FetchResult:
        if indicator_id not in PATTERNS:
            raise ConnectorError(f"Unsupported NBS release indicator: {indicator_id}")
        if not url.startswith("https://www.stats.gov.cn/"):
            raise ConnectorError("NBS release URL must use the official stats.gov.cn host")
        response = request_with_retry(self.client, "GET", url)
        if response.status_code != 200:
            raise ConnectorError(f"NBS returned HTTP {response.status_code}")
        observation = self.parse(indicator_id, response.content)
        return FetchResult(
            source_id="nbs_cn",
            request_url=str(response.request.url),
            media_type=response.headers.get("content-type", "text/html"),
            retrieved_at=datetime.now(UTC),
            raw_content=response.content,
            observations=(observation,),
        )

    @staticmethod
    def parse(indicator_id: str, content: bytes) -> Observation:
        pattern = PATTERNS.get(indicator_id)
        if pattern is None:
            raise ConnectorError(f"Unsupported NBS release indicator: {indicator_id}")
        decoded = content.decode("utf-8", errors="replace")
        text = html.unescape(re.sub(r"<[^>]+>", "", decoded))
        text = re.sub(r"\s+", "", text)
        match = pattern.search(text)
        if match is None:
            raise ConnectorError("Official NBS release did not contain the expected headline value")
        year, month = int(match["year"]), int(match["month"])
        table_labels = {
            "NBS_CN_CORE_CPI_YOY": "其中：不包括食品和能源",
            "NBS_CN_GOODS_CPI_YOY": "其中：消费品",
            "NBS_CN_SERVICES_CPI_YOY": "服务",
        }
        if indicator_id in table_labels:
            value = _table_row_yoy(decoded, table_labels[indicator_id])
        else:
            direction = match["direction"]
            raw_value = match["value"]
            if direction == "持平":
                value = 0.0
            elif raw_value is None:
                raise ConnectorError("NBS release direction had no numeric value")
            else:
                value = float(raw_value) * (-1 if direction == "下降" else 1)
        release_match = re.search(
            r"(?P<year>20\d{2})/(?P<month>\d{2})/(?P<day>\d{2})\s*(?P<hour>\d{2}):(?P<minute>\d{2})",
            decoded,
        )
        available_at = None
        if release_match is not None:
            available_at = datetime(
                int(release_match["year"]),
                int(release_match["month"]),
                int(release_match["day"]),
                int(release_match["hour"]),
                int(release_match["minute"]),
                tzinfo=ZoneInfo("Asia/Shanghai"),
            )
        return Observation(
            date(year, month, monthrange(year, month)[1]), value, available_at=available_at
        )


def _table_row_yoy(decoded: str, wanted_label: str) -> float:
    for row in re.findall(r"<tr[^>]*>.*?</tr>", decoded, flags=re.DOTALL):
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, flags=re.DOTALL)
        if len(cells) < 3:
            continue
        label = html.unescape(re.sub(r"<[^>]+>", "", cells[0]))
        label = re.sub(r"\s+", "", label).replace("　", "")
        if label != wanted_label:
            continue
        yoy_text = html.unescape(re.sub(r"<[^>]+>", " ", cells[2]))
        match = re.search(r"[-+]?\d+(?:\.\d+)?", yoy_text)
        if match is None:
            break
        return float(match.group(0))
    raise ConnectorError(f"NBS CPI table contained no usable {wanted_label} row")
