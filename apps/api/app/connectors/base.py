import time
from dataclasses import dataclass
from datetime import date, datetime

import httpx


class ConnectorError(RuntimeError):
    pass


@dataclass(frozen=True)
class Observation:
    observation_date: date
    value: float | None
    status: str = "published"
    available_at: datetime | None = None


@dataclass(frozen=True)
class FetchResult:
    source_id: str
    request_url: str
    media_type: str
    retrieved_at: datetime
    raw_content: bytes
    observations: tuple[Observation, ...]


def request_with_retry(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    attempts: int = 3,
    **kwargs,
) -> httpx.Response:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            response = client.request(method, url, **kwargs)
            if response.status_code != 429 and response.status_code < 500:
                return response
            last_error = ConnectorError(f"Retryable HTTP {response.status_code}")
        except httpx.TransportError as error:
            last_error = error
        if attempt < attempts - 1:
            time.sleep(0.25 * (2**attempt))
    raise ConnectorError(f"Request failed after {attempts} attempts: {last_error}")
