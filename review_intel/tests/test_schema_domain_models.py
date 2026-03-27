# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""领域模型（Raw/Normalized/Page）与枚举的契约测试。"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from review_intel.schemas.enums import ContentType, JobStatus, PlatformType
from review_intel.schemas.examples import (
    example_comment_page,
    example_normalized_review,
    example_raw_review_event,
    example_search_page,
)
from review_intel.schemas.normalized import NormalizedReview
from review_intel.schemas.pages import CommentPage, SearchPage
from review_intel.schemas.raw_event import RawReviewEvent


def test_enums_are_str_subclass() -> None:
    """枚举成员可与 str 比较，便于 JSON/DB。"""
    assert PlatformType.XHS.value == "xhs"
    assert ContentType.COMMENT.value == "comment"
    assert JobStatus.PENDING.value == "pending"


def test_raw_review_event_example_roundtrip() -> None:
    """RawReviewEvent 工厂与 JSON 往返。"""
    ev = example_raw_review_event()
    assert isinstance(ev, RawReviewEvent)
    assert ev.event_id
    assert ev.raw_payload is not None
    data = ev.model_dump(mode="json")
    back = RawReviewEvent.model_validate(data)
    assert back.event_id == ev.event_id
    json.dumps(data)


def test_normalized_review_example_roundtrip() -> None:
    """NormalizedReview 工厂与 JSON 往返。"""
    n = example_normalized_review()
    assert isinstance(n, NormalizedReview)
    assert n.review_id
    assert n.job_id
    assert "like_count" in n.extra_meta
    data = n.model_dump(mode="json")
    back = NormalizedReview.model_validate(data)
    assert back.review_id == n.review_id
    assert back.extra_meta.get("like_count") == n.extra_meta.get("like_count")
    json.dumps(data)


def test_search_and_comment_pages() -> None:
    """分页模型与 items 类型。"""
    sp = example_search_page()
    cp = example_comment_page()
    assert isinstance(sp, SearchPage)
    assert isinstance(cp, CommentPage)
    assert isinstance(sp.items, list)
    assert all(isinstance(x, dict) for x in sp.items)
    assert all(isinstance(x, RawReviewEvent) for x in cp.items)
    sjson = sp.model_dump(mode="json")
    cjson = cp.model_dump(mode="json")
    SearchPage.model_validate(sjson)
    CommentPage.model_validate(cjson)
    json.dumps(sjson)
    json.dumps(cjson)


def test_datetime_json_encoding() -> None:
    """含 datetime 的 dump 可被 json 序列化（字符串化）。"""
    ev = example_raw_review_event()
    d = ev.model_dump(mode="json")
    assert isinstance(d["publish_time"], str)
    assert isinstance(d["crawl_time"], str)


def test_explicit_constructors() -> None:
    """显式构造与默认值。"""
    t = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    ev = RawReviewEvent(
        event_id="e1",
        platform=PlatformType.UNKNOWN,
        content_type=ContentType.COMMENT,
        source_id="s1",
        parent_id=None,
        author_id="a1",
        publish_time=t,
        crawl_time=t,
        raw_text="hi",
        job_id="j1",
    )
    assert ev.raw_media == []
    assert ev.raw_metrics == {}
    assert ev.raw_payload == {}
    assert ev.extra_meta == {}
