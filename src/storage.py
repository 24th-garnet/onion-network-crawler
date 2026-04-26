from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Optional


SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS services (
    service_id INTEGER PRIMARY KEY AUTOINCREMENT,
    onion_host TEXT NOT NULL UNIQUE,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pages (
    page_id INTEGER PRIMARY KEY AUTOINCREMENT,
    service_id INTEGER,
    url TEXT NOT NULL UNIQUE,
    onion_host TEXT,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    FOREIGN KEY(service_id) REFERENCES services(service_id)
);

CREATE TABLE IF NOT EXISTS snapshots (
    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    page_id INTEGER NOT NULL,
    fetched_at TEXT NOT NULL,
    final_url TEXT,
    status_code INTEGER,
    content_type TEXT,
    title TEXT,
    meta_description TEXT,
    raw_html_sha256 TEXT,
    normalized_text_sha256 TEXT,
    ok INTEGER NOT NULL,
    error_type TEXT,
    error_message TEXT,
    elapsed_sec REAL,
    FOREIGN KEY(page_id) REFERENCES pages(page_id)
);

CREATE TABLE IF NOT EXISTS links (
    link_id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER NOT NULL,
    source_page_id INTEGER NOT NULL,
    source_url TEXT NOT NULL,
    target_url TEXT NOT NULL,
    target_host TEXT,
    target_onion_host TEXT,
    is_onion INTEGER NOT NULL,
    anchor_text TEXT,
    observed_at TEXT NOT NULL,
    UNIQUE(snapshot_id, source_url, target_url, anchor_text),
    FOREIGN KEY(snapshot_id) REFERENCES snapshots(snapshot_id),
    FOREIGN KEY(source_page_id) REFERENCES pages(page_id)
);

CREATE TABLE IF NOT EXISTS crawl_queue (
    queue_id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL UNIQUE,
    onion_host TEXT,
    depth INTEGER NOT NULL,
    priority INTEGER NOT NULL DEFAULT 100,
    seed_origin TEXT,
    discovered_from_url TEXT,
    discovered_at TEXT NOT NULL,
    next_fetch_at TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    last_error TEXT
);

CREATE TABLE IF NOT EXISTS events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    page_id INTEGER,
    snapshot_id INTEGER,
    source_url TEXT,
    target_url TEXT,
    event_time TEXT NOT NULL,
    details TEXT,
    FOREIGN KEY(page_id) REFERENCES pages(page_id),
    FOREIGN KEY(snapshot_id) REFERENCES snapshots(snapshot_id)
);

CREATE TABLE IF NOT EXISTS fetch_errors (
    error_id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL,
    onion_host TEXT,
    error_type TEXT,
    error_message TEXT,
    occurred_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_pages_onion_host ON pages(onion_host);
CREATE INDEX IF NOT EXISTS idx_snapshots_page_time ON snapshots(page_id, fetched_at);
CREATE INDEX IF NOT EXISTS idx_links_source_target ON links(source_url, target_url);
CREATE INDEX IF NOT EXISTS idx_queue_status_priority ON crawl_queue(status, priority);
"""


class Storage:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")

    def close(self) -> None:
        self.conn.close()

    def init_db(self) -> None:
        self.conn.executescript(SCHEMA_SQL)
        self.conn.commit()

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Cursor:
        cur = self.conn.execute(sql, params)
        self.conn.commit()
        return cur

    def query(self, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        return list(self.conn.execute(sql, params))

    def get_or_create_service(self, onion_host: str, now: str) -> int:
        row = self.conn.execute(
            "SELECT service_id FROM services WHERE onion_host = ?",
            (onion_host,),
        ).fetchone()
        if row:
            self.conn.execute(
                "UPDATE services SET last_seen = ? WHERE service_id = ?",
                (now, row["service_id"]),
            )
            self.conn.commit()
            return int(row["service_id"])

        cur = self.conn.execute(
            """
            INSERT INTO services(onion_host, first_seen, last_seen)
            VALUES (?, ?, ?)
            """,
            (onion_host, now, now),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def get_or_create_page(self, url: str, onion_host: Optional[str], now: str) -> int:
        row = self.conn.execute(
            "SELECT page_id FROM pages WHERE url = ?",
            (url,),
        ).fetchone()
        if row:
            self.conn.execute(
                "UPDATE pages SET last_seen = ? WHERE page_id = ?",
                (now, row["page_id"]),
            )
            self.conn.commit()
            return int(row["page_id"])

        service_id = None
        if onion_host:
            service_id = self.get_or_create_service(onion_host, now)

        cur = self.conn.execute(
            """
            INSERT INTO pages(service_id, url, onion_host, first_seen, last_seen)
            VALUES (?, ?, ?, ?, ?)
            """,
            (service_id, url, onion_host, now, now),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def insert_snapshot(
        self,
        page_id: int,
        fetched_at: str,
        final_url: str | None,
        status_code: int | None,
        content_type: str | None,
        title: str | None,
        meta_description: str | None,
        raw_html_sha256: str | None,
        normalized_text_sha256: str | None,
        ok: bool,
        error_type: str | None,
        error_message: str | None,
        elapsed_sec: float,
    ) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO snapshots(
                page_id, fetched_at, final_url, status_code, content_type,
                title, meta_description, raw_html_sha256, normalized_text_sha256,
                ok, error_type, error_message, elapsed_sec
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                page_id,
                fetched_at,
                final_url,
                status_code,
                content_type,
                title,
                meta_description,
                raw_html_sha256,
                normalized_text_sha256,
                1 if ok else 0,
                error_type,
                error_message,
                elapsed_sec,
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def insert_link(
        self,
        snapshot_id: int,
        source_page_id: int,
        source_url: str,
        target_url: str,
        target_host: str | None,
        target_onion_host: str | None,
        is_onion: bool,
        anchor_text: str,
        observed_at: str,
    ) -> None:
        self.conn.execute(
            """
            INSERT OR IGNORE INTO links(
                snapshot_id, source_page_id, source_url, target_url,
                target_host, target_onion_host, is_onion, anchor_text, observed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot_id,
                source_page_id,
                source_url,
                target_url,
                target_host,
                target_onion_host,
                1 if is_onion else 0,
                anchor_text,
                observed_at,
            ),
        )
        self.conn.commit()

    def enqueue_url(
        self,
        url: str,
        onion_host: str | None,
        depth: int,
        priority: int,
        seed_origin: str | None,
        discovered_from_url: str | None,
        discovered_at: str,
    ) -> None:
        self.conn.execute(
            """
            INSERT OR IGNORE INTO crawl_queue(
                url, onion_host, depth, priority, seed_origin,
                discovered_from_url, discovered_at, next_fetch_at, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, NULL, 'pending')
            """,
            (
                url,
                onion_host,
                depth,
                priority,
                seed_origin,
                discovered_from_url,
                discovered_at,
            ),
        )
        self.conn.commit()

    def next_queue_item(self) -> sqlite3.Row | None:
        return self.conn.execute(
            """
            SELECT * FROM crawl_queue
            WHERE status = 'pending'
            ORDER BY priority ASC, queue_id ASC
            LIMIT 1
            """
        ).fetchone()

    def mark_queue_status(self, queue_id: int, status: str, last_error: str | None = None) -> None:
        self.conn.execute(
            """
            UPDATE crawl_queue
            SET status = ?, last_error = ?
            WHERE queue_id = ?
            """,
            (status, last_error, queue_id),
        )
        self.conn.commit()

    def insert_event(
        self,
        event_type: str,
        event_time: str,
        page_id: int | None = None,
        snapshot_id: int | None = None,
        source_url: str | None = None,
        target_url: str | None = None,
        details: str | None = None,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO events(
                event_type, page_id, snapshot_id, source_url,
                target_url, event_time, details
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_type,
                page_id,
                snapshot_id,
                source_url,
                target_url,
                event_time,
                details,
            ),
        )
        self.conn.commit()

    def insert_fetch_error(
        self,
        url: str,
        onion_host: str | None,
        error_type: str | None,
        error_message: str | None,
        occurred_at: str,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO fetch_errors(url, onion_host, error_type, error_message, occurred_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (url, onion_host, error_type, error_message, occurred_at),
        )
        self.conn.commit()