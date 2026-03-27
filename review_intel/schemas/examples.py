# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""领域模型样例工厂，供测试与文档示例统一引用。"""

from __future__ import annotations

from datetime import datetime, timezone

from review_intel.schemas.enums import ContentType, PlatformType
from review_intel.schemas.normalized import NormalizedReview
from review_intel.schemas.pages import CommentPage, SearchPage
from review_intel.schemas.raw_event import RawReviewEvent


def _ts() -> datetime:
    return datetime(2025, 3, 1, 8, 30, 0, tzinfo=timezone.utc)


def example_raw_review_event() -> RawReviewEvent:
    """构造一条典型的原始评价事件。"""
    t = _ts()
    return RawReviewEvent(
        event_id="xhs:review:demo-001",
        platform=PlatformType.XHS,
        content_type=ContentType.COMMENT,
        source_id="comment-demo-001",
        parent_id="note-demo-100",
        author_id="user-42",
        publish_time=t,
        crawl_time=t,
        raw_text="  示例评论正文  ",
        raw_media=[{"type": "image", "url": "https://example.com/i.jpg"}],
        raw_metrics={"likes": 3},
        url="https://example.com/note/100#c1",
        job_id="job-demo-1",
        extra_meta={
            "note_id": "note-demo-100",
            "note_title": "示例笔记标题",
            "note_type": "normal",
        },
        raw_payload={"note": "opaque platform json"},
    )


def example_normalized_review() -> NormalizedReview:
    """构造一条典型的归一化评价。"""
    t = _ts()
    return NormalizedReview(
        job_id="job-demo-1",
        review_id="norm:xhs:demo-001",
        platform=PlatformType.XHS,
        industry="美妆",
        category="口红",
        brand="DemoBrand",
        query_hit_terms=["好用", "显白"],
        review_text="示例归一化正文",
        publish_time=t,
        crawl_time=t,
        engagement_score=0.72,
        freshness_score=0.9,
        quality_score=0.85,
        spam_score=0.05,
        author_type="verified_user",
        evidence_url="https://example.com/evidence/1",
        source_post_id="note-demo-100",
        source_comment_id="comment-demo-001",
        extra_meta={
            "like_count": 3,
            "reply_count": 0,
            "user_name": "demo_user",
        },
    )


def example_search_page() -> SearchPage:
    """构造一页搜索结果。"""
    return SearchPage(
        items=[
            {"id": "n1", "title": "帖子 A", "snippet": "…"},
            {"id": "n2", "title": "帖子 B", "snippet": "…"},
        ],
        next_cursor="cursor-next-abc",
        page_token=None,
        has_more=True,
        total_count=120,
        job_id="job-search-1",
    )


def example_comment_page() -> CommentPage:
    """构造一页评论（含一条原始事件）。"""
    return CommentPage(
        items=[example_raw_review_event()],
        next_cursor=None,
        page_token="pt_next",
        has_more=False,
        total_count=1,
        job_id="job-cmt-1",
    )
