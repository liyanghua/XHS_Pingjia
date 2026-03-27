# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""小红书 ``PlatformAdapter``：复用 ``media_platform.xhs.client.XiaoHongShuClient`` 的 HTTP 能力。

**接入假设**

- 调用方已按 ``media_platform/xhs/core.py`` 的方式完成浏览器启动、登录，并得到带签名能力的
  ``XiaoHongShuClient``（依赖 Playwright 页面对 ``X-S`` 等头签名）。
- ``post_id`` 即小红书 ``note_id``；搜索命中条目的 ``xsec_token`` / ``xsec_source`` 由适配器在
  ``search_posts`` 时缓存，供 ``fetch_post_detail`` / ``fetch_comments`` 使用。
- 若仅知道 ``note_id`` 而无缓存（例如冷启动直拉详情），将使用 ``xsec_*`` 空串与默认
  ``pc_search``；``get_note_by_id``（/feed）失败或返回空时，会回退 ``get_note_by_id_from_html``，
  与 ``media_platform/xhs/core.py`` 中 ``get_note_detail_async_task`` 行为一致。

**与 Runner 的边界**

- 网络与签名：全部由现有 ``XiaoHongShuClient`` 完成。
- 标准化：见 ``xhs_mapping.py``；Runner 只接收 ``SearchPage`` / ``CommentPage`` / ``NormalizedReview``。
"""

from __future__ import annotations

import json
import logging
from typing import Any

from tenacity import RetryError

from media_platform.xhs.client import XiaoHongShuClient

from review_intel.adapters.base import PlatformAdapter
from review_intel.adapters.types import JsonObject, RateLimitPolicy
from review_intel.adapters.xhs_mapping import (
    build_comment_page_from_api,
    build_search_page_from_api,
    normalize_xhs_comment_dict,
    normalize_xhs_post_dict,
    xhs_timestamp_to_utc,
)
from review_intel.schemas.normalized import NormalizedReview
from review_intel.schemas.pages import CommentPage, SearchPage

logger = logging.getLogger(__name__)


def _parse_search_cursor(cursor: str | None) -> tuple[int, str]:
    """首页 ``cursor is None`` 时生成新 ``search_id``；否则解析 JSON ``{page, search_id}``。"""
    from media_platform.xhs.help import get_search_id

    if not cursor:
        return 1, get_search_id()
    try:
        d = json.loads(cursor)
        return int(d["page"]), str(d["search_id"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
        raise ValueError(f"invalid search cursor: {cursor!r}") from e


class XHSAdapter(PlatformAdapter):
    """小红书适配器：委托 ``XiaoHongShuClient``，映射见 ``xhs_mapping``。"""

    def __init__(
        self,
        client: XiaoHongShuClient,
        *,
        job_id: str = "xhs-adapter-local",
        industry: str | None = None,
        category: str | None = None,
        page_size: int = 20,
    ) -> None:
        self._client = client
        self._job_id = job_id
        self._industry = industry
        self._category = category
        self._page_size = page_size
        self._note_sec: dict[str, tuple[str, str]] = {}

    def adapter_name(self) -> str:
        return "xhs"

    def rate_limit_policy(self) -> RateLimitPolicy:
        return RateLimitPolicy(min_interval_seconds=1.0, max_concurrency=2, burst=4)

    def _remember_note_tokens(self, items: list[dict[str, Any]]) -> None:
        for it in items:
            nid = it.get("id") or it.get("post_id")
            if not nid:
                continue
            nid = str(nid)
            tok = str(it.get("xsec_token") or "")
            src = str(it.get("xsec_source") or "pc_search")
            self._note_sec[nid] = (tok, src)

    async def search_posts(self, query: str, cursor: str | None = None) -> SearchPage:
        from media_platform.xhs.field import SearchNoteType, SearchSortType

        page, search_id = _parse_search_cursor(cursor)
        data = await self._client.get_note_by_keyword(
            keyword=query.strip(),
            search_id=search_id,
            page=page,
            page_size=self._page_size,
            sort=SearchSortType.GENERAL,
            note_type=SearchNoteType.ALL,
        )
        if not isinstance(data, dict):
            data = {}
        sp = build_search_page_from_api(
            api_data=data,
            search_id=search_id,
            page=page,
            job_id=self._job_id,
        )
        self._remember_note_tokens(sp.items)
        return sp

    async def fetch_post_detail(self, post_id: str) -> JsonObject:
        """拉取帖子详情：先 ``/feed`` API，失败或空则回退 HTML 解析（与 ``core.get_note_detail_async_task`` 一致）。"""
        xsec_token, xsec_source = self._note_sec.get(post_id, ("", "pc_search"))
        detail: dict[str, Any] | None = None
        try:
            got = await self._client.get_note_by_id(post_id, xsec_source, xsec_token)
            detail = got if got else None
        except RetryError as e:
            logger.info(
                "get_note_by_id exhausted retries for note_id=%s, fallback to HTML: %s",
                post_id,
                e,
            )
        except Exception as e:  # noqa: BLE001 — 对齐主流程，避免单次 DataFetchError 直接终止
            logger.warning("get_note_by_id failed for note_id=%s: %s", post_id, e)

        if not detail:
            try:
                detail = await self._client.get_note_by_id_from_html(
                    post_id,
                    xsec_source,
                    xsec_token,
                    enable_cookie=True,
                )
            except Exception as e:
                logger.warning("get_note_by_id_from_html failed for note_id=%s: %s", post_id, e)
                detail = None

        if not detail:
            logger.warning("fetch_post_detail empty for note_id=%s", post_id)
        out = dict(detail) if detail else {}
        out.setdefault("note_id", post_id)
        out["xsec_token"] = out.get("xsec_token") or xsec_token
        out["xsec_source"] = out.get("xsec_source") or xsec_source
        return out

    async def fetch_comments(self, post_id: str, cursor: str | None = None) -> CommentPage:
        xsec_token, _ = self._note_sec.get(post_id, ("", ""))
        if not xsec_token:
            logger.warning(
                "fetch_comments: no cached xsec_token for note_id=%s; API 可能失败。请先 search_posts 命中该帖。",
                post_id,
            )
        note_context: dict[str, Any] = {}
        try:
            detail = await self.fetch_post_detail(post_id)
            if detail:
                title = str(detail.get("title") or detail.get("display_title") or "")[:500]
                if title:
                    note_context["note_title"] = title
                ntype = detail.get("type")
                if ntype is not None:
                    note_context["note_type"] = str(ntype)
                t = detail.get("time")
                if t is not None:
                    note_context["note_publish_time"] = xhs_timestamp_to_utc(t).isoformat()
        except Exception as e:  # noqa: BLE001 — 笔记元信息失败不阻断评论拉取
            logger.debug("fetch_post_detail for note_meta failed note_id=%s: %s", post_id, e)

        cur = cursor or ""
        data = await self._client.get_note_comments(
            note_id=post_id,
            xsec_token=xsec_token,
            cursor=cur,
        )
        if not isinstance(data, dict):
            data = {}
        return build_comment_page_from_api(
            note_id=post_id,
            api_data=data,
            job_id=self._job_id,
            note_context=note_context if note_context else None,
        )

    async def fetch_replies(self, comment_id: str, cursor: str | None = None) -> CommentPage:
        raise NotImplementedError(
            "小红书二级评论请使用 media_platform.xhs.client.XiaoHongShuClient.get_note_sub_comments；"
            "需在适配层补充 note_id、root_comment_id 与 xsec_token 的关联缓存后再实现。"
        )

    def normalize_post(self, raw: JsonObject) -> JsonObject:
        return normalize_xhs_post_dict(raw)

    def normalize_comment(self, raw: JsonObject) -> NormalizedReview:
        payload = raw.get("raw_payload")
        raw_ex: dict[str, Any] = {}
        em = raw.get("extra_meta")
        if isinstance(em, dict):
            raw_ex = em
        base: dict[str, Any]
        if isinstance(payload, dict) and (payload.get("id") or payload.get("comment_id")):
            base = dict(payload)
            base.setdefault("note_id", raw.get("parent_id"))
        else:
            metrics = raw.get("raw_metrics") if isinstance(raw.get("raw_metrics"), dict) else {}
            base = {
                "id": raw.get("source_id") or raw.get("id"),
                "note_id": raw.get("parent_id"),
                "content": raw.get("raw_text") or raw.get("content"),
                "create_time": raw.get("create_time"),
                "user_info": raw.get("user_info") or {},
                "like_count": raw.get("like_count", metrics.get("like_count", 0)),
                "sub_comment_count": metrics.get("sub_comment_count", 0),
            }
        return normalize_xhs_comment_dict(
            base,
            industry=self._industry,
            category=self._category,
            raw_extra_meta=raw_ex,
        )
