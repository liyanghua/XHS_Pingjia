# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""原始事件 SQLite 存储。

选用 **SQLite**（而非纯 JSONL）的原因：

- 需要按 ``job_id`` 随机读、按 ``event_id`` 主键去重，B-Tree 索引比扫描整文件更合适。
- 单文件即可复制备份，仍便于调试与整体回放；后续可迁 PostgreSQL 而保留 Repository 接口。
"""

from __future__ import annotations

import logging
import sqlite3

from review_intel.schemas.raw_event import RawReviewEvent
from review_intel.storage.repository_protocols import RawReviewRepository
from review_intel.storage.sqlite_support import dumps_model

logger = logging.getLogger(__name__)


class SqliteRawReviewStore:
    """基于 SQLite 的 ``RawReviewRepository`` 实现。"""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def save(self, event: RawReviewEvent) -> bool:
        """``INSERT OR IGNORE``：重复 ``event_id`` 返回 ``False``。"""
        payload = dumps_model(event)
        cur = self._conn.execute(
            """
            INSERT OR IGNORE INTO raw_review_events (event_id, job_id, payload_json)
            VALUES (?, ?, ?)
            """,
            (event.event_id, event.job_id, payload),
        )
        self._conn.commit()
        inserted = cur.rowcount == 1
        if not inserted:
            logger.debug("skip duplicate raw event_id=%s", event.event_id)
        return inserted

    def list_by_job(self, job_id: str) -> list[RawReviewEvent]:
        rows = self._conn.execute(
            "SELECT payload_json FROM raw_review_events WHERE job_id = ? ORDER BY event_id",
            (job_id,),
        ).fetchall()
        return [RawReviewEvent.model_validate_json(r["payload_json"]) for r in rows]


def open_raw_store(db_path: str) -> SqliteRawReviewStore:
    """便捷工厂：打开库文件并返回 raw 存储（与 ``open_normalized_store`` 可共享路径）。"""
    from review_intel.storage.sqlite_support import connect

    return SqliteRawReviewStore(connect(db_path))
