# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""真小红书：搜索 + 评论 → 写入 ``REVIEW_INTEL_CAPTURE_ROOT/{job_id}/``（manifest + raw + events.jsonl）。

不落 SQLite；第二阶段用 ``python -m review_intel.jobs.ingest_capture``。

运行示例::

    export REVIEW_INTEL_CAPTURE_ROOT=~/review_intel_capture
    python -m review_intel.jobs.xhs_capture --keyword 防晒 --job-id job-xhs-001

"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import uuid
from pathlib import Path

import config
from media_platform.xhs.core import XiaoHongShuCrawler
from media_platform.xhs.exception import DataFetchError
from media_platform.xhs.field import SearchNoteType, SearchSortType
from media_platform.xhs.help import get_search_id
from playwright.async_api import async_playwright
from proxy.proxy_ip_pool import create_ip_pool
from tenacity import RetryError
from tools import utils

from review_intel.adapters.xhs_mapping import build_search_page_from_api
from review_intel.adapters.xiaohongshu import XHSAdapter
from review_intel.jobs.capture_io import (
    default_capture_root,
    job_capture_dir,
    manifest_template,
    utc_now_iso,
    write_json,
)

# 复用 xhs_demo 的会话与登录流程
from review_intel.adapters.xhs_demo import (
    _format_request_error,
    _looks_like_login_expired,
    ensure_xhs_api_session,
)


async def _run_capture(
    keyword: str,
    job_id: str,
    capture_root: Path,
    max_notes: int,
    max_comments: int | None,
) -> None:
    capture_root = Path(capture_root)
    job_dir = job_capture_dir(capture_root, job_id)
    raw_dir = job_dir / "raw"
    search_dir = raw_dir / "search"
    search_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / "notes").mkdir(parents=True, exist_ok=True)

    terms = [t for t in keyword.replace(",", " ").split() if t.strip()]
    if not terms:
        terms = ["demo"]
    crawl_query = " ".join(terms)

    manifest = manifest_template(
        job_id=job_id,
        crawl_query=crawl_query,
        industry="xhs-capture",
        category="xhs-capture",
        query_terms=terms,
        status="running",
    )
    write_json(job_dir / "manifest.json", manifest)

    crawler = XiaoHongShuCrawler()
    playwright_proxy_format, httpx_proxy_format = None, None
    if config.ENABLE_IP_PROXY:
        crawler.ip_proxy_pool = await create_ip_pool(config.IP_PROXY_POOL_COUNT, enable_validate_ip=True)
        ip_proxy_info = await crawler.ip_proxy_pool.get_proxy()
        playwright_proxy_format, httpx_proxy_format = utils.format_proxy_info(ip_proxy_info)

    try:
        async with async_playwright() as playwright:
            if config.ENABLE_CDP_MODE:
                crawler.browser_context = await crawler.launch_browser_with_cdp(
                    playwright,
                    playwright_proxy_format,
                    crawler.user_agent,
                    headless=config.CDP_HEADLESS,
                )
            else:
                chromium = playwright.chromium
                crawler.browser_context = await crawler.launch_browser(
                    chromium,
                    playwright_proxy_format,
                    crawler.user_agent,
                    headless=config.HEADLESS,
                )
                await crawler.browser_context.add_init_script(path="libs/stealth.min.js")

            crawler.context_page = await crawler.browser_context.new_page()
            await crawler.context_page.goto(crawler.index_url, wait_until="domcontentloaded")
            await asyncio.sleep(1.5)

            crawler.xhs_client = await crawler.create_xhs_client(httpx_proxy_format)
            await crawler.xhs_client.update_cookies(browser_context=crawler.browser_context)

            if not await ensure_xhs_api_session(crawler):
                print(
                    "\n[xhs_capture] 无法建立有效的小红书 API 会话（pong=False）。\n",
                    file=sys.stderr,
                )
                manifest["status"] = "failed"
                manifest["error"] = "ensure_xhs_api_session failed"
                manifest["capture_finished_at"] = utc_now_iso()
                write_json(job_dir / "manifest.json", manifest)
                await crawler.close()
                raise SystemExit(2)

            client = crawler.xhs_client
            search_id = get_search_id()
            data = await client.get_note_by_keyword(
                keyword=keyword.strip(),
                search_id=search_id,
                page=1,
                page_size=20,
                sort=SearchSortType.GENERAL,
                note_type=SearchNoteType.ALL,
            )
            if not isinstance(data, dict):
                data = {}

            write_json(search_dir / "page_001.json", data)

            sp = build_search_page_from_api(
                api_data=data,
                search_id=search_id,
                page=1,
                job_id=job_id,
            )

            adapter = XHSAdapter(
                client,
                job_id=job_id,
                industry="xhs-capture",
                category="xhs-capture",
            )
            adapter._remember_note_tokens(sp.items)

            events_path = raw_dir / "events.jsonl"
            n_written = 0
            with events_path.open("w", encoding="utf-8") as f:
                hits = sp.items[:max_notes]
                for note in hits:
                    pid = note.get("id") or note.get("post_id")
                    if not pid:
                        continue
                    pid = str(pid)
                    try:
                        cpage = await adapter.fetch_comments(pid, None)
                    except (RetryError, DataFetchError) as e:
                        utils.logger.warning(
                            "[xhs_capture] fetch_comments failed note_id=%s: %s", pid, e
                        )
                        continue

                    items = cpage.items
                    if max_comments is not None:
                        items = items[: max_comments]

                    for ev in items:
                        ev_job = ev.model_copy(update={"job_id": job_id})
                        f.write(ev_job.model_dump_json() + "\n")
                        n_written += 1

            manifest["status"] = "succeeded"
            manifest["capture_finished_at"] = utc_now_iso()
            manifest["events_written"] = n_written
            manifest["error"] = None
            write_json(job_dir / "manifest.json", manifest)

            print(f"[xhs_capture] job_id={job_id} dir={job_dir} events={n_written}")
            await crawler.close()

    except SystemExit:
        raise
    except Exception as e:
        utils.logger.exception("[xhs_capture] failed: %s", e)
        manifest["status"] = "failed"
        manifest["error"] = repr(e)
        manifest["capture_finished_at"] = utc_now_iso()
        write_json(job_dir / "manifest.json", manifest)
        raise


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    p = argparse.ArgumentParser(description="小红书抓取落盘（manifest + raw + events.jsonl），不落库")
    p.add_argument("--keyword", default="防晒", help="搜索关键词")
    p.add_argument(
        "--job-id",
        default=None,
        help="作业 ID；默认随机 job-xhs-<uuid>",
    )
    p.add_argument(
        "--capture-root",
        type=Path,
        default=None,
        help="覆盖环境变量 REVIEW_INTEL_CAPTURE_ROOT",
    )
    p.add_argument("--max-notes", type=int, default=3, help="最多处理搜索结果中前几条帖子")
    p.add_argument(
        "--max-comments",
        type=int,
        default=None,
        help="每帖最多写入几条评论；默认不截断",
    )
    args = p.parse_args()
    jid = args.job_id or f"job-xhs-{uuid.uuid4().hex[:12]}"
    root = args.capture_root or default_capture_root()
    asyncio.run(
        _run_capture(
            args.keyword,
            jid,
            root,
            args.max_notes,
            args.max_comments,
        )
    )


if __name__ == "__main__":
    main()
