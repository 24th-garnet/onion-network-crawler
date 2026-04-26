from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import requests

from src.config import TorConfig
from src.policy import CrawlPolicy


@dataclass(frozen=True)
class FetchResult:
    url: str
    final_url: str | None
    ok: bool
    status_code: int | None
    content_type: str | None
    body_text: str | None
    body_bytes: bytes | None
    error_type: str | None
    error_message: str | None
    elapsed_sec: float


class TorFetcher:
    def __init__(self, config: TorConfig, policy: CrawlPolicy):
        self.config = config
        self.policy = policy
        self.session = requests.Session()
        self.session.proxies.update(
            {
                "http": self.config.proxy_url,
                "https": self.config.proxy_url,
            }
        )
        self.session.headers.update(
            {
                "User-Agent": self.config.user_agent,
                "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.1",
            }
        )

    def fetch(self, url: str) -> FetchResult:
        last_error_type: Optional[str] = None
        last_error_message: Optional[str] = None

        for attempt in range(self.config.max_retries + 1):
            started = time.time()
            try:
                response = self.session.get(
                    url,
                    timeout=self.config.request_timeout_sec,
                    allow_redirects=True,
                    stream=True,
                )

                content_type = response.headers.get("Content-Type")
                ok_ct, reason_ct = self.policy.is_content_type_allowed(content_type)
                if not ok_ct:
                    response.close()
                    return FetchResult(
                        url=url,
                        final_url=response.url,
                        ok=False,
                        status_code=response.status_code,
                        content_type=content_type,
                        body_text=None,
                        body_bytes=None,
                        error_type="content_type_blocked",
                        error_message=reason_ct,
                        elapsed_sec=time.time() - started,
                    )

                content_length = response.headers.get("Content-Length")
                if content_length and content_length.isdigit():
                    ok_size, reason_size = self.policy.is_response_size_allowed(int(content_length))
                    if not ok_size:
                        response.close()
                        return FetchResult(
                            url=url,
                            final_url=response.url,
                            ok=False,
                            status_code=response.status_code,
                            content_type=content_type,
                            body_text=None,
                            body_bytes=None,
                            error_type="response_too_large",
                            error_message=reason_size,
                            elapsed_sec=time.time() - started,
                        )

                chunks: list[bytes] = []
                total = 0
                for chunk in response.iter_content(chunk_size=65536):
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > self.policy.config.max_response_bytes:
                        response.close()
                        return FetchResult(
                            url=url,
                            final_url=response.url,
                            ok=False,
                            status_code=response.status_code,
                            content_type=content_type,
                            body_text=None,
                            body_bytes=None,
                            error_type="response_too_large",
                            error_message="stream_exceeded_limit",
                            elapsed_sec=time.time() - started,
                        )
                    chunks.append(chunk)

                body_bytes = b"".join(chunks)
                response.encoding = response.encoding or "utf-8"
                body_text = body_bytes.decode(response.encoding, errors="replace")

                return FetchResult(
                    url=url,
                    final_url=response.url,
                    ok=200 <= response.status_code < 400,
                    status_code=response.status_code,
                    content_type=content_type,
                    body_text=body_text,
                    body_bytes=body_bytes,
                    error_type=None if 200 <= response.status_code < 400 else "http_error",
                    error_message=None if 200 <= response.status_code < 400 else f"HTTP {response.status_code}",
                    elapsed_sec=time.time() - started,
                )

            except requests.exceptions.Timeout as e:
                last_error_type = "timeout"
                last_error_message = str(e)
            except requests.exceptions.ProxyError as e:
                last_error_type = "proxy_error"
                last_error_message = str(e)
            except requests.exceptions.ConnectionError as e:
                last_error_type = "connection_error"
                last_error_message = str(e)
            except requests.exceptions.RequestException as e:
                last_error_type = "request_error"
                last_error_message = str(e)

            if attempt < self.config.max_retries:
                time.sleep(self.config.retry_sleep_sec)

        return FetchResult(
            url=url,
            final_url=None,
            ok=False,
            status_code=None,
            content_type=None,
            body_text=None,
            body_bytes=None,
            error_type=last_error_type,
            error_message=last_error_message,
            elapsed_sec=0.0,
        )