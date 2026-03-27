# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""归一化评价 SQLite 存储（与 ``raw_store`` 共用同一 DB 文件与连接时可保证同事务边界）。

``payload_json`` 为 ``NormalizedReview`` 全量 JSON，含 ``job_id``、``extra_meta`` 等扩展字段。
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from typing import Optional

from review_intel.schemas.normalized import NormalizedReview
from review_intel.storage.repository_protocols import NormalizedReviewRepository
from review_intel.storage.sqlite_support import dumps_model

logger = logging.getLogger(__name__)


class SqliteNormalizedReviewStore:
    """基于 SQLite 的 ``NormalizedReviewRepository`` 实现。"""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def save(self, review: NormalizedReview) -> bool:
        """``INSERT OR IGNORE``：重复 ``review_id`` 返回 ``False``。"""
        payload = dumps_model(review)
        pub_iso = review.publish_time.isoformat()
        cur = self._conn.execute(
            """
            INSERT OR IGNORE INTO normalized_reviews
            (review_id, platform, category, publish_time_iso, payload_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                review.review_id,
                review.platform.value,
                review.category,
                pub_iso,
                payload,
            ),
        )
        self._conn.commit()
        inserted = cur.rowcount == 1
        if not inserted:
            logger.debug("skip duplicate normalized review_id=%s", review.review_id)
        return inserted

    def query(
        self,
        *,
        platform: Optional[str] = None,
        category: Optional[str] = None,
        time_start: Optional[datetime] = None,
        time_end: Optional[datetime] = None,
    ) -> list[NormalizedReview]:
        clauses: list[str] = []
        params: list[str] = []
        if platform is not None:
            clauses.append("platform = ?")
            params.append(platform)
        if category is not None:
            clauses.append("category = ?")
            params.append(category)
        if time_start is not None:
            clauses.append("publish_time_iso >= ?")
            params.append(time_start.isoformat())
        if time_end is not None:
            clauses.append("publish_time_iso <= ?")
            params.append(time_end.isoformat())
        where = " AND ".join(clauses) if clauses else "1=1"
        sql = f"SELECT payload_json FROM normalized_reviews WHERE {where} ORDER BY publish_time_iso"
        rows = self._conn.execute(sql, params).fetchall()
        return [NormalizedReview.model_validate_json(r["payload_json"]) for r in rows]


def open_normalized_store(db_path: str) -> SqliteNormalizedReviewStore:
    """便捷工厂：单独打开归一化存储。"""
    from review_intel.storage.sqlite_support import connect

    return SqliteNormalizedReviewStore(connect(db_path))
