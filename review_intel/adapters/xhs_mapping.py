# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""小红书 Web API 响应 → review_intel 领域模型的纯映射函数。

本模块**不**依赖 ``XiaoHongShuClient``，仅消费 ``dict`` 结构，便于单测与替换数据源。
字段含义参考 ``store/xhs/__init__.py`` 中 ``update_xhs_note_comment`` 对评论结构的约定，
以及 ``media_platform/xhs/core.py`` 对搜索结果条目的使用方式（``id`` / ``xsec_*``）。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from review_intel.adapters.types import JsonObject
from review_intel.schemas.enums import ContentType, PlatformType
from review_intel.schemas.normalized import NormalizedReview
from review_intel.schemas.pages import CommentPage, SearchPage


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def xhs_timestamp_to_utc(value: Any) -> datetime:
    """将小红书常见的时间戳（毫秒或秒）或 ISO 字符串转为 UTC ``datetime``。"""
    if value is None:
        return _utc_now()
    if isinstance(value, str) and value.strip():
        try:
            s = value.strip().replace("Z", "+00:00")
            return datetime.fromisoformat(s)
        except ValueError:
            return _utc_now()
    try:
        n = float(value)
    except (TypeError, ValueError):
        return _utc_now()
    # 13 位毫秒
    if n > 1e12:
        n = n / 1000.0
    elif n > 1e10:
        n = n / 1000.0
    return datetime.fromtimestamp(n, tz=timezone.utc)


def search_items_to_hit_dicts(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """将搜索 API 的 ``items`` 转为 ``SearchPage.items`` 用的宽松 dict（含 runner 所需 ``id``）。"""
    out: list[dict[str, Any]] = []
    for it in items:
        if it.get("model_type") in ("rec_query", "hot_query"):
            continue
        nid = it.get("id") or (it.get("note_card") or {}).get("note_id")
        if not nid:
            continue
        nid = str(nid)
        card = it.get("note_card") or {}
        # 与 core 一致：token 多在顶层；部分版本在 note_card 内
        xsec_token = str(
            it.get("xsec_token")
            or card.get("xsec_token")
            or ""
        )
        xsec_source = str(
            it.get("xsec_source")
            or card.get("xsec_source")
            or "pc_search"
        )
        body = card if card else it
        title = str(body.get("display_title") or body.get("title") or "")[:500]
        desc = str(body.get("desc") or "")[:500]
        out.append(
            {
                "id": nid,
                "post_id": nid,
                "title": title,
                "snippet": desc,
                "xsec_token": xsec_token,
                "xsec_source": xsec_source,
            }
        )
    return out


def build_search_page_from_api(
    *,
    api_data: dict[str, Any],
    search_id: str,
    page: int,
    job_id: str | None,
) -> SearchPage:
    """由 ``get_note_by_keyword`` 返回的 ``data`` 构造 ``SearchPage``。"""
    items_raw = list(api_data.get("items") or [])
    hit_items = search_items_to_hit_dicts(items_raw)
    has_more = bool(api_data.get("has_more", False))
    next_cursor: str | None = None
    if has_more:
        import json

        next_cursor = json.dumps({"page": page + 1, "search_id": search_id}, separators=(",", ":"))
    return SearchPage(
        items=hit_items,
        next_cursor=next_cursor,
        page_token=None,
        has_more=has_more,
        total_count=api_data.get("total_count"),
        job_id=job_id,
    )


def _raw_note_extra_meta(note_id: str, note_context: dict[str, Any] | None) -> dict[str, Any]:
    """笔记级窄字段写入 Raw ``extra_meta``（与 ``raw_payload`` 全量并存）。"""
    out: dict[str, Any] = {"note_id": note_id}
    if not note_context:
        return out
    for key in ("note_title", "note_type", "note_publish_time"):
        if key in note_context and note_context[key] is not None:
            out[key] = note_context[key]
    return out


def xhs_comment_dict_to_raw_event(
    *,
    note_id: str,
    comment: dict[str, Any],
    job_id: str,
    note_context: dict[str, Any] | None = None,
) -> "RawReviewEvent":
    """单条一级评论 → ``RawReviewEvent``。"""
    from review_intel.schemas.raw_event import RawReviewEvent

    uid = str(comment.get("id") or comment.get("comment_id") or "")
    user_info = comment.get("user_info") or {}
    author_id = str(user_info.get("user_id") or "")
    text = str(comment.get("content") or "").strip()
    ts = xhs_timestamp_to_utc(comment.get("create_time"))
    event_id = f"xhs:{note_id}:{uid}" if uid else f"xhs:{note_id}:unknown"
    return RawReviewEvent(
        event_id=event_id,
        platform=PlatformType.XHS,
        content_type=ContentType.COMMENT,
        source_id=uid or event_id,
        parent_id=note_id,
        author_id=author_id,
        publish_time=ts,
        raw_text=text,
        raw_metrics={
            "like_count": comment.get("like_count", 0),
            "sub_comment_count": comment.get("sub_comment_count", 0),
        },
        url=f"https://www.xiaohongshu.com/explore/{note_id}" if note_id else None,
        job_id=job_id,
        extra_meta=_raw_note_extra_meta(note_id, note_context),
        raw_payload=dict(comment),
    )


def build_comment_page_from_api(
    *,
    note_id: str,
    api_data: dict[str, Any],
    job_id: str,
    note_context: dict[str, Any] | None = None,
) -> CommentPage:
    """由 ``get_note_comments`` 返回的 ``data`` 构造 ``CommentPage``。"""
    comments = list(api_data.get("comments") or [])
    items = [
        xhs_comment_dict_to_raw_event(
            note_id=note_id,
            comment=c,
            job_id=job_id,
            note_context=note_context,
        )
        for c in comments
    ]
    cursor = str(api_data.get("cursor") or "")
    has_more = bool(api_data.get("has_more", False))
    next_c: str | None = cursor if has_more and cursor else None
    return CommentPage(
        items=items,
        next_cursor=next_c,
        page_token=None,
        has_more=has_more,
        total_count=api_data.get("total_count"),
        job_id=job_id,
    )


def normalize_xhs_post_dict(raw: JsonObject) -> JsonObject:
    """帖子详情 note_card 风格 dict → 统一窄表（供调度/展示，非平台原始全量）。"""
    return {
        "platform": "xhs",
        "note_id": raw.get("note_id") or raw.get("id"),
        "title": raw.get("title") or raw.get("display_title"),
        "desc": raw.get("desc"),
        "type": raw.get("type"),
        "time": raw.get("time"),
        "interact_info": raw.get("interact_info") or {},
        "user": {"user_id": (raw.get("user") or {}).get("user_id"), "nickname": (raw.get("user") or {}).get("nickname")},
        "xsec_token": raw.get("xsec_token"),
        "xsec_source": raw.get("xsec_source"),
    }


def _comment_extra_meta_from_xhs_dict(raw: JsonObject, note_id: str) -> dict[str, Any]:
    """评论 dict 侧可稳定抽取的字段 → ``extra_meta``（后与 Raw 层笔记字段合并，同名以评论为准）。"""
    user_info = raw.get("user_info") if isinstance(raw.get("user_info"), dict) else {}
    user_name = str((user_info or {}).get("nickname") or "").strip()
    parent = raw.get("parent_comment_id") or raw.get("parent_comment_id_str") or ""
    level = 2 if str(parent).strip() else 1
    like_raw = raw.get("like_count")
    sub_raw = raw.get("sub_comment_count")
    like_count: int | None
    reply_count: int | None
    try:
        like_count = int(like_raw) if like_raw is not None else None
    except (TypeError, ValueError):
        like_count = None
    try:
        reply_count = int(sub_raw) if sub_raw is not None else None
    except (TypeError, ValueError):
        reply_count = None
    em: dict[str, Any] = {
        "note_id": note_id or None,
        "comment_level": level,
    }
    if user_name:
        em["user_name"] = user_name
    if like_count is not None:
        em["like_count"] = like_count
    if reply_count is not None:
        em["reply_count"] = reply_count
    return em


def normalize_xhs_comment_dict(
    raw: JsonObject,
    *,
    industry: str | None = None,
    category: str | None = None,
    raw_extra_meta: dict[str, Any] | None = None,
) -> NormalizedReview:
    """评论 API 单条 dict → ``NormalizedReview``（与 ``normalize_post`` 分离，避免混用）。

    ``raw_extra_meta`` 通常来自 ``RawReviewEvent.extra_meta``（笔记标题等）；与评论侧 ``extra_meta`` 合并时，
    同名键以评论字段为准。
    """
    note_id = str(raw.get("note_id") or "")
    cid = str(raw.get("id") or raw.get("comment_id") or "")
    text = str(raw.get("content") or "").strip()
    rid = f"norm:xhs:{note_id}:{cid}" if cid else f"norm:xhs:{note_id}:unknown"
    pub = xhs_timestamp_to_utc(raw.get("create_time"))
    likes = raw.get("like_count")
    eng: float | None = None
    if likes is not None:
        try:
            eng = min(1.0, float(likes) / 1000.0)
        except (TypeError, ValueError):
            eng = None
    em: dict[str, Any] = dict(raw_extra_meta or {})
    comment_em = _comment_extra_meta_from_xhs_dict(raw, note_id)
    em.update(comment_em)
    return NormalizedReview(
        review_id=rid,
        platform=PlatformType.XHS,
        industry=industry,
        category=category,
        brand=None,
        query_hit_terms=[],
        review_text=text,
        publish_time=pub,
        engagement_score=eng,
        freshness_score=None,
        quality_score=None,
        spam_score=None,
        author_type="xhs_user",
        evidence_url=f"https://www.xiaohongshu.com/explore/{note_id}" if note_id else None,
        source_post_id=note_id or None,
        source_comment_id=cid or None,
        extra_meta=em,
    )
