from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Optional

from tqdm import tqdm

from src.fingerprint import html_fingerprints
from src.normalizer import normalize_url
from src.parser import parse_html
from src.policy import CrawlPolicy
from src.snapshot_diff import SnapshotDiffer
from src.storage import Storage
from src.tor_fetcher import TorFetcher


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class OnionCrawler:
    def __init__(
        self,
        storage: Storage,
        fetcher: TorFetcher,
        policy: CrawlPolicy,
    ):
        self.storage = storage
        self.fetcher = fetcher
        self.policy = policy
        self.differ = SnapshotDiffer(storage)
        self.last_host_fetch_time: dict[str, float] = {}

    def crawl(self, max_pages: Optional[int] = None, max_depth: Optional[int] = None) -> None:
        max_pages = max_pages if max_pages is not None else self.policy.config.max_pages
        max_depth = max_depth if max_depth is not None else self.policy.config.max_depth

        processed = 0
        pbar = tqdm(total=max_pages, desc="Crawling", unit="page")

        while processed < max_pages:
            item = self.storage.next_queue_item()
            if item is None:
                break

            queue_id = int(item["queue_id"])
            url = str(item["url"])
            depth = int(item["depth"])

            if depth > max_depth:
                self.storage.mark_queue_status(queue_id, "skipped", "depth_exceeded")
                continue

            allowed, reason = self.policy.is_url_allowed(url, depth)
            if not allowed:
                self.storage.mark_queue_status(queue_id, "skipped", reason)
                continue

            norm = normalize_url(url)
            if norm is None:
                self.storage.mark_queue_status(queue_id, "skipped", "invalid_url")
                continue

            self._respect_same_host_delay(norm.host)

            now = utc_now_iso()
            page_id = self.storage.get_or_create_page(
                url=norm.normalized_url,
                onion_host=norm.onion_host,
                now=now,
            )

            result = self.fetcher.fetch(norm.normalized_url)
            fetched_at = utc_now_iso()

            title = None
            meta_description = None
            raw_html_hash = None
            normalized_text_hash = None
            parsed_links = []

            if result.ok and result.body_text:
                parsed = parse_html(result.body_text)
                title = parsed.title
                meta_description = parsed.meta_description
                parsed_links = parsed.links

                fps = html_fingerprints(result.body_text)
                raw_html_hash = fps["raw_html_sha256"]
                normalized_text_hash = fps["normalized_text_sha256"]

            snapshot_id = self.storage.insert_snapshot(
                page_id=page_id,
                fetched_at=fetched_at,
                final_url=result.final_url,
                status_code=result.status_code,
                content_type=result.content_type,
                title=title,
                meta_description=meta_description,
                raw_html_sha256=raw_html_hash,
                normalized_text_sha256=normalized_text_hash,
                ok=result.ok,
                error_type=result.error_type,
                error_message=result.error_message,
                elapsed_sec=result.elapsed_sec,
            )

            if not result.ok:
                self.storage.insert_fetch_error(
                    url=norm.normalized_url,
                    onion_host=norm.onion_host,
                    error_type=result.error_type,
                    error_message=result.error_message,
                    occurred_at=fetched_at,
                )
                self.storage.mark_queue_status(queue_id, "failed", result.error_type)
                self.differ.create_events_for_snapshot(page_id, snapshot_id, fetched_at)
                processed += 1
                pbar.update(1)
                continue

            discovered_count = self._process_links(
                source_url=norm.normalized_url,
                source_page_id=page_id,
                snapshot_id=snapshot_id,
                parsed_links=parsed_links,
                depth=depth,
                observed_at=fetched_at,
                max_depth=max_depth,
            )

            self.storage.mark_queue_status(queue_id, "done", None)
            self.differ.create_events_for_snapshot(page_id, snapshot_id, fetched_at)

            processed += 1
            pbar.set_postfix({"new_links": discovered_count})
            pbar.update(1)

        pbar.close()

    def _respect_same_host_delay(self, host: str) -> None:
        delay = self.policy.config.same_host_delay_sec
        if delay <= 0:
            return

        now = time.time()
        last = self.last_host_fetch_time.get(host)
        if last is not None:
            elapsed = now - last
            if elapsed < delay:
                time.sleep(delay - elapsed)

        self.last_host_fetch_time[host] = time.time()

    def _process_links(
        self,
        source_url: str,
        source_page_id: int,
        snapshot_id: int,
        parsed_links,
        depth: int,
        observed_at: str,
        max_depth: int,
    ) -> int:
        discovered_count = 0
        seen_targets: set[str] = set()

        for link in parsed_links:
            target = normalize_url(link.href, base_url=source_url)
            if target is None:
                continue

            if target.normalized_url in seen_targets:
                continue
            seen_targets.add(target.normalized_url)

            self.storage.insert_link(
                snapshot_id=snapshot_id,
                source_page_id=source_page_id,
                source_url=source_url,
                target_url=target.normalized_url,
                target_host=target.host,
                target_onion_host=target.onion_host,
                is_onion=target.is_onion,
                anchor_text=link.anchor_text,
                observed_at=observed_at,
            )

            next_depth = depth + 1
            if target.is_onion and next_depth <= max_depth:
                allowed, _ = self.policy.is_url_allowed(target.normalized_url, next_depth)
                if allowed:
                    self.storage.enqueue_url(
                        url=target.normalized_url,
                        onion_host=target.onion_host,
                        depth=next_depth,
                        priority=100 + next_depth,
                        seed_origin="discovered_from_crawl",
                        discovered_from_url=source_url,
                        discovered_at=observed_at,
                    )
                    discovered_count += 1

        return discovered_count