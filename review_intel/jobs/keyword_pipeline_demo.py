# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""关键词 → 搜索 → 评论 → 归一化 → 清洗 → SQLite 入库 → **打印入库内容**（离线演示）。

使用 ``DummyAdapter``：不访问外网，但走与生产相同的 ``ReviewCollectionRunner``、
``clean_and_score_reviews``、``SqliteNormalizedReviewStore``，便于核对 ``job_id``、
``extra_meta.crawl_query``、去重与质量分等。

与 ``test_runner.py`` 验证的是同一条链路；本脚本侧重**人工可读输出**。

运行示例：

.. code-block:: bash

   cd /path/to/MediaCrawler-main
   python -m review_intel.jobs.keyword_pipeline_demo --keyword "防晒 搓泥"
   # 或
   make review-intel-keyword-pipeline

真实小红书网络验收（不经 Runner 入库）见 ``python -m review_intel.adapters.xhs_demo``。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import tempfile
from pathlib import Path

from review_intel.adapters.dummy import DummyAdapter
from review_intel.jobs.models import CollectionJob, FreshnessLevel, QueryIntent, QuerySpec
from review_intel.jobs.runner import ReviewCollectionRunner
from review_intel.schemas.enums import JobStatus, PlatformType
from review_intel.storage.sqlite_support import open_review_intel_stores


def _job_from_keyword(keyword: str, job_id: str) -> CollectionJob:
    """构造带检索词的 ``CollectionJob``（``runner._query_from_job`` 会拼成 crawl_query）。"""
    terms = [t for t in keyword.replace(",", " ").split() if t.strip()]
    if not terms:
        terms = ["demo"]
    spec = QuerySpec(
        industry="demo",
        category="demo",
        brand=None,
        intent=QueryIntent.PAINPOINT_SEARCH,
        terms=terms,
        negative_terms=[],
        time_window=None,
        platforms=[PlatformType.XHS],
    )
    return CollectionJob(
        job_id=job_id,
        industry=spec.industry,
        category=spec.category,
        brand=None,
        query_spec=spec,
        target_types=["post", "comment"],
        priority=0,
        freshness_level=FreshnessLevel.NORMAL,
        status=JobStatus.PENDING,
        owner="keyword-pipeline-demo",
    )


async def _run_async(keyword: str, job_id: str) -> None:
    job = _job_from_keyword(keyword, job_id)
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "keyword_pipeline.db"
        raw_store, norm_store = open_review_intel_stores(db_path)
        summary = await ReviewCollectionRunner().run(job, DummyAdapter(), raw_store, norm_store)

        stored = norm_store.query()
        raw_rows = raw_store.list_by_job(job.job_id)

    print("=== CollectionRunSummary ===")
    print(json.dumps(summary.model_dump(mode="json"), ensure_ascii=False, indent=2))

    print(f"\n=== SQLite normalized_reviews（共 {len(stored)} 条，payload_json 反序列化）===")
    for i, rev in enumerate(stored, 1):
        print(f"\n--- [{i}] review_id={rev.review_id} ---")
        print(json.dumps(rev.model_dump(mode="json"), ensure_ascii=False, indent=2))

    print(f"\n=== raw_review_events 同 job（共 {len(raw_rows)} 条，节选 event_id / job_id）===")
    for ev in raw_rows:
        print(f"  event_id={ev.event_id} job_id={ev.job_id}")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    p = argparse.ArgumentParser(
        description="关键词驱动的 Runner 全链路演示（DummyAdapter + 临时 DB + 打印入库）",
    )
    p.add_argument(
        "--keyword",
        default="闷热 假滑",
        help="写入 QuerySpec.terms，空格分词；合并为 Runner 的 crawl_query",
    )
    p.add_argument("--job-id", default="job-keyword-pipeline-demo", help="作业 ID")
    args = p.parse_args()
    asyncio.run(_run_async(args.keyword, args.job_id))


if __name__ == "__main__":
    main()
