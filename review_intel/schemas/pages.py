# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""分页结果：搜索与评论列表抓取的标准包装（不绑定具体平台 API）。"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from review_intel.schemas.raw_event import RawReviewEvent


class SearchPage(BaseModel):
    """关键词/Feed 搜索一页结果；条目用宽松 dict 承载多变字段。"""

    items: list[dict[str, Any]] = Field(
        default_factory=list,
        description="搜索结果条目（平台原始或半结构化 dict）",
    )
    next_cursor: Optional[str] = Field(
        default=None,
        description="下一页游标（平台原生 cursor）",
    )
    page_token: Optional[str] = Field(
        default=None,
        description="下一页 token（与 cursor 二选一或并存，视平台而定）",
    )
    has_more: bool = Field(default=False, description="是否还有下一页")
    total_count: Optional[int] = Field(default=None, description="总命中数（若平台提供）")
    job_id: Optional[str] = Field(default=None, description="关联采集作业 ID")


class CommentPage(BaseModel):
    """评论列表一页结果；条目已映射为 `RawReviewEvent`。"""

    items: list[RawReviewEvent] = Field(
        default_factory=list,
        description="本页评论事件列表",
    )
    next_cursor: Optional[str] = Field(default=None, description="下一页游标")
    page_token: Optional[str] = Field(default=None, description="下一页 token")
    has_more: bool = Field(default=False, description="是否还有下一页")
    total_count: Optional[int] = Field(default=None, description="评论总数（若可知）")
    job_id: Optional[str] = Field(default=None, description="关联采集作业 ID")
