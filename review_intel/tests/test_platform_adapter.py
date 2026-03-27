# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""PlatformAdapter / DummyAdapter 行为测试。"""

from __future__ import annotations

import pytest

from review_intel.adapters import DummyAdapter, PlatformAdapter, RateLimitPolicy
from review_intel.schemas.pages import CommentPage, SearchPage


@pytest.mark.asyncio
async def test_dummy_adapter_async_methods() -> None:
    """异步方法返回约定 schema 类型。"""
    adapter: PlatformAdapter = DummyAdapter()
    sp = await adapter.search_posts("kw", None)
    assert isinstance(sp, SearchPage)
    detail = await adapter.fetch_post_detail("p1")
    assert detail["post_id"] == "p1"
    cc = await adapter.fetch_comments("p1", None)
    assert isinstance(cc, CommentPage)
    cr = await adapter.fetch_replies("c1", None)
    assert isinstance(cr, CommentPage)


def test_dummy_adapter_sync_methods() -> None:
    """同步方法与策略。"""
    adapter = DummyAdapter()
    assert adapter.adapter_name() == "dummy"
    pol = adapter.rate_limit_policy()
    assert isinstance(pol, RateLimitPolicy)
    assert pol.max_concurrency >= 1

    norm_post = adapter.normalize_post({"title": "t", "extra": 1})
    assert norm_post["normalized"] is True
    assert "title" in norm_post

    norm_c = adapter.normalize_comment({"comment_id": "cid-9", "body": "x"})
    assert norm_c.source_comment_id == "cid-9"
