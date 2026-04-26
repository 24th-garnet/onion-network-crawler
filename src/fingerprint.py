from __future__ import annotations

import hashlib
import re
from bs4 import BeautifulSoup


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def html_to_normalized_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text = soup.get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def html_fingerprints(html: str) -> dict[str, str]:
    raw_hash = sha256_text(html)
    normalized_text = html_to_normalized_text(html)
    text_hash = sha256_text(normalized_text)
    return {
        "raw_html_sha256": raw_hash,
        "normalized_text_sha256": text_hash,
    }