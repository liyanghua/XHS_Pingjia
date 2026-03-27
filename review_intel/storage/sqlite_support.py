# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""SQLite 连接与表结构初始化（单文件、无 ORM，便于替换为其他 DB）。"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1


def connect(db_path: str | Path) -> sqlite3.Connection:
    """打开数据库并确保 schema 存在。"""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    _init_schema(conn)
    return conn


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS review_intel_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS raw_review_events (
            event_id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL,
            payload_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_raw_events_job ON raw_review_events(job_id);

        CREATE TABLE IF NOT EXISTS normalized_reviews (
            review_id TEXT PRIMARY KEY,
            platform TEXT NOT NULL,
            category TEXT,
            publish_time_iso TEXT NOT NULL,
            payload_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_norm_platform_cat
            ON normalized_reviews(platform, category);
        CREATE INDEX IF NOT EXISTS idx_norm_publish_time ON normalized_reviews(publish_time_iso);
        """
    )
    row = conn.execute(
        "SELECT 1 FROM review_intel_meta WHERE key = ?",
        ("schema_version",),
    ).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO review_intel_meta (key, value) VALUES (?, ?)",
            ("schema_version", str(SCHEMA_VERSION)),
        )
    conn.commit()


def dumps_model(model: Any) -> str:
    return json.dumps(model.model_dump(mode="json"), ensure_ascii=False)


def open_review_intel_stores(db_path: str | Path) -> tuple[Any, Any]:
    """共享同一 SQLite 连接，返回 raw 与 normalized 两仓库。"""
    from review_intel.storage.normalized_store import SqliteNormalizedReviewStore
    from review_intel.storage.raw_store import SqliteRawReviewStore

    conn = connect(db_path)
    return SqliteRawReviewStore(conn), SqliteNormalizedReviewStore(conn)
