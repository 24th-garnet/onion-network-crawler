from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin, urlparse, urlunparse


ONION_V3_RE = re.compile(r"^[a-z2-7]{56}\.onion$", re.IGNORECASE)
ONION_IN_TEXT_RE = re.compile(r"\b[a-z2-7]{56}\.onion\b", re.IGNORECASE)


@dataclass(frozen=True)
class NormalizedURL:
    original_url: str
    normalized_url: str
    scheme: str
    host: str
    onion_host: Optional[str]
    path: str
    is_onion: bool


def extract_onion_hosts(text: str) -> list[str]:
    return sorted(set(m.group(0).lower() for m in ONION_IN_TEXT_RE.finditer(text)))


def is_v3_onion_host(host: str) -> bool:
    return bool(ONION_V3_RE.match(host.lower()))


def normalize_url(
    url: str,
    base_url: str | None = None,
    keep_query: bool = True,
) -> Optional[NormalizedURL]:
    url = (url or "").strip()
    if not url:
        return None

    if url.startswith(("mailto:", "javascript:", "data:", "tel:")):
        return None

    if base_url:
        url = urljoin(base_url, url)

    parsed = urlparse(url)

    if not parsed.scheme:
        url = "http://" + url
        parsed = urlparse(url)

    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower().strip(".")

    if not host:
        return None

    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    query = parsed.query if keep_query else ""
    fragment = ""

    netloc = host
    if parsed.port:
        netloc = f"{host}:{parsed.port}"

    normalized = urlunparse((scheme, netloc, path, "", query, fragment))

    onion_host = host if host.endswith(".onion") else None

    return NormalizedURL(
        original_url=url,
        normalized_url=normalized,
        scheme=scheme,
        host=host,
        onion_host=onion_host,
        path=path,
        is_onion=onion_host is not None,
    )


def host_from_url(url: str) -> Optional[str]:
    parsed = urlparse(url)
    return (parsed.hostname or "").lower() or None


def onion_host_from_url(url: str) -> Optional[str]:
    host = host_from_url(url)
    if host and host.endswith(".onion"):
        return host
    return None