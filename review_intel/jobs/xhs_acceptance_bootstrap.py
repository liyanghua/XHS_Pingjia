# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""小红书验收入口与 ``runner_acceptance_demo`` 共用的浏览器启动与 Runner 执行逻辑。"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

import config
from media_platform.xhs.core import XiaoHongShuCrawler
from playwright.async_api import async_playwright
from proxy.proxy_ip_pool import create_ip_pool
from tools import utils

from review_intel.adapters.xhs_demo import ensure_xhs_api_session
from review_intel.adapters.xiaohongshu import XHSAdapter
from review_intel.jobs.models import CollectionJob, CollectionRunLimits, QuerySpec, example_job_xhs_acceptance_womens_sun_painpoint
from review_intel.jobs.runner import CollectionRunSummary, ReviewCollectionRunner
from review_intel.schemas.enums import JobStatus, PlatformType
from review_intel.storage.sqlite_support import open_review_intel_stores

logger = logging.getLogger(__name__)

_DEFAULT_GOTO_TIMEOUT_MS = 120_000


async def goto_xhs_index(page: object, url: str, *, timeout_ms: int) -> None:
    """打开首页：优先 ``domcontentloaded``，超时则降级为 ``commit`` 并稍等 DOM。"""
    from playwright.async_api import Page

    if not isinstance(page, Page):
        raise TypeError("expected Playwright Page")
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
    except Exception as e:
        logger.warning(
            "goto_xhs_index: domcontentloaded failed (%s), retry with commit",
            e,
        )
        await page.goto(url, wait_until="commit", timeout=timeout_ms)
        await asyncio.sleep(3.0)


def build_acceptance_job(
    *,
    job_id: str,
    keyword: str | None,
) -> CollectionJob:
    """基于 ``example_job_xhs_acceptance_womens_sun_painpoint`` 可覆盖关键词。"""
    base = example_job_xhs_acceptance_womens_sun_painpoint()
    terms = base.query_spec.terms
    if keyword:
        terms = [t for t in keyword.replace(",", " ").split() if t.strip()] or terms
    spec = QuerySpec(
        industry=base.query_spec.industry,
        category=base.query_spec.category,
        brand=base.query_spec.brand,
        intent=base.query_spec.intent,
        terms=terms,
        negative_terms=list(base.query_spec.negative_terms),
        time_window=base.query_spec.time_window,
        platforms=[PlatformType.XHS],
    )
    return CollectionJob(
        job_id=job_id,
        industry=base.industry,
        category=base.category,
        brand=base.brand,
        query_spec=spec,
        target_types=base.target_types,
        priority=base.priority,
        freshness_level=base.freshness_level,
        status=JobStatus.PENDING,
        owner=base.owner,
    )


async def run_xhs_collection_with_browser(
    *,
    job: CollectionJob,
    db_path: Path,
    limits: CollectionRunLimits,
    goto_timeout_ms: int = _DEFAULT_GOTO_TIMEOUT_MS,
) -> CollectionRunSummary:
    """启动 Chromium/Playwright、同步 Cookie、执行 ``ReviewCollectionRunner`` 并关闭浏览器。

    前置条件：需已登录小红书 Web（见 ``review_intel/adapters/README_XHS.md``）。
    """
    crawler = XiaoHongShuCrawler()
    playwright_proxy_format, httpx_proxy_format = None, None
    if config.ENABLE_IP_PROXY:
        crawler.ip_proxy_pool = await create_ip_pool(config.IP_PROXY_POOL_COUNT, enable_validate_ip=True)
        ip_proxy_info = await crawler.ip_proxy_pool.get_proxy()
        playwright_proxy_format, httpx_proxy_format = utils.format_proxy_info(ip_proxy_info)

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
        await goto_xhs_index(crawler.context_page, crawler.index_url, timeout_ms=goto_timeout_ms)
        await asyncio.sleep(1.5)

        crawler.xhs_client = await crawler.create_xhs_client(httpx_proxy_format)
        await crawler.xhs_client.update_cookies(browser_context=crawler.browser_context)

        if not await ensure_xhs_api_session(crawler):
            print(
                "[xhs_acceptance_bootstrap] 无法建立有效的小红书 API 会话。",
                file=sys.stderr,
            )
            await crawler.close()
            raise SystemExit(2)

        adapter = XHSAdapter(
            crawler.xhs_client,
            job_id=job.job_id,
            industry=job.industry,
            category=job.category,
        )
        db_path.parent.mkdir(parents=True, exist_ok=True)
        raw_store, norm_store = open_review_intel_stores(db_path)
        summary = await ReviewCollectionRunner().run(
            job,
            adapter,
            raw_store,
            norm_store,
            limits=limits,
        )
        await crawler.close()

    return summary
