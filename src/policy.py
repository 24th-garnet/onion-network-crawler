from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from src.config import PolicyConfig
from src.normalizer import normalize_url


class CrawlPolicy:
    def __init__(self, config: PolicyConfig):
        self.config = config

    def is_url_allowed(self, url: str, depth: int) -> tuple[bool, str]:
        if depth > self.config.max_depth:
            return False, "depth_exceeded"

        norm = normalize_url(url)
        if norm is None:
            return False, "invalid_url"

        if norm.scheme not in self.config.allowed_schemes:
            return False, "scheme_not_allowed"

        parsed = urlparse(norm.normalized_url)
        path = parsed.path.lower()
        suffix = Path(path).suffix.lower()

        if suffix in self.config.skip_extensions:
            return False, f"extension_skipped:{suffix}"

        return True, "allowed"

    def is_content_type_allowed(self, content_type: str | None) -> tuple[bool, str]:
        if not content_type:
            return True, "unknown_content_type_allowed"

        ct = content_type.split(";")[0].strip().lower()

        for allowed in self.config.allowed_content_types:
            if ct == allowed.lower():
                return True, "allowed"

        return False, f"content_type_skipped:{ct}"

    def is_response_size_allowed(self, size_bytes: int | None) -> tuple[bool, str]:
        if size_bytes is None:
            return True, "unknown_size_allowed"

        if size_bytes > self.config.max_response_bytes:
            return False, "response_too_large"

        return True, "allowed"