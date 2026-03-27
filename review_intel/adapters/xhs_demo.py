# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""小红书适配器最小验收脚本：搜索 → 取 1～3 条帖子 → 拉一级评论 → 打印标准化样例。

**依赖**

- 工作目录为 MediaCrawler 仓库根目录（保证 ``import config``、``media_platform`` 可用）。
- 配置沿用 ``config/base_config.py`` / ``config/xhs_config.py``（登录方式、无头、CDP 等）。
- 首次运行需能完成小红书 Web 登录（扫码 / Cookie，与主爬虫一致）。

**实现说明**

浏览器启动与 ``XiaoHongShuClient`` 创建逻辑与 ``media_platform/xhs/core.py`` 中
``XiaoHongShuCrawler.start`` 前段一致（有意并列维护，避免改动 ``core.py``）。
若主流程变更，请对照更新本文件。

**运行**

.. code-block:: bash

   cd /path/to/MediaCrawler-main
   python -m review_intel.adapters.xhs_demo --keyword 防晒衣

"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys

import config
from media_platform.xhs.core import XiaoHongShuCrawler
from media_platform.xhs.exception import DataFetchError
from media_platform.xhs.login import XiaoHongShuLogin
from playwright.async_api import BrowserContext, Page, async_playwright
from tenacity import RetryError
from proxy.proxy_ip_pool import create_ip_pool
from tools import utils

from review_intel.adapters.xiaohongshu import XHSAdapter


async def _quick_probe_logged_in(browser_context: BrowserContext, page: Page) -> bool:
    """轻量判断「是否已登录」，避免误走扫码流程。

    **为何不用** ``XiaoHongShuLogin.check_login_state``：该方法带长重试，适合等用户扫码，
    不适合在 ``pong()`` 失败后做一次快速判断。

    逻辑对齐 ``login.py`` 中思路：侧栏「我」/ 英文 Me、可点击的个人主页链、以及常见登录 Cookie。
    """
    # 1) 侧栏「我」或英文 Me（与主站语言相关）
    for text in ("我", "Me"):
        sel = f"xpath=//a[contains(@href, '/user/profile/')]//span[text()='{text}']"
        try:
            if await page.is_visible(sel, timeout=800):
                utils.logger.info("[xhs_demo] login probe: profile span (%s) visible", text)
                return True
        except Exception:
            pass

    # 2) 任意可见的个人主页入口（不依赖文案）
    try:
        loc = page.locator("a[href*='/user/profile/']").first
        if await loc.is_visible(timeout=1200):
            utils.logger.info("[xhs_demo] login probe: profile link visible")
            return True
    except Exception:
        pass

    # 3) Cookie：已有会话则视为已登录（与 login.check_login_state 中 web_session 思路一致）
    try:
        _, cookie_dict = utils.convert_cookies(await browser_context.cookies())
        if cookie_dict.get("web_session"):
            utils.logger.info("[xhs_demo] login probe: web_session cookie present")
            return True
    except Exception:
        pass

    return False


async def _soft_resync_session(crawler: XiaoHongShuCrawler) -> bool:
    """刷新页面并同步 Cookie 到 httpx 客户端，再 ``pong()``。

    用于「浏览器里像已登录但 API 自检失败」时，先尝试对齐会话，避免立刻走扫码 DOM。
    """
    try:
        await crawler.context_page.reload(wait_until="domcontentloaded")
    except Exception as e:  # noqa: BLE001
        utils.logger.warning("[xhs_demo] soft resync reload failed: %s", e)
        return False
    await asyncio.sleep(2.0)
    await crawler.xhs_client.update_cookies(browser_context=crawler.browser_context)
    ok = await crawler.xhs_client.pong()
    if ok:
        utils.logger.info("[xhs_demo] soft resync: pong=True")
    return ok


async def _stabilize_session_after_login(crawler: XiaoHongShuCrawler) -> bool:
    """扫码/手机登录成功后，edith 与 Cookie 可能尚未对齐：同步 Cookie、回首页等待，多次重试 ``pong()``。"""
    for attempt in range(5):
        await crawler.xhs_client.update_cookies(browser_context=crawler.browser_context)
        if attempt == 0:
            try:
                await crawler.context_page.goto(
                    crawler.index_url, wait_until="domcontentloaded", timeout=60000
                )
            except Exception as e:  # noqa: BLE001
                utils.logger.warning("[xhs_demo] post-login goto index failed: %s", e)
        wait_s = 2.0 + attempt * 0.5
        await asyncio.sleep(wait_s)
        if await crawler.xhs_client.pong():
            utils.logger.info(
                "[xhs_demo] pong=True after login stabilize (attempt %s/5)", attempt + 1
            )
            return True
    return False


async def _run_xhs_login_safe(crawler: XiaoHongShuCrawler) -> bool:
    """调用 ``XiaoHongShuLogin.begin()``；失败时返回 False，不把 Playwright 超时直接抛到顶层。"""
    login_obj = XiaoHongShuLogin(
        login_type=config.LOGIN_TYPE,
        login_phone="",
        browser_context=crawler.browser_context,
        context_page=crawler.context_page,
        cookie_str=config.COOKIES,
    )
    try:
        await login_obj.begin()
    except SystemExit as se:
        utils.logger.warning("[xhs_demo] login module exited with SystemExit(%s)", se.code)
        return False
    except Exception as e:  # noqa: BLE001 — 含 Playwright TimeoutError
        utils.logger.exception("[xhs_demo] login flow failed: %s", e)
        return False
    await crawler.xhs_client.update_cookies(browser_context=crawler.browser_context)
    return True


async def ensure_xhs_api_session(crawler: XiaoHongShuCrawler) -> bool:
    """统一到 API ``pong()`` 有效。

    **原因说明（与「已登录但爬取出错」相关）**：

    - ``pong()`` 调的是 edith API 的 ``query_self``；与页面是否显示「我」、是否有 ``web_session`` 可能**不同步**。
    - 若 **pong=False** 但 **页面已是登录态**，旧逻辑会走 ``login_by_qrcode``；该流程假定**未登录首页**顶栏存在可点的「登录」按钮。
      已登录首页**没有**该按钮 → ``login_button_ele.click()`` 超时（你遇到的栈）。

    本函数顺序：**一次**软同步（单次 reload，避免连刷 3 次）→ 视情况打开 ``/login`` → 再走扫码/手机/Cookie；
    登录失效时仍会进入 ``XiaoHongShuLogin.begin()``，不再因 probe 而禁止扫码。
    """
    await crawler.xhs_client.update_cookies(browser_context=crawler.browser_context)
    if await crawler.xhs_client.pong():
        utils.logger.info("[xhs_demo] API session OK (pong=True), skip login UI")
        return True

    utils.logger.info("[xhs_demo] pong=False; soft resync 1/1 (single reload)")
    if await _soft_resync_session(crawler):
        return True

    probe = await _quick_probe_logged_in(crawler.browser_context, crawler.context_page)

    if probe:
        utils.logger.warning(
            "[xhs_demo] 页面/Cookie 显示已登录，但 pong 仍为 False。"
            "将尝试打开 /login 再同步 Cookie；若站点重定向回首页，后续扫码仍可能因 DOM 不匹配失败。"
        )
        try:
            await crawler.context_page.goto(
                f"{crawler.index_url}/login",
                wait_until="domcontentloaded",
                timeout=60000,
            )
            await asyncio.sleep(1.5)
            await crawler.xhs_client.update_cookies(browser_context=crawler.browser_context)
            if await crawler.xhs_client.pong():
                utils.logger.info("[xhs_demo] pong=True after visiting /login")
                return True
        except Exception as e:  # noqa: BLE001
            utils.logger.warning("[xhs_demo] goto /login skipped or failed: %s", e)

    if not probe:
        utils.logger.info("[xhs_demo] probe=False, run LOGIN_TYPE=%s", config.LOGIN_TYPE)
    else:
        utils.logger.warning(
            "[xhs_demo] probe=True 但 pong=False（常见于登录过期、Cookie 仍残留）。"
            "仍将尝试 %s；若顶栏无「登录」或长时间无二维码，请在窗口内手动退出账号后再扫码，"
            "或改用 LOGIN_TYPE=cookie / XHS_DEBUG_SELFINFO=1",
            config.LOGIN_TYPE,
        )
        if config.DEBUG_XHS_SELFINFO:
            await crawler.xhs_client.query_self()

    if not await _run_xhs_login_safe(crawler):
        if probe:
            print(
                "\n[xhs_demo] 扫码/登录流程未成功。若你**在浏览器里已经登录**，常见原因是：\n"
                "  · API 会话（pong）与页面登录态不一致；\n"
                "  · ``login_by_qrcode`` 需要在**未登录顶栏**出现「登录」按钮；已登录首页没有该节点 → 点击超时。\n"
                "建议：1) 在浏览器中**退出账号**后重新运行本脚本并完成扫码；\n"
                "      2) 或在 config 使用 LOGIN_TYPE=cookie 并配置 COOKIES；\n"
                "      3) 或清空/更换 SAVE_LOGIN_STATE 用户数据目录后重试。\n",
                file=sys.stderr,
            )
        return False

    # 登录模块已判定成功；对齐 httpx Cookie 与页面后再验 ping，避免「扫码成功但 selfinfo 尚未就绪」
    if await _stabilize_session_after_login(crawler):
        return True

    if await _quick_probe_logged_in(crawler.browser_context, crawler.context_page):
        utils.logger.warning(
            "[xhs_demo] selfinfo(pong) 仍为 False，但浏览器探测为已登录（常见于扫码刚完成、API 与 UI 不同步）。"
            "将继续抓取；若后续搜索/评论报「登录已过期」，请设 XHS_DEBUG_SELFINFO=1 或改用 Cookie。"
        )
        return True

    utils.logger.error(
        "[xhs_demo] Login UI 已成功但 pong 与页面探测均无法确认会话 — "
        "check QR / phone login, config.COOKIES, or SAVE_LOGIN_STATE user dir"
    )
    return False


def _format_request_error(exc: BaseException) -> str:
    """从 ``RetryError`` / ``DataFetchError`` 等取出可读说明。"""
    if isinstance(exc, RetryError):
        fut = exc.last_attempt
        if fut is not None and fut.done():
            inner = fut.exception()
            if inner is not None:
                return str(inner)
        return str(exc)
    return str(exc)


def _looks_like_login_expired(msg: str) -> bool:
    m = (msg or "").lower()
    if "登录" in msg or "登录已过期" in msg:
        return True
    if "expired" in m and "login" in m:
        return True
    return False


async def _run_demo_async(keyword: str, max_notes: int, max_comments: int) -> None:
    """在单个 playwright 会话内完成 bootstrap + 适配器调用。"""
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
        await crawler.context_page.goto(crawler.index_url, wait_until="domcontentloaded")
        await asyncio.sleep(1.5)

        crawler.xhs_client = await crawler.create_xhs_client(httpx_proxy_format)
        await crawler.xhs_client.update_cookies(browser_context=crawler.browser_context)

        if not await ensure_xhs_api_session(crawler):
            print(
                "\n[xhs_demo] 无法建立有效的小红书 API 会话（pong=False）。"
                "请完成扫码/手机登录或检查 config 与 Cookie。\n",
                file=sys.stderr,
            )
            await crawler.close()
            raise SystemExit(2)

        adapter = XHSAdapter(
            crawler.xhs_client,
            job_id="xhs-demo",
            industry=None,
            category=None,
        )

        try:
            page = await adapter.search_posts(keyword, None)
        except (RetryError, DataFetchError) as e:
            msg = _format_request_error(e)
            print(f"\n[xhs_demo] 搜索失败: {msg}\n", file=sys.stderr)
            if _looks_like_login_expired(msg):
                print(
                    "[xhs_demo] 提示：疑似登录已过期。请重新运行本脚本并完成登录；"
                    "若仍失败，请清除浏览器用户目录后重试（与 SAVE_LOGIN_STATE 相关）。\n",
                    file=sys.stderr,
                )
            await crawler.close()
            raise SystemExit(3) from e
        hits = page.items[:max_notes]
        print(f"[demo] search hits (first {max_notes}): {len(hits)}")
        for i, hit in enumerate(hits):
            pid = hit.get("id") or hit.get("post_id")
            if not pid:
                continue
            detail = await adapter.fetch_post_detail(str(pid))
            norm_post = adapter.normalize_post(detail)
            print(f"\n--- note {i+1} post_id={pid} ---")
            print(json.dumps(norm_post, ensure_ascii=False, indent=2)[:2000])

            cpage = await adapter.fetch_comments(str(pid), None)
            print(f"[demo] comments page size={len(cpage.items)}")
            for j, ev in enumerate(cpage.items[:max_comments]):
                raw_d = ev.model_dump(mode="json")
                nr = adapter.normalize_comment(raw_d)
                print(f"  comment {j+1}: {json.dumps(nr.model_dump(mode='json'), ensure_ascii=False)[:800]}")

        await crawler.close()


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    p = argparse.ArgumentParser(description="XHSAdapter 最小验收（真实请求）")
    p.add_argument("--keyword", default="防晒", help="搜索关键词")
    p.add_argument("--max-notes", type=int, default=2, help="取前几条帖子")
    p.add_argument("--max-comments", type=int, default=3, help="每条帖子打印几条评论")
    args = p.parse_args(argv)
    asyncio.run(_run_demo_async(args.keyword, args.max_notes, args.max_comments))


if __name__ == "__main__":
    main(sys.argv[1:])
