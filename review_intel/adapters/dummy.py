# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""占位适配器：返回固定 mock 数据，用于管线联调与单测。"""

from __future__ import annotations

from review_intel.adapters.base import PlatformAdapter
from review_intel.adapters.types import JsonObject, RateLimitPolicy
from review_intel.schemas.examples import (
    example_comment_page,
    example_normalized_review,
    example_search_page,
)
from review_intel.schemas.normalized import NormalizedReview
from review_intel.schemas.pages import CommentPage, SearchPage


class DummyAdapter(PlatformAdapter):
    """不访问外网的假适配器；所有 ID/query 参数均被忽略，仅返回可序列化样例。"""

    def adapter_name(self) -> str:
        return "dummy"

    def rate_limit_policy(self) -> RateLimitPolicy:
        return RateLimitPolicy(
            min_interval_seconds=0.0,
            max_concurrency=4,
            burst=8,
        )

    async def search_posts(self, query: str, cursor: str | None = None) -> SearchPage:
        _ = (query, cursor)
        return example_search_page()

    async def fetch_post_detail(self, post_id: str) -> JsonObject:
        return {
            "post_id": post_id,
            "title": "dummy-post-title",
            "snippet": "mock snippet",
            "metrics": {"likes": 0},
        }

    async def fetch_comments(self, post_id: str, cursor: str | None = None) -> CommentPage:
        _ = (post_id, cursor)
        return example_comment_page()

    async def fetch_replies(self, comment_id: str, cursor: str | None = None) -> CommentPage:
        _ = (comment_id, cursor)
        return example_comment_page()

    def normalize_post(self, raw: JsonObject) -> JsonObject:
        return {
            "normalized": True,
            "source_keys": sorted(raw.keys()),
            "title": raw.get("title", ""),
        }

    def normalize_comment(self, raw: JsonObject) -> NormalizedReview:
        base = example_normalized_review()
        rid = raw.get("comment_id") or raw.get("source_id")
        if isinstance(rid, str) and rid:
            return base.model_copy(update={"source_comment_id": rid})
        return base
