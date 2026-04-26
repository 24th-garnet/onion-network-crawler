from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone

from src.normalizer import normalize_url
from src.policy import CrawlPolicy
from src.storage import Storage


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SeedManager:
    def __init__(self, storage: Storage, policy: CrawlPolicy):
        self.storage = storage
        self.policy = policy

    def import_seeds(
        self,
        seeds_path: str | Path,
        seed_origin: str = "manual_hidden_wiki",
        priority: int = 10,
    ) -> int:
        seeds_path = Path(seeds_path)
        count = 0
        now = utc_now_iso()

        with seeds_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                norm = normalize_url(line)
                if norm is None:
                    continue

                allowed, _ = self.policy.is_url_allowed(norm.normalized_url, depth=0)
                if not allowed:
                    continue

                self.storage.enqueue_url(
                    url=norm.normalized_url,
                    onion_host=norm.onion_host,
                    depth=0,
                    priority=priority,
                    seed_origin=seed_origin,
                    discovered_from_url=None,
                    discovered_at=now,
                )
                count += 1

        return count