from __future__ import annotations

import json

from src.storage import Storage


class SnapshotDiffer:
    def __init__(self, storage: Storage):
        self.storage = storage

    def create_events_for_snapshot(
        self,
        page_id: int,
        snapshot_id: int,
        fetched_at: str,
    ) -> None:
        snapshots = self.storage.query(
            """
            SELECT snapshot_id, raw_html_sha256, normalized_text_sha256, ok, error_type
            FROM snapshots
            WHERE page_id = ?
            ORDER BY fetched_at DESC, snapshot_id DESC
            LIMIT 2
            """,
            (page_id,),
        )

        if len(snapshots) == 1:
            self.storage.insert_event(
                event_type="NEW_PAGE",
                page_id=page_id,
                snapshot_id=snapshot_id,
                event_time=fetched_at,
            )
            self._create_new_link_events(snapshot_id, fetched_at)
            return

        current = snapshots[0]
        previous = snapshots[1]

        if int(previous["ok"]) == 0 and int(current["ok"]) == 1:
            self.storage.insert_event(
                event_type="SERVICE_RECOVERED",
                page_id=page_id,
                snapshot_id=snapshot_id,
                event_time=fetched_at,
            )

        if int(previous["ok"]) == 1 and int(current["ok"]) == 0:
            self.storage.insert_event(
                event_type="SERVICE_DOWN",
                page_id=page_id,
                snapshot_id=snapshot_id,
                event_time=fetched_at,
                details=current["error_type"],
            )

        if (
            current["normalized_text_sha256"]
            and previous["normalized_text_sha256"]
            and current["normalized_text_sha256"] != previous["normalized_text_sha256"]
        ):
            self.storage.insert_event(
                event_type="CONTENT_CHANGED",
                page_id=page_id,
                snapshot_id=snapshot_id,
                event_time=fetched_at,
                details=json.dumps(
                    {
                        "prev_hash": previous["normalized_text_sha256"],
                        "curr_hash": current["normalized_text_sha256"],
                    },
                    ensure_ascii=False,
                ),
            )

        self._create_link_diff_events(
            previous_snapshot_id=int(previous["snapshot_id"]),
            current_snapshot_id=snapshot_id,
            fetched_at=fetched_at,
        )

    def _create_new_link_events(self, snapshot_id: int, fetched_at: str) -> None:
        links = self.storage.query(
            """
            SELECT source_url, target_url
            FROM links
            WHERE snapshot_id = ?
            """,
            (snapshot_id,),
        )

        for link in links:
            self.storage.insert_event(
                event_type="NEW_LINK",
                source_url=link["source_url"],
                target_url=link["target_url"],
                snapshot_id=snapshot_id,
                event_time=fetched_at,
            )

    def _create_link_diff_events(
        self,
        previous_snapshot_id: int,
        current_snapshot_id: int,
        fetched_at: str,
    ) -> None:
        prev_links = self.storage.query(
            "SELECT source_url, target_url FROM links WHERE snapshot_id = ?",
            (previous_snapshot_id,),
        )
        curr_links = self.storage.query(
            "SELECT source_url, target_url FROM links WHERE snapshot_id = ?",
            (current_snapshot_id,),
        )

        prev_set = {(r["source_url"], r["target_url"]) for r in prev_links}
        curr_set = {(r["source_url"], r["target_url"]) for r in curr_links}

        for source_url, target_url in sorted(curr_set - prev_set):
            self.storage.insert_event(
                event_type="NEW_LINK",
                snapshot_id=current_snapshot_id,
                source_url=source_url,
                target_url=target_url,
                event_time=fetched_at,
            )

        for source_url, target_url in sorted(prev_set - curr_set):
            self.storage.insert_event(
                event_type="REMOVED_LINK",
                snapshot_id=current_snapshot_id,
                source_url=source_url,
                target_url=target_url,
                event_time=fetched_at,
            )