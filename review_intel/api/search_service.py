# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""跨作业 SQLite 扫描 + 关键词过滤（应用层子串匹配）。

数据布局与 ``JobRegistry.store_path`` 一致：``storage_root/{job_id}/store.db``。
不修改现有表结构；首版遍历 ``payload_json``，后续可换 FTS5。
"""

from __future__ import annotations

import logging
from pathlib import Path

from review_intel.schemas.normalized import NormalizedReview
from review_intel.storage.sqlite_support import connect

logger = logging.getLogger(__name__)


def iter_job_store_paths(storage_root: Path) -> list[tuple[str, Path]]:
    """枚举 ``storage_root`` 下各作业目录中的 ``store.db``。

    Returns:
        ``(job_id, db_path)`` 列表；仅包含存在且为文件的库路径。
    """
    root = Path(storage_root)
    if not root.is_dir():
        return []
    out: list[tuple[str, Path]] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        job_id = child.name
        if ".." in job_id or "/" in job_id or "\\" in job_id:
            continue
        db = child / "store.db"
        if db.is_file():
            out.append((job_id, db))
    return out


def _matches_keyword(review: NormalizedReview, keyword: str) -> bool:
    """子串匹配（大小写不敏感）：正文、命中词、``extra_meta.crawl_query``。"""
    k = keyword.strip().lower()
    if not k:
        return False
    text = (review.review_text or "").lower()
    if k in text:
        return True
    for t in review.query_hit_terms:
        if k in (t or "").lower():
            return True
    cq = (review.extra_meta or {}).get("crawl_query")
    if cq is not None and k in str(cq).lower():
        return True
    for fld in (review.industry, review.category, review.brand):
        if fld and k in str(fld).lower():
            return True
    return False


def load_normalized_for_job(db_path: Path) -> list[NormalizedReview]:
    """读取单库全部归一化行。"""
    conn = connect(str(db_path))
    try:
        rows = conn.execute("SELECT payload_json FROM normalized_reviews").fetchall()
    finally:
        conn.close()
    out: list[NormalizedReview] = []
    for r in rows:
        try:
            out.append(NormalizedReview.model_validate_json(r["payload_json"]))
        except Exception as e:  # noqa: BLE001
            logger.warning("skip invalid payload in %s: %s", db_path, e)
    return out


def scan_storage_for_keyword(
    storage_root: Path,
    keyword: str,
    *,
    exclude_job_id: str | None = None,
) -> list[tuple[str, NormalizedReview]]:
    """扫描所有作业库，返回关键词命中的 ``(job_id, review)``。"""
    hits: list[tuple[str, NormalizedReview]] = []
    for job_id, db_path in iter_job_store_paths(storage_root):
        if exclude_job_id is not None and job_id == exclude_job_id:
            continue
        for rev in load_normalized_for_job(db_path):
            if _matches_keyword(rev, keyword):
                hits.append((job_id, rev))
    return hits
