# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""小红书第一轮真实平台验收：``ReviewCollectionRunner`` + ``XHSAdapter`` + SQLite。

浏览器与会话逻辑见 ``xhs_acceptance_bootstrap``；更完整的 JSON/Markdown 报告请用
``python -m review_intel.jobs.run_xhs_acceptance``。

运行（仓库根目录，需已登录小红书 Web）::

    python -m review_intel.jobs.runner_acceptance_demo --db-path /tmp/xhs_accept.db

若首页 ``goto`` 超时：检查网络/代理/VPN；或加大 ``--goto-timeout-ms``（默认 120000）。

"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path

from review_intel.jobs.models import CollectionRunLimits
from review_intel.jobs.xhs_acceptance_bootstrap import (
    _DEFAULT_GOTO_TIMEOUT_MS,
    build_acceptance_job,
    run_xhs_collection_with_browser,
)


async def _run_async(
    *,
    job_id: str,
    db_path: Path,
    keyword: str | None,
    goto_timeout_ms: int,
) -> None:
    job = build_acceptance_job(job_id=job_id, keyword=keyword)
    limits = CollectionRunLimits(
        max_search_pages=1,
        max_posts=3,
        max_comments_per_post=20,
        max_comment_pages_per_post=20,
        enable_replies=False,
    )
    summary = await run_xhs_collection_with_browser(
        job=job,
        db_path=db_path,
        limits=limits,
        goto_timeout_ms=goto_timeout_ms,
    )
    print(json.dumps(summary.model_dump(mode="json"), ensure_ascii=False, indent=2))


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    p = argparse.ArgumentParser(
        description="小红书 Runner 真实验收（女装/防晒衣/painpoint 示例作业 + CollectionRunLimits）",
    )
    p.add_argument(
        "--job-id",
        default="job-xhs-acceptance-womens-sun-painpoint",
        help="覆盖示例作业 ID",
    )
    p.add_argument(
        "--db-path",
        type=Path,
        default=Path("review_intel_data") / "xhs_acceptance" / "store.db",
        help="SQLite 路径（父目录会自动创建）",
    )
    p.add_argument(
        "--keyword",
        default=None,
        help="覆盖搜索词（空格分词写入 QuerySpec.terms）；默认用示例作业 terms",
    )
    p.add_argument(
        "--goto-timeout-ms",
        type=int,
        default=_DEFAULT_GOTO_TIMEOUT_MS,
        help="首页 Page.goto 超时（毫秒）；网络慢或跨境可加大，例如 180000",
    )
    args = p.parse_args()
    asyncio.run(
        _run_async(
            job_id=args.job_id,
            db_path=args.db_path,
            keyword=args.keyword,
            goto_timeout_ms=args.goto_timeout_ms,
        )
    )


if __name__ == "__main__":
    main()
